import type {
  AccountCatalogRow,
  DashboardSummary,
  DashboardEnvelope,
  EntryCreatedEnvelope,
  JournalEntry,
  ProductCatalogRow,
  RealtimeEnvelope,
  SalesBreakdownRow,
  SalesWorkspace,
  WorkspaceSnapshot,
} from '../api'

type RealtimeWorkspace = WorkspaceSnapshot & {
  __realtime?: {
    customerKeys: Record<string, true>
    saleProducts: Record<string, Record<string, true>>
  }
}

type RealtimeMetadata = NonNullable<RealtimeWorkspace['__realtime']>

export type PendingRealtimeEntry = {
  eventId: string
  backend: string
  ts: string
  receivedAt: number
  payload: JournalEntry
}

export type PendingRealtimeTransaction = {
  transactionKey: string
  backend: string
  eventType: string
  firstReceivedAt: number
  lastReceivedAt: number
  entries: PendingRealtimeEntry[]
}

const SNAPSHOT_ACK_GRACE_MS = 5000
const MAX_PENDING_ENTRY_AGE_MS = 45000
const MAX_PENDING_ENTRIES = 512

export function isEntryCreatedEnvelope(payload: RealtimeEnvelope | WorkspaceSnapshot): payload is EntryCreatedEnvelope {
  return 'event_type' in payload && payload.event_type === 'entry.created'
}

export function isDashboardEnvelope(payload: RealtimeEnvelope | WorkspaceSnapshot): payload is DashboardEnvelope {
  return 'event_type' in payload && payload.event_type === 'dashboard.snapshot'
}

type FeedLabelParams = {
  socketStatus: string
  liveWorkspace: WorkspaceSnapshot | null
  hasActiveFilters: boolean
  isPaused: boolean
  bufferedEventCount: number
  viewId: string
}

export function feedLabel({ socketStatus, liveWorkspace, hasActiveFilters, isPaused, bufferedEventCount, viewId }: FeedLabelParams) {
  if (isPaused) {
    return bufferedEventCount > 0
      ? `Visao congelada · ${bufferedEventCount} registros em espera`
      : 'Visao congelada'
  }
  if (viewId === 'queue' && socketStatus === 'open' && liveWorkspace && hasActiveFilters) {
    return 'Lancamentos filtrados em curso'
  }
  if (viewId === 'queue' && socketStatus === 'open' && liveWorkspace) {
    return 'Lancamentos em curso'
  }
  if (socketStatus === 'open' && liveWorkspace && hasActiveFilters) {
    return 'Leitura filtrada sincronizada'
  }
  if (socketStatus === 'open' && liveWorkspace) {
    return 'Leitura sincronizada'
  }
  if (socketStatus === 'connecting' && hasActiveFilters) {
    return 'Sincronizando recorte filtrado'
  }
  if (socketStatus === 'connecting') {
    return 'Sincronizando base operacional'
  }
  if (socketStatus === 'error' && hasActiveFilters) {
    return 'Leitura filtrada em contingencia'
  }
  if (socketStatus === 'error') {
    return 'Leitura em contingencia'
  }
  return 'Base operacional'
}

export function withRealtimeEntry(workspace: WorkspaceSnapshot | null, entry: JournalEntry, backend: string, ts: string) {
  if (!workspace) {
    return workspace
  }

  const nextEntries = [entry, ...workspace.entries.filter((item) => item.entry_id !== entry.entry_id)].slice(0, 180)

  const runtimeWorkspace = workspace as RealtimeWorkspace
  const runtime = runtimeWorkspace.__realtime ?? seedRealtimeMetadata(workspace)
  const nextSummary = updateSummary(workspace.summary, entry, backend, ts, nextEntries)
  const nextAccounts = updateAccounts(workspace.account_catalog, entry)
  const nextProducts = updateProducts(workspace.product_catalog, entry)
  const nextSalesWorkspace = updateSalesWorkspace(workspace.sales_workspace, entry, runtime)

  return {
    ...workspace,
    __realtime: runtime,
    backend,
    timestamp: ts,
    entries: nextEntries,
    summary: nextSummary,
    account_catalog: nextAccounts,
    product_catalog: nextProducts,
    sales_workspace: nextSalesWorkspace,
  }
}

export function preferIncomingSnapshot(current: WorkspaceSnapshot | null, incoming: WorkspaceSnapshot) {
  if (!current) {
    return incoming
  }

  const currentTs = Date.parse(current.timestamp)
  const incomingTs = Date.parse(incoming.timestamp)
  if (Number.isFinite(currentTs) && Number.isFinite(incomingTs) && incomingTs < currentTs) {
    return current
  }

  return incoming
}

