export type DashboardSummary = {
  timestamp: string
  as_of: string
  balance_sheet: {
    assets: { cash: number; bank_accounts: number; recoverable_tax: number; inventory: number; total: number }
    liabilities: { accounts_payable: number; tax_payable: number; total: number }
    equity: { current_earnings: number }
    total_liabilities_and_equity: number
    difference: number
  }
  income_statement: {
    revenue: number
    returns: number
    net_revenue: number
    marketplace_fees: number
    freight_out: number
    bank_fees: number
    other_expenses: number
    operating_expenses: number
    expenses: number
    net_income: number
    cmv: number
    gross_profit: number
    return_rate_pct?: number | null
    gross_margin_pct?: number | null
    net_margin_pct?: number | null
    expense_ratio_pct?: number | null
  }
  entries: JournalEntry[]
  filters?: EntryFilters
  backend?: string
}

export type JournalEntry = {
  entry_id: string
  event_id: string
  trace_id: string
  entry_side: 'debit' | 'credit'
  account_code: string
  account_name: string
  account_role: string
  amount: number
  signed_amount: number
  quantity: number
  unit_price: number
  currency: string
  ontology_event_type: string
  ontology_description: string
  ontology_source: string
  product_id: string
  product_name: string
  product_category: string
  product_brand: string
  supplier_id: string | null
  supplier_name: string | null
  customer_id: string | null
  customer_name: string | null
  customer_cpf: string | null
  customer_email: string | null
  customer_segment: string | null
  warehouse_id: string
  warehouse_name: string
  channel: string
  channel_name: string
  entry_category: string
  sale_id: string | null
  order_id: string
  order_status: string | null
  order_origin: string | null
  payment_method: string | null
  payment_installments: number
  coupon_code: string | null
  device_type: string | null
  sales_region: string | null
  freight_service: string | null
  cart_items_count: number
  cart_quantity: number
  cart_gross_amount: number
  cart_discount: number
  cart_net_amount: number
  sale_line_index: number
  source_payload_hash: string
  occurred_at: string
  ingested_at: string
  revision: number
}

export type EntryFilters = {
  as_of?: string
  start_at?: string
  end_at?: string
  product_name?: string
  product_category?: string
  supplier_name?: string
  event_type?: string
  entry_category?: string
  account_code?: string
  warehouse_id?: string
  entry_side?: 'debit' | 'credit' | ''
  ontology_source?: string
  channel?: string
  customer_name?: string
  customer_cpf?: string
  customer_email?: string
  customer_segment?: string
  sale_id?: string
  order_id?: string
  order_status?: string
  payment_method?: string
}

export type QueueFilters = Pick<
  EntryFilters,
  | 'as_of'
  | 'start_at'
  | 'end_at'
  | 'product_name'
  | 'product_category'
  | 'supplier_name'
  | 'event_type'
  | 'entry_category'
  | 'account_code'
  | 'warehouse_id'
  | 'entry_side'
  | 'ontology_source'
  | 'channel'
>

export type SalesFilters = Pick<
  EntryFilters,
  | 'as_of'
  | 'start_at'
  | 'end_at'
  | 'product_name'
  | 'product_category'
  | 'channel'
  | 'customer_name'
  | 'customer_cpf'
  | 'customer_email'
  | 'customer_segment'
  | 'sale_id'
  | 'order_id'
  | 'order_status'
  | 'payment_method'
>

export type FilterOptions = {
  product_names: string[]
  product_categories: string[]
  supplier_names: string[]
  event_types: string[]
  entry_categories: string[]
  account_codes: string[]
  warehouse_ids: string[]
  channels: string[]
  entry_sides: string[]
  ontology_sources: string[]
  payment_methods: string[]
  order_statuses: string[]
  customer_segments: string[]
}

export type SaleRecord = {
  sale_id: string
  order_id: string
  occurred_at: string
  customer_id: string | null
  customer_name: string | null
  customer_cpf: string | null
  customer_email: string | null
  customer_segment: string | null
  channel: string
  channel_name: string
  payment_method: string | null
  payment_installments: number
  order_status: string | null
  order_origin: string | null
  coupon_code: string | null
  device_type: string | null
  sales_region: string | null
  freight_service: string | null
  lead_product: string | null
  product_mix: number
  cart_items_count: number
  quantity: number
  gross_amount: number
  net_amount: number
  cart_discount: number
  tax_amount: number
  marketplace_fee_amount: number
  cmv: number
}

export type SalesBreakdownRow = {
  label: string
  order_count: number
  quantity?: number
  gross_sales?: number
  net_sales: number
}

export type SalesWorkspace = {
  sales: SaleRecord[]
  kpis: {
    order_count: number
    unique_customers: number
    gross_sales: number
    net_sales: number
    units_sold: number
    average_ticket: number
    avg_items_per_order: number
  }
  by_channel: SalesBreakdownRow[]
  by_product: SalesBreakdownRow[]
  by_status: SalesBreakdownRow[]
  data_mode?: 'full' | 'pinot_order_fallback'
  data_warning?: string | null
  missing_dimensions?: string[]
}

