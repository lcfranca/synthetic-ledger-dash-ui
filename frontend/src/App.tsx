import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchSummary, type DashboardSummary } from './api'

function money(value: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
}

export default function App() {
  const { data } = useQuery({
    queryKey: ['summary'],
    queryFn: fetchSummary,
    refetchInterval: 5000
  })

  const [live, setLive] = useState<DashboardSummary | null>(null)

  useEffect(() => {
    const ws = new WebSocket(`${window.location.origin.replace('http', 'ws')}/ws/metrics`)
    ws.onmessage = (event) => setLive(JSON.parse(event.data))
    return () => ws.close()
  }, [])

  const summary = live ?? data

  return (
    <main style={{ fontFamily: 'Inter, system-ui, sans-serif', padding: 24 }}>
      <h1>Synthetic Ledger Dashboard</h1>
      <p>Atualização: {summary?.timestamp ?? '-'}</p>

      <section>
        <h2>BP (Balance Sheet)</h2>
        <p>Caixa: {summary ? money(summary.balance_sheet.assets.cash) : '-'}</p>
        <p>Estoque: {summary ? money(summary.balance_sheet.assets.inventory) : '-'}</p>
        <p>Contas a pagar: {summary ? money(summary.balance_sheet.liabilities.accounts_payable) : '-'}</p>
      </section>

      <section>
        <h2>DRE (Income Statement)</h2>
        <p>Receita: {summary ? money(summary.income_statement.revenue) : '-'}</p>
        <p>Despesas: {summary ? money(summary.income_statement.expenses) : '-'}</p>
        <p>CMV: {summary ? money(summary.income_statement.cmv) : '-'}</p>
        <p>Lucro líquido: {summary ? money(summary.income_statement.net_income) : '-'}</p>
      </section>
    </main>
  )
}