export function appendPendingRealtimeEntry(
  pendingEntries: PendingRealtimeEntry[],
  envelope: EntryCreatedEnvelope,
  receivedAt = Date.now(),
) {
  const nextPendingEntry: PendingRealtimeEntry = {
    eventId: envelope.event_id,
    backend: envelope.backend,
    ts: envelope.ts,
    receivedAt,
    payload: envelope.payload,
  }

  const nextPendingEntries = [
    nextPendingEntry,
    ...pendingEntries.filter((item) => item.payload.entry_id !== envelope.payload.entry_id && item.eventId !== envelope.event_id),
  ]

  return nextPendingEntries.slice(0, MAX_PENDING_ENTRIES)
}

export function transactionKeyForEntry(entry: JournalEntry) {
  return entry.trace_id || entry.event_id || entry.entry_id
}

export function upsertPendingRealtimeTransaction(
  transactions: PendingRealtimeTransaction[],
  envelope: EntryCreatedEnvelope,
  receivedAt = Date.now(),
) {
  const transactionKey = transactionKeyForEntry(envelope.payload)
  const nextEntry: PendingRealtimeEntry = {
    eventId: envelope.event_id,
    backend: envelope.backend,
    ts: envelope.ts,
    receivedAt,
    payload: envelope.payload,
  }

  const existing = transactions.find((item) => item.transactionKey === transactionKey)
  const nextEntries = [
    nextEntry,
    ...(existing?.entries ?? []).filter((item) => item.payload.entry_id !== envelope.payload.entry_id && item.eventId !== envelope.event_id),
  ].sort((left, right) => {
    const leftTs = Date.parse(left.ts || left.payload.ingested_at || left.payload.occurred_at)
    const rightTs = Date.parse(right.ts || right.payload.ingested_at || right.payload.occurred_at)
    if (Number.isFinite(leftTs) && Number.isFinite(rightTs) && leftTs !== rightTs) {
      return leftTs - rightTs
    }
    return left.payload.entry_id.localeCompare(right.payload.entry_id)
  })

  const nextTransaction: PendingRealtimeTransaction = {
    transactionKey,
    backend: envelope.backend,
    eventType: envelope.payload.ontology_event_type,
    firstReceivedAt: existing?.firstReceivedAt ?? receivedAt,
    lastReceivedAt: receivedAt,
    entries: nextEntries,
  }

  const remainingTransactions = transactions.filter((item) => item.transactionKey !== transactionKey)
  return [nextTransaction, ...remainingTransactions].slice(0, MAX_PENDING_ENTRIES)
}

export function projectRealtimeWorkspace(baseWorkspace: WorkspaceSnapshot | null, pendingEntries: PendingRealtimeEntry[]) {
  if (!baseWorkspace) {
    return baseWorkspace
  }

  return pendingEntries.reduce<WorkspaceSnapshot | null>(
    (workspace, pendingEntry) => withRealtimeEntry(workspace, pendingEntry.payload, pendingEntry.backend, pendingEntry.ts),
    baseWorkspace,
  )
}

export function reconcilePendingRealtimeEntries(
  baseWorkspace: WorkspaceSnapshot | null,
  pendingEntries: PendingRealtimeEntry[],
  now = Date.now(),
) {
  if (pendingEntries.length === 0) {
    return pendingEntries
  }

  if (!baseWorkspace) {
    return pendingEntries.filter((item) => now - item.receivedAt <= MAX_PENDING_ENTRY_AGE_MS).slice(0, MAX_PENDING_ENTRIES)
  }

  const acknowledgedIds = snapshotAcknowledgedIds(baseWorkspace)
  const snapshotWatermark = snapshotWatermarkMs(baseWorkspace)
  const snapshotWindowSaturated = baseWorkspace.entries.length >= 180

  return pendingEntries.filter((pendingEntry) => {
    if (acknowledgedIds.has(pendingEntry.payload.entry_id) || acknowledgedIds.has(pendingEntry.eventId) || acknowledgedIds.has(pendingEntry.payload.event_id)) {
      return false
    }

    const pendingAgeMs = now - pendingEntry.receivedAt
    if (pendingAgeMs > MAX_PENDING_ENTRY_AGE_MS) {
      return false
    }

    const entryWatermark = entryWatermarkMs(pendingEntry)
    if (!Number.isFinite(entryWatermark)) {
      return true
    }

    if (snapshotWatermark >= entryWatermark + SNAPSHOT_ACK_GRACE_MS && snapshotWindowSaturated) {
      return false
    }

    return true
  }).slice(0, MAX_PENDING_ENTRIES)
}

