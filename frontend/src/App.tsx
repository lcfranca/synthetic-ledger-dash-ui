import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchSummary, type DashboardSummary, type JournalEntry } from './api'

function money(value: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
}

function sideLabel(side: JournalEntry['entry_side']) {
  return side === 'debit' ? 'Débito' : 'Crédito'
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
      <p>As Of (Time-travel): {summary?.as_of ?? '-'}</p>

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

      <section>
        <h2>Fila de Lançamentos (Débito/Crédito) — Tempo Real</h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 1200 }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Ocorrido em</th>
                <th style={{ textAlign: 'left' }}>Tipo</th>
                <th style={{ textAlign: 'left' }}>Conta</th>
                <th style={{ textAlign: 'left' }}>Valor</th>
                <th style={{ textAlign: 'left' }}>Origem Ontológica</th>
                <th style={{ textAlign: 'left' }}>Descrição Ontológica</th>
                <th style={{ textAlign: 'left' }}>Event ID</th>
                <th style={{ textAlign: 'left' }}>Trace ID</th>
                <th style={{ textAlign: 'left' }}>Hash</th>
              </tr>
            </thead>
            <tbody>
              {(summary?.entries ?? []).map((entry) => (
                <tr key={entry.entry_id}>
                  <td>{entry.occurred_at}</td>
                  <td>{sideLabel(entry.entry_side)}</td>
                  <td>{entry.account_code} - {entry.account_name}</td>
                  <td>{money(entry.amount)}</td>
                  <td>{entry.ontology_event_type} ({entry.ontology_source})</td>
                  <td>{entry.ontology_description}</td>
                  <td>{entry.event_id}</td>
                  <td>{entry.trace_id}</td>
                  <td>{entry.source_payload_hash.slice(0, 16)}...</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
