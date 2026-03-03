export type DashboardSummary = {
  timestamp: string
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
}

export async function fetchSummary(): Promise<DashboardSummary> {
  const response = await fetch('/api/v1/dashboard/summary')
  if (!response.ok) throw new Error('Falha ao obter resumo')
  return response.json()
}