export function reconcilePendingRealtimeTransactions(
  baseWorkspace: WorkspaceSnapshot | null,
  transactions: PendingRealtimeTransaction[],
  now = Date.now(),
) {
  if (transactions.length === 0) {
    return transactions
  }

  const acknowledgedIds = baseWorkspace ? snapshotAcknowledgedIds(baseWorkspace) : new Set<string>()

  return transactions
    .map((transaction) => ({
      ...transaction,
      entries: transaction.entries.filter((entry) => {
        if (acknowledgedIds.has(entry.payload.entry_id) || acknowledgedIds.has(entry.eventId) || acknowledgedIds.has(entry.payload.event_id)) {
          return false
        }
        return now - entry.receivedAt <= MAX_PENDING_ENTRY_AGE_MS
      }),
    }))
    .filter((transaction) => transaction.entries.length > 0)
    .slice(0, MAX_PENDING_ENTRIES)
}

export function releaseMatureRealtimeTransactions(
  transactions: PendingRealtimeTransaction[],
  holdbackMs: number,
  now = Date.now(),
) {
  const ready: PendingRealtimeTransaction[] = []
  const waiting: PendingRealtimeTransaction[] = []

  for (const transaction of transactions) {
    if (now - transaction.lastReceivedAt >= holdbackMs) {
      ready.push(transaction)
      continue
    }
    waiting.push(transaction)
  }

  ready.sort((left, right) => left.firstReceivedAt - right.firstReceivedAt)
  return { ready, waiting }
}

function snapshotAcknowledgedIds(workspace: WorkspaceSnapshot) {
  const ids = new Set<string>()

  for (const entry of workspace.entries) {
    if (entry.entry_id) {
      ids.add(entry.entry_id)
    }
    if (entry.event_id) {
      ids.add(entry.event_id)
    }
  }

  return ids
}

function snapshotWatermarkMs(workspace: WorkspaceSnapshot) {
  const timestamps = [
    workspace.timestamp,
    workspace.summary.timestamp,
    ...workspace.entries.flatMap((entry) => [entry.ingested_at, entry.occurred_at]),
  ]

  return timestamps.reduce((maxValue, value) => {
    const parsed = Date.parse(value)
    return Number.isFinite(parsed) ? Math.max(maxValue, parsed) : maxValue
  }, 0)
}

function entryWatermarkMs(pendingEntry: PendingRealtimeEntry) {
  const timestamps = [pendingEntry.ts, pendingEntry.payload.ingested_at, pendingEntry.payload.occurred_at]

  return timestamps.reduce((maxValue, value) => {
    const parsed = Date.parse(value)
    return Number.isFinite(parsed) ? Math.max(maxValue, parsed) : maxValue
  }, Number.NEGATIVE_INFINITY)
}

function seedRealtimeMetadata(workspace: WorkspaceSnapshot) {
  const customerKeys: Record<string, true> = {}
  const saleProducts: Record<string, Record<string, true>> = {}

  for (const sale of workspace.sales_workspace.sales) {
    const saleKey = sale.sale_id || sale.order_id
    const customerKey = sale.customer_email || sale.customer_id || saleKey
    customerKeys[customerKey] = true
    saleProducts[saleKey] = {
      [sale.lead_product || 'unknown-product']: true,
    }
  }

  return { customerKeys, saleProducts }
}

function round(value: number, digits = 2) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function percentage(numerator: number, denominator: number, digits = 2) {
  if (Math.abs(denominator) < 0.0001) {
    return null
  }
  return round((numerator / denominator) * 100, digits)
}

function incomeStatementMetrics(values: {
  revenue: number
  returns: number
  marketplaceFees: number
  freightOut: number
  bankFees: number
  financialExpenses: number
  otherExpenses: number
  cmv: number
}) {
  const netRevenue = round(values.revenue - values.returns)
  const grossProfit = round(netRevenue - values.cmv)
  const operatingExpenses = round(values.marketplaceFees + values.freightOut + values.bankFees + values.otherExpenses)
  const expenses = round(operatingExpenses + values.financialExpenses + values.cmv)
  const netIncome = round(netRevenue - expenses)
  return {
    netRevenue,
    grossProfit,
    operatingExpenses,
    expenses,
    netIncome,
    returnRatePct: percentage(values.returns, values.revenue),
    grossMarginPct: percentage(grossProfit, netRevenue),
    netMarginPct: percentage(netIncome, netRevenue),
    expenseRatioPct: percentage(operatingExpenses, netRevenue),
  }
}

