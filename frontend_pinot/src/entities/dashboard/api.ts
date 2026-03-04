export type DashboardSummary = {
  timestamp: string
  as_of: string
  balance_sheet: {
    assets: { cash: number; inventory: number }
    liabilities: { accounts_payable: number }
  }
  income_statement: {
    revenue: number
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
  amount: number
  signed_amount: number
  currency: string
  ontology_event_type: string
  ontology_description: string
  ontology_source: string
  product_id: string
  supplier_id: string | null
  customer_id: string | null
  warehouse_id: string
  channel: string
  entry_category: string
  source_payload_hash: string
  occurred_at: string
  ingested_at: string
  revision: number
}

export type EntryFilters = {
  as_of?: string
  product_id?: string
  supplier_id?: string
  event_type?: string
  entry_category?: string
  account_code?: string
  warehouse_id?: string
  entry_side?: 'debit' | 'credit' | ''
  ontology_source?: string
  channel?: string
}

export type FilterOptions = {
  product_ids: string[]
  supplier_ids: string[]
  event_types: string[]
  entry_categories: string[]
  account_codes: string[]
  warehouse_ids: string[]
  channels: string[]
  entry_sides: string[]
  ontology_sources: string[]
}

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

export async function fetchSummary(filters: EntryFilters = {}): Promise<DashboardSummary> {
  const response = await fetch(`/api/v1/dashboard/summary${toQuery(filters)}`)
  if (!response.ok) throw new Error('Falha ao obter resumo')
  return response.json()
}

export async function fetchFilterOptions(): Promise<FilterOptions> {
  const response = await fetch('/api/v1/dashboard/filter-options')
  if (!response.ok) throw new Error('Falha ao obter opções de filtro')
  return response.json()
}
