import type { DashboardSummary, MasterDataOverview } from '../../entities/dashboard/api'
import { money } from '../../shared/lib/format'

type Props = {
  summary?: DashboardSummary
  overview?: MasterDataOverview
  backend: string
  feedMode: string
}

export default function ShellMetrics({ summary, overview, backend, feedMode }: Props) {
  return (
    <div className="metric-strip hero-strip">
      <article className="metric-card accent-card panel-surface">
        <div className="metric-topline">
          <span className="metric-label">Sync engine</span>
          <span className="status-dot live" />
        </div>
        <div className="metric-value small-text">{feedMode}</div>
        <div className="metric-helper">Stack ativo: {backend}</div>
      </article>
      <article className="metric-card panel-surface">
        <div className="metric-label">Patrimonio liquido</div>
        <div className="metric-value">{summary ? money(summary.balance_sheet.equity.current_earnings) : '-'}</div>
        <div className="metric-helper">Diferenca BP: {summary ? money(summary.balance_sheet.difference) : '-'}</div>
      </article>
      <article className="metric-card panel-surface">
        <div className="metric-label">Receita liquida</div>
        <div className="metric-value">{summary ? money(summary.income_statement.net_revenue) : '-'}</div>
        <div className="metric-helper">CMV: {summary ? money(summary.income_statement.cmv) : '-'}</div>
      </article>
      <article className="metric-card panel-surface">
        <div className="metric-label">Universo operacional</div>
        <div className="metric-value">{overview?.stats.product_count ?? 0}</div>
        <div className="metric-helper">Canais {overview?.stats.channel_count ?? 0} · Contas {overview?.stats.account_count ?? 0}</div>
      </article>
    </div>
  )
}