function enrichProductMetrics(product: ProductCatalogRow): ProductCatalogRow {
  const revenueAmount = round(product.revenue_amount ?? 0)
  const returnAmount = round(product.return_amount ?? 0)
  const netRevenueAmount = round(product.net_revenue_amount ?? (revenueAmount - returnAmount))
  const cogsAmount = round(product.cogs_amount ?? 0)
  const sellingExpensesAmount = round(product.selling_expenses_amount ?? 0)
  const grossProfitAmount = round(product.gross_profit_amount ?? (netRevenueAmount - cogsAmount))
  const netProfitAmount = round(product.net_profit_amount ?? (grossProfitAmount - sellingExpensesAmount))
  const netSoldQuantity = round(Math.max(product.net_sold_quantity ?? (product.sold_quantity - product.returned_quantity), 0), 3)

  return {
    ...product,
    net_sold_quantity: netSoldQuantity,
    revenue_amount: revenueAmount,
    return_amount: returnAmount,
    net_revenue_amount: netRevenueAmount,
    cogs_amount: cogsAmount,
    selling_expenses_amount: sellingExpensesAmount,
    gross_profit_amount: grossProfitAmount,
    net_profit_amount: netProfitAmount,
    return_rate_pct: percentage(product.returned_quantity, product.sold_quantity, 2),
    gross_margin_pct: percentage(grossProfitAmount, netRevenueAmount, 2),
    net_margin_pct: percentage(netProfitAmount, netRevenueAmount, 2),
  }
}

