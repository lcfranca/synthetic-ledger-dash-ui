import type { DashboardSummary } from '../../entities/dashboard/api'
import { money, percent } from '../../shared/lib/format'

type Props = {
  summary?: DashboardSummary | null
}

export default function KpiPanel({ summary }: Props) {
  const bpClosed = summary ? Math.abs(summary.balance_sheet.difference) <= 0.11 : false

  return (
    <section className="panel">
      <h2>KPIs Contábeis</h2>
      <div className="metric-grid">
        <article className="metric-card">
          <div className="metric-label">Caixa</div>
          <div className="metric-value">{summary ? money(summary.balance_sheet.assets.cash) : '-'}</div>
        </article>
        <article className="metric-card">
          <div className="metric-label">Estoque</div>
          <div className="metric-value">{summary ? money(summary.balance_sheet.assets.inventory) : '-'}</div>
        </article>
        <article className="metric-card metric-card--accent">
          <div className="metric-label">Receita liquida</div>
          <div className="metric-value">{summary ? money(summary.income_statement.net_revenue) : '-'}</div>
          <div className="metric-footnote">Devolucao {summary ? percent(summary.income_statement.return_rate_pct) : '-'}</div>
        </article>
        <article className="metric-card">
          <div className="metric-label">Margem Bruta</div>
          <div className="metric-value">{summary ? percent(summary.income_statement.gross_margin_pct) : '-'}</div>
          <div className="metric-footnote">Lucro bruto {summary ? money(summary.income_statement.gross_profit) : '-'}</div>
        </article>
        <article className="metric-card">
          <div className="metric-label">Margem Liquida</div>
          <div className="metric-value">{summary ? percent(summary.income_statement.net_margin_pct) : '-'}</div>
          <div className="metric-footnote">Resultado {summary ? money(summary.income_statement.net_income) : '-'}</div>
        </article>
        <article className={`metric-card ${bpClosed ? 'metric-card--balanced' : 'metric-card--warning'}`}>
          <div className="metric-label">Fechamento do BP</div>
          <div className="metric-value">{summary ? (bpClosed ? 'Fechado' : 'Divergente') : '-'}</div>
          <div className="metric-footnote">
            {summary ? `${money(summary.balance_sheet.assets.total)} vs ${money(summary.balance_sheet.total_liabilities_and_equity)}` : '-'}
          </div>
          <div className="metric-footnote">
            {summary ? `Diferença ${money(summary.balance_sheet.difference)}` : '-'}
          </div>
        </article>
      </div>
    </section>
  )
}