export type MasterDataCompany = {
  company_id: string
  tenant_id: string
  legal_name: string
  trade_name: string
  description: string
  segment: string
  currency: string
  headquarters_city: string
  headquarters_state: string
}

export type MasterDataAccount = {
  account_code: string
  account_name: string
  account_role: string
  statement_section: string
  account_nature: string
  normal_side?: string
  entry_category?: string
  documentation: string
  usage_notes: string
  financial_statement_group: string
}

export type MasterDataProduct = {
  product_id: string
  product_name: string
  product_category: string
  product_brand: string
  preferred_supplier_id: string
  supplier_name: string
  default_warehouse_id: string
  warehouse_name: string
  base_cost: number
  base_price: number
  tax_rate: number
  reorder_point: number
  target_stock: number
  demand_weight: number
  initial_stock: Record<string, number>
  channel_ids: string[]
  channel_names?: string[]
}

export type MasterDataChannel = {
  channel_id: string
  channel_name: string
  commission_rate: number
  settlement_days: number
  price_multiplier: number
  demand_weight: number
  channel_type: string
}

export type MasterDataOverview = {
  company: MasterDataCompany
  products: MasterDataProduct[]
  accounts: MasterDataAccount[]
  channels: MasterDataChannel[]
  stats: {
    product_count: number
    channel_count: number
    account_count: number
    supplier_count: number
    warehouse_count: number
    opening_inventory_units: number
    opening_inventory_positions: number
    account_sections: Record<string, number>
  }
}

export type AccountCatalogRow = MasterDataAccount & {
  current_balance: number
  entry_count: number
}

export type ProductCatalogRow = MasterDataProduct & {
  registered_channels: string[]
  opening_stock_quantity?: number
  current_stock_quantity: number
  sold_quantity: number
  net_sold_quantity: number
  returned_quantity: number
  average_purchase_price: number
  average_sale_price: number
  revenue_amount: number
  return_amount: number
  net_revenue_amount: number
  cogs_amount: number
  selling_expenses_amount: number
  gross_profit_amount: number
  net_profit_amount: number
  return_rate_pct?: number | null
  gross_margin_pct?: number | null
  net_margin_pct?: number | null
  daily_demand_units: number
  coverage_days: number | null
  suggested_purchase_quantity: number
  suggested_purchase_supplier_name: string
  purchase_recommendation: string
  needs_restock: boolean
}

export type WorkspaceSnapshot = {
  timestamp: string
  summary: DashboardSummary
  entries: JournalEntry[]
  master_data: MasterDataOverview
  account_catalog: AccountCatalogRow[]
  product_catalog: ProductCatalogRow[]
  sales_workspace: SalesWorkspace
  backend?: string
}

export type DashboardEnvelope = {
  event_id: string
  event_type: string
  version: string
  backend: string
  ts: string
  payload: WorkspaceSnapshot
}

export type EntryCreatedEnvelope = {
  event_id: string
  event_type: 'entry.created'
  version: string
  backend: string
  ts: string
  payload: JournalEntry
}

export type RealtimeEnvelope = DashboardEnvelope | EntryCreatedEnvelope

export function buildFilterSearchParams(params: EntryFilters = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value))
    }
  })
  return search
}

function toQuery(params: EntryFilters = {}) {
  const search = buildFilterSearchParams(params)
  const query = search.toString()
  return query ? `?${query}` : ''
}

async function getJson<T>(path: string, errorMessage: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(errorMessage)
  }
  return response.json() as Promise<T>
}

export async function fetchSummary(filters: EntryFilters = {}): Promise<DashboardSummary> {
  return getJson(`/api/v1/dashboard/summary${toQuery(filters)}`, 'Falha ao obter resumo')
}

export async function fetchFilterOptions(): Promise<FilterOptions> {
  return getJson('/api/v1/dashboard/filter-options', 'Falha ao obter opções de filtro')
}

export async function fetchFilterSearch(field: string, query: string): Promise<string[]> {
  const search = new URLSearchParams({ field, query })
  const payload = await getJson<{ matches: string[] }>(`/api/v1/dashboard/filter-search?${search.toString()}`, 'Falha ao buscar filtro')
  return payload.matches ?? []
}

export async function fetchMasterDataOverview(): Promise<MasterDataOverview> {
  return getJson('/api/v1/master-data/overview', 'Falha ao obter visão de dados mestres')
}

export async function fetchWorkspaceSnapshot(filters: EntryFilters = {}): Promise<WorkspaceSnapshot> {
  return getJson(`/api/v1/dashboard/workspace${toQuery(filters)}`, 'Falha ao obter workspace em tempo real')
}

export async function fetchAccountCatalog(): Promise<{ accounts: AccountCatalogRow[]; count: number; backend: string }> {
  return getJson('/api/v1/dashboard/accounts-catalog', 'Falha ao obter catálogo de contas')
}

export async function fetchProductCatalog(): Promise<{ products: ProductCatalogRow[]; count: number; backend: string }> {
  return getJson('/api/v1/dashboard/products-catalog', 'Falha ao obter catálogo de produtos')
}