function updateSummary(summary: DashboardSummary, entry: JournalEntry, backend: string, ts: string, nextEntries: JournalEntry[]): DashboardSummary {
  const cash = summary.balance_sheet.assets.cash
  const bankAccounts = summary.balance_sheet.assets.bank_accounts
  const recoverableTax = summary.balance_sheet.assets.recoverable_tax
  const inventory = summary.balance_sheet.assets.inventory
  const accountsPayableRaw = -summary.balance_sheet.liabilities.accounts_payable
  const shortTermLoansRaw = -summary.balance_sheet.liabilities.short_term_loans
  const taxPayableRaw = -summary.balance_sheet.liabilities.tax_payable
  const revenueRaw = -summary.income_statement.revenue
  const returnsRaw = summary.income_statement.returns
  const marketplaceFeesRaw = summary.income_statement.marketplace_fees
  const freightOutRaw = summary.income_statement.freight_out
  const bankFeesRaw = summary.income_statement.bank_fees
  const financialExpensesRaw = summary.income_statement.financial_expenses
  const otherExpensesRaw = summary.income_statement.other_expenses
  const cmvRaw = summary.income_statement.cmv

  let nextCash = cash
  let nextBankAccounts = bankAccounts
  let nextRecoverableTax = recoverableTax
  let nextInventory = inventory
  let nextAccountsPayableRaw = accountsPayableRaw
  let nextShortTermLoansRaw = shortTermLoansRaw
  let nextTaxPayableRaw = taxPayableRaw
  let nextRevenueRaw = revenueRaw
  let nextReturnsRaw = returnsRaw
  let nextMarketplaceFeesRaw = marketplaceFeesRaw
  let nextFreightOutRaw = freightOutRaw
  let nextBankFeesRaw = bankFeesRaw
  let nextFinancialExpensesRaw = financialExpensesRaw
  let nextOtherExpensesRaw = otherExpensesRaw
  let nextCmvRaw = cmvRaw

  switch (entry.account_role) {
    case 'cash':
      nextCash = round(nextCash + entry.signed_amount)
      break
    case 'bank_accounts':
      nextBankAccounts = round(nextBankAccounts + entry.signed_amount)
      break
    case 'recoverable_tax':
      nextRecoverableTax = round(nextRecoverableTax + entry.signed_amount)
      break
    case 'inventory':
      nextInventory = round(nextInventory + entry.signed_amount)
      break
    case 'accounts_payable':
      nextAccountsPayableRaw = round(nextAccountsPayableRaw + entry.signed_amount)
      break
    case 'short_term_loans':
      nextShortTermLoansRaw = round(nextShortTermLoansRaw + entry.signed_amount)
      break
    case 'tax_payable':
      nextTaxPayableRaw = round(nextTaxPayableRaw + entry.signed_amount)
      break
    case 'revenue':
      nextRevenueRaw = round(nextRevenueRaw + entry.signed_amount)
      break
    case 'returns':
      nextReturnsRaw = round(nextReturnsRaw + entry.signed_amount)
      break
    case 'marketplace_fees':
      nextMarketplaceFeesRaw = round(nextMarketplaceFeesRaw + entry.signed_amount)
      break
    case 'outbound_freight':
      nextFreightOutRaw = round(nextFreightOutRaw + entry.signed_amount)
      break
    case 'bank_fees':
      nextBankFeesRaw = round(nextBankFeesRaw + entry.signed_amount)
      break
    case 'interest_expense':
      nextFinancialExpensesRaw = round(nextFinancialExpensesRaw + entry.signed_amount)
      break
    case 'cogs':
      nextCmvRaw = round(nextCmvRaw + entry.signed_amount)
      break
    default:
      if (entry.entry_category === 'despesa' || entry.account_role.endsWith('_expense')) {
        nextOtherExpensesRaw = round(nextOtherExpensesRaw + entry.signed_amount)
      }
  }

  const accountsPayable = round(Math.abs(nextAccountsPayableRaw))
  const shortTermLoans = round(Math.abs(nextShortTermLoansRaw))
  const taxPayable = round(Math.abs(nextTaxPayableRaw))
  const revenue = round(Math.abs(nextRevenueRaw))
  const returns = round(nextReturnsRaw)
  const marketplaceFees = round(nextMarketplaceFeesRaw)
  const freightOut = round(nextFreightOutRaw)
  const bankFees = round(nextBankFeesRaw)
  const financialExpenses = round(nextFinancialExpensesRaw)
  const otherExpenses = round(nextOtherExpensesRaw)
  const cmv = round(nextCmvRaw)
  const metrics = incomeStatementMetrics({
    revenue,
    returns,
    marketplaceFees,
    freightOut,
    bankFees,
    financialExpenses,
    otherExpenses,
    cmv,
  })
  const liabilitiesTotal = round(accountsPayable + shortTermLoans + taxPayable)
  const netRevenue = metrics.netRevenue
  const grossProfit = metrics.grossProfit
  const operatingExpenses = metrics.operatingExpenses
  const expenses = metrics.expenses
  const netIncome = metrics.netIncome
  const assetsTotal = round(nextCash + nextBankAccounts + nextRecoverableTax + nextInventory)
  const equityTotal = round(assetsTotal - liabilitiesTotal)
  const totalLiabilitiesAndEquity = round(liabilitiesTotal + equityTotal)
  const difference = round(assetsTotal - totalLiabilitiesAndEquity)

  return {
    ...summary,
    backend,
    timestamp: ts,
    entries: nextEntries,
    balance_sheet: {
      assets: {
        cash: nextCash,
        bank_accounts: nextBankAccounts,
        recoverable_tax: nextRecoverableTax,
        inventory: nextInventory,
        total: assetsTotal,
      },
      liabilities: {
        accounts_payable: accountsPayable,
        short_term_loans: shortTermLoans,
        tax_payable: taxPayable,
        total: liabilitiesTotal,
      },
      equity: {
        current_earnings: netIncome,
        total: equityTotal,
      },
      total_liabilities_and_equity: totalLiabilitiesAndEquity,
      difference,
    },
    income_statement: {
      revenue,
      returns,
      net_revenue: netRevenue,
      marketplace_fees: marketplaceFees,
      freight_out: freightOut,
      bank_fees: bankFees,
      financial_expenses: financialExpenses,
      other_expenses: otherExpenses,
      operating_expenses: operatingExpenses,
      expenses,
      net_income: netIncome,
      cmv,
      gross_profit: grossProfit,
      return_rate_pct: metrics.returnRatePct,
      gross_margin_pct: metrics.grossMarginPct,
      net_margin_pct: metrics.netMarginPct,
      expense_ratio_pct: metrics.expenseRatioPct,
    },
  }
}

function updateAccounts(accounts: AccountCatalogRow[], entry: JournalEntry) {
  const index = accounts.findIndex((account) => account.account_code === entry.account_code)
  if (index < 0) {
    return accounts
  }

  const nextAccounts = [...accounts]
  nextAccounts[index] = {
    ...nextAccounts[index],
    current_balance: round(nextAccounts[index].current_balance + entry.signed_amount),
    entry_count: nextAccounts[index].entry_count + 1,
  }
  return nextAccounts
}

function supplyPlanForProduct(product: ProductCatalogRow) {
  const effectiveStock = Math.max(round(product.current_stock_quantity, 3), 0)
  const demandWeight = Math.max(Number(product.demand_weight ?? 0), 0.1)
  const dailyDemandUnits = round(Math.max(product.net_sold_quantity / 30, demandWeight), 3)
  const coverageDays = dailyDemandUnits > 0 ? round(effectiveStock / dailyDemandUnits, 1) : null
  const reorderPoint = Number(product.reorder_point ?? 0)
  const targetStock = Number(product.target_stock ?? 0)
  const suggestedPurchaseQuantity = round(Math.max(targetStock - effectiveStock, 0), 3)
  const suggestedSupplierName = product.supplier_name || product.preferred_supplier_id || 'Fornecedor padrão'
  const needsRestock = effectiveStock <= reorderPoint
  const purchaseRecommendation = needsRestock && suggestedPurchaseQuantity > 0
    ? `Comprar ${suggestedPurchaseQuantity} un de ${suggestedSupplierName}`
    : `Sem compra sugerida para ${suggestedSupplierName}`

  return {
    daily_demand_units: dailyDemandUnits,
    coverage_days: coverageDays,
    suggested_purchase_quantity: suggestedPurchaseQuantity,
    suggested_purchase_supplier_name: suggestedSupplierName,
    purchase_recommendation: purchaseRecommendation,
    needs_restock: needsRestock,
  }
}

