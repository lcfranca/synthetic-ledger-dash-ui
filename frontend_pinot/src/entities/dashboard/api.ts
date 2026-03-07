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
  warehouse_id: string
  warehouse_name: string
  channel: string
  channel_name: string
  entry_category: string
  order_id: string
  source_payload_hash: string
  occurred_at: string
  ingested_at: string
  revision: number
}

export type EntryFilters = {
  as_of?: string
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
}

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
  returned_quantity: number
  average_purchase_price: number
  average_sale_price: number
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

function toQuery(params: EntryFilters = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value))
    }
  })
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

export async function fetchMasterDataOverview(): Promise<MasterDataOverview> {
  return getJson('/api/v1/master-data/overview', 'Falha ao obter visão de dados mestres')
}

export async function fetchWorkspaceSnapshot(): Promise<WorkspaceSnapshot> {
  return getJson('/api/v1/dashboard/workspace', 'Falha ao obter workspace em tempo real')
}

export async function fetchAccountCatalog(): Promise<{ accounts: AccountCatalogRow[]; count: number; backend: string }> {
  return getJson('/api/v1/dashboard/accounts-catalog', 'Falha ao obter catálogo de contas')
}

export async function fetchProductCatalog(): Promise<{ products: ProductCatalogRow[]; count: number; backend: string }> {
  return getJson('/api/v1/dashboard/products-catalog', 'Falha ao obter catálogo de produtos')
}
