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
  source_payload_hash: string
  occurred_at: string
  ingested_at: string
  revision: number
}

export async function fetchSummary(): Promise<DashboardSummary> {
  const response = await fetch('/api/v1/dashboard/summary')
  if (!response.ok) throw new Error('Falha ao obter resumo')
  return response.json()
}