function updateProducts(products: ProductCatalogRow[], entry: JournalEntry) {
  if (!entry.product_id) {
    return products
  }

  const index = products.findIndex((product) => product.product_id === entry.product_id)
  if (index < 0) {
    return products
  }

  const current = products[index]
  let currentStockQuantity = current.current_stock_quantity
  let soldQuantity = current.sold_quantity
  let netSoldQuantity = current.net_sold_quantity
  let returnedQuantity = current.returned_quantity
  let averagePurchasePrice = current.average_purchase_price
  const averageSalePrice = current.average_sale_price
  const revenueAmount = current.revenue_amount
  const returnAmount = current.return_amount
  const cogsAmount = current.cogs_amount
  const sellingExpensesAmount = current.selling_expenses_amount

  if (entry.account_role === 'inventory') {
    const stockDelta = entry.entry_side === 'debit' ? entry.quantity : -entry.quantity
    currentStockQuantity = round(current.current_stock_quantity + stockDelta, 3)
    returnedQuantity = entry.ontology_event_type === 'return'
      ? round(current.returned_quantity + entry.quantity, 3)
      : current.returned_quantity
    soldQuantity = entry.ontology_event_type === 'sale'
      ? round(current.sold_quantity + entry.quantity, 3)
      : current.sold_quantity
    netSoldQuantity = entry.ontology_event_type === 'sale'
      ? round(current.net_sold_quantity + entry.quantity, 3)
      : entry.ontology_event_type === 'return'
        ? round(Math.max(current.net_sold_quantity - entry.quantity, 0), 3)
        : current.net_sold_quantity
    averagePurchasePrice = entry.ontology_event_type === 'purchase'
      ? round((current.average_purchase_price + entry.unit_price) / 2, 2)
      : current.average_purchase_price
  }

  let nextProduct = enrichProductMetrics({
    ...current,
    current_stock_quantity: currentStockQuantity,
    sold_quantity: soldQuantity,
    net_sold_quantity: netSoldQuantity,
    returned_quantity: returnedQuantity,
    average_purchase_price: averagePurchasePrice,
    average_sale_price: averageSalePrice,
    revenue_amount: revenueAmount,
    return_amount: returnAmount,
    net_revenue_amount: current.net_revenue_amount,
    cogs_amount: cogsAmount,
    selling_expenses_amount: sellingExpensesAmount,
    gross_profit_amount: current.gross_profit_amount,
    net_profit_amount: current.net_profit_amount,
  })
  nextProduct = { ...nextProduct, ...supplyPlanForProduct(nextProduct) }

  const nextProducts = [...products]
  nextProducts[index] = nextProduct
  return nextProducts
}

function createEmptyBreakdown(label: string): SalesBreakdownRow {
  return { label, order_count: 0, quantity: 0, gross_sales: 0, net_sales: 0 }
}

function updateBreakdown(
  rows: SalesBreakdownRow[],
  label: string,
  delta: { orderCount?: number; quantity?: number; grossSales?: number; netSales?: number },
  sortKey: 'net_sales' | 'gross_sales' | 'order_count',
) {
  if (!label) {
    return rows
  }

  const index = rows.findIndex((row) => row.label === label)
  const current = index >= 0 ? rows[index] : createEmptyBreakdown(label)
  const nextRow: SalesBreakdownRow = {
    ...current,
    order_count: current.order_count + (delta.orderCount ?? 0),
    quantity: round(Number(current.quantity ?? 0) + (delta.quantity ?? 0), 3),
    gross_sales: round(Number(current.gross_sales ?? 0) + (delta.grossSales ?? 0)),
    net_sales: round(current.net_sales + (delta.netSales ?? 0)),
  }

  const nextRows = index >= 0
    ? rows.map((row, rowIndex) => (rowIndex === index ? nextRow : row))
    : [...rows, nextRow]

  return [...nextRows]
    .sort((left, right) => Number(right[sortKey] ?? 0) - Number(left[sortKey] ?? 0))
    .slice(0, 8)
}

function updateSalesWorkspace(salesWorkspace: SalesWorkspace, entry: JournalEntry, runtime: RealtimeMetadata) {
  if (entry.ontology_event_type !== 'sale') {
    return salesWorkspace
  }

  const saleKey = entry.sale_id || entry.order_id
  if (!saleKey) {
    return salesWorkspace
  }

  const sales = [...salesWorkspace.sales]
  const saleIndex = sales.findIndex((sale) => sale.sale_id === saleKey || sale.order_id === entry.order_id)
  const existingSale = saleIndex >= 0 ? sales[saleIndex] : null
  const productKey = entry.product_name || entry.product_id || 'unknown-product'
  const customerKey = entry.customer_email || entry.customer_id || saleKey
  const saleProducts = runtime.saleProducts[saleKey] ?? {}
  const isNewSale = !existingSale
  const isNewProduct = !saleProducts[productKey]

  saleProducts[productKey] = true
  runtime.saleProducts[saleKey] = saleProducts

  const nextSale = {
    sale_id: existingSale?.sale_id || saleKey,
    order_id: existingSale?.order_id || entry.order_id,
    occurred_at: existingSale?.occurred_at && existingSale.occurred_at > entry.occurred_at ? existingSale.occurred_at : entry.occurred_at,
    customer_id: existingSale?.customer_id || entry.customer_id,
    customer_name: existingSale?.customer_name || entry.customer_name,
    customer_cpf: existingSale?.customer_cpf || entry.customer_cpf,
    customer_email: existingSale?.customer_email || entry.customer_email,
    customer_segment: existingSale?.customer_segment || entry.customer_segment,
    channel: existingSale?.channel || entry.channel,
    channel_name: existingSale?.channel_name || entry.channel_name,
    payment_method: existingSale?.payment_method || entry.payment_method,
    payment_installments: Math.max(existingSale?.payment_installments ?? 0, entry.payment_installments ?? 0),
    order_status: existingSale?.order_status || entry.order_status,
    order_origin: existingSale?.order_origin || entry.order_origin,
    coupon_code: existingSale?.coupon_code || entry.coupon_code,
    device_type: existingSale?.device_type || entry.device_type,
    sales_region: existingSale?.sales_region || entry.sales_region,
    freight_service: existingSale?.freight_service || entry.freight_service,
    lead_product: existingSale?.lead_product || entry.product_name || entry.product_id,
    product_mix: isNewSale ? 1 : existingSale!.product_mix + (isNewProduct ? 1 : 0),
    cart_items_count: Math.max(existingSale?.cart_items_count ?? 0, entry.cart_items_count ?? 0),
    quantity: existingSale?.quantity ?? 0,
    gross_amount: existingSale?.gross_amount ?? 0,
    net_amount: existingSale?.net_amount ?? 0,
    cart_discount: Math.max(existingSale?.cart_discount ?? 0, entry.cart_discount ?? 0),
    tax_amount: existingSale?.tax_amount ?? 0,
    marketplace_fee_amount: existingSale?.marketplace_fee_amount ?? 0,
    cmv: existingSale?.cmv ?? 0,
  }

  let grossSalesDelta = 0
  let netSalesDelta = 0
  let grossMarginDelta = 0
  let unitsSoldDelta = 0

  switch (entry.account_role) {
    case 'revenue':
      grossSalesDelta = round(entry.unit_price * entry.quantity)
      netSalesDelta = round(entry.amount)
      grossMarginDelta = round(grossMarginDelta + netSalesDelta)
      unitsSoldDelta = round(entry.quantity, 3)
      nextSale.quantity = round(nextSale.quantity + entry.quantity, 3)
      nextSale.gross_amount = round(nextSale.gross_amount + grossSalesDelta)
      nextSale.net_amount = round(nextSale.net_amount + netSalesDelta)
      break
    case 'marketplace_fees':
      nextSale.marketplace_fee_amount = round(nextSale.marketplace_fee_amount + entry.amount)
      break
    case 'tax_payable':
      nextSale.tax_amount = round(nextSale.tax_amount + entry.amount)
      break
    case 'cogs':
      nextSale.cmv = round(nextSale.cmv + entry.amount)
      grossMarginDelta = round(grossMarginDelta - entry.amount)
      break
    default:
      break
  }

  if (isNewSale) {
    sales.unshift(nextSale)
  } else {
    sales[saleIndex] = nextSale
  }

  sales.sort((left, right) => right.occurred_at.localeCompare(left.occurred_at))

  const nextOrderCount = salesWorkspace.kpis.order_count + (isNewSale && entry.account_role === 'revenue' ? 1 : 0)
  let nextUniqueCustomers = salesWorkspace.kpis.unique_customers
  if (isNewSale && entry.account_role === 'revenue' && !runtime.customerKeys[customerKey]) {
    runtime.customerKeys[customerKey] = true
    nextUniqueCustomers += 1
  }

  const nextGrossSales = round(salesWorkspace.kpis.gross_sales + grossSalesDelta)
  const nextNetSales = round(salesWorkspace.kpis.net_sales + netSalesDelta)
  const nextGrossMargin = round(salesWorkspace.kpis.gross_margin + grossMarginDelta)
  const nextUnitsSold = round(salesWorkspace.kpis.units_sold + unitsSoldDelta, 3)
  const nextAverageTicket = nextOrderCount > 0 ? round(nextNetSales / nextOrderCount) : 0
  const nextAvgItemsPerOrder = isNewSale && entry.account_role === 'revenue'
    ? round(((salesWorkspace.kpis.avg_items_per_order * Math.max(nextOrderCount - 1, 0)) + entry.cart_items_count) / nextOrderCount, 2)
    : salesWorkspace.kpis.avg_items_per_order

  const orderDelta = isNewSale && entry.account_role === 'revenue' ? 1 : 0
  const nextByChannel = entry.account_role === 'revenue'
    ? updateBreakdown(salesWorkspace.by_channel, entry.channel_name || entry.channel, {
      orderCount: orderDelta,
      quantity: unitsSoldDelta,
      grossSales: grossSalesDelta,
      netSales: netSalesDelta,
    }, 'net_sales')
    : salesWorkspace.by_channel
  const nextByProduct = entry.account_role === 'revenue'
    ? updateBreakdown(salesWorkspace.by_product, entry.product_name || entry.product_id, {
      orderCount: isNewProduct ? 1 : 0,
      quantity: unitsSoldDelta,
      grossSales: grossSalesDelta,
      netSales: netSalesDelta,
    }, 'net_sales')
    : salesWorkspace.by_product
  const nextByStatus = entry.account_role === 'revenue' && entry.order_status
    ? updateBreakdown(salesWorkspace.by_status, entry.order_status, { orderCount: orderDelta, netSales: netSalesDelta }, 'order_count')
    : salesWorkspace.by_status
  const nextByPayment = entry.account_role === 'revenue'
    ? updateBreakdown(salesWorkspace.by_payment, entry.payment_method || 'nao_informado', {
      orderCount: orderDelta,
      quantity: unitsSoldDelta,
      grossSales: grossSalesDelta,
      netSales: netSalesDelta,
    }, 'net_sales')
    : salesWorkspace.by_payment

  return {
    ...salesWorkspace,
    sales: sales.slice(0, 40),
    kpis: {
      order_count: nextOrderCount,
      unique_customers: nextUniqueCustomers,
      gross_sales: nextGrossSales,
      net_sales: nextNetSales,
      gross_margin: nextGrossMargin,
      units_sold: nextUnitsSold,
      average_ticket: nextAverageTicket,
      avg_items_per_order: nextAvgItemsPerOrder,
    },
    by_channel: nextByChannel,
    by_product: nextByProduct,
    by_status: nextByStatus,
    by_payment: nextByPayment,
  }
}

export function productAudit(products: ProductCatalogRow[]) {
  const opening = products.reduce((total, item) => total + Number(item.opening_stock_quantity ?? 0), 0)
  const current = products.reduce((total, item) => total + Number(item.current_stock_quantity ?? 0), 0)
  const sold = products.reduce((total, item) => total + Number(item.net_sold_quantity ?? 0), 0)
  const returned = products.reduce((total, item) => total + Number(item.returned_quantity ?? 0), 0)
  const restock = products.filter((item) => item.needs_restock).length
  const suggestedPurchase = products.reduce((total, item) => total + Number(item.suggested_purchase_quantity ?? 0), 0)
  const netRevenue = products.reduce((total, item) => total + Number(item.net_revenue_amount ?? 0), 0)
  const grossProfit = products.reduce((total, item) => total + Number(item.gross_profit_amount ?? 0), 0)
  const netProfit = products.reduce((total, item) => total + Number(item.net_profit_amount ?? 0), 0)
  const grossSold = products.reduce((total, item) => total + Number(item.sold_quantity ?? 0), 0)
  return {
    opening,
    current,
    sold,
    returned,
    restock,
    suggestedPurchase,
    netRevenue,
    grossProfit,
    netProfit,
    returnRatePct: percentage(returned, grossSold, 2),
    grossMarginPct: percentage(grossProfit, netRevenue, 2),
    netMarginPct: percentage(netProfit, netRevenue, 2),
  }
}