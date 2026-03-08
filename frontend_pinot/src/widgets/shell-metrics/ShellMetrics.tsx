import type { DashboardSummary, MasterDataOverview } from '../../entities/dashboard/api'
import { money } from '../../shared/lib/format'

type Props = {
  summary?: DashboardSummary
  overview?: MasterDataOverview
  backend: string
  feedMode: string
  isRealtimePaused: boolean
  pendingRealtimeEvents: number
  onToggleRealtime: () => void
}

export default function ShellMetrics({ summary, overview, backend, feedMode, isRealtimePaused, pendingRealtimeEvents, onToggleRealtime }: Props) {
  const equityTotal = summary?.balance_sheet.equity.total ?? summary?.balance_sheet.equity.current_earnings

  return (
    <div className="metric-strip hero-strip">
      <button type="button" className="metric-card accent-card panel-surface metric-toggle-card" onClick={onToggleRealtime}>
        <div className="metric-topline">
          <span className="metric-label">Ritmo operacional</span>
          <span className="status-dot live" />
        </div>
        <div className="metric-value small-text">{isRealtimePaused ? 'Congelado' : 'Continuo'}</div>
        <div className="metric-helper">{feedMode}</div>
        <div className="metric-helper">Fonte de dados: {backend.toUpperCase()}{isRealtimePaused && pendingRealtimeEvents > 0 ? ` · fila ${pendingRealtimeEvents}` : ''}</div>
      </button>
      <article className="metric-card panel-surface">
        <div className="metric-label">Patrimonio liquido</div>
        <div className="metric-value">{summary ? money(equityTotal ?? 0) : '-'}</div>
        <div className="metric-helper">Resultado corrente: {summary ? money(summary.balance_sheet.equity.current_earnings) : '-'}</div>
      </article>
      <article className="metric-card panel-surface">
        <div className="metric-label">Receita liquida</div>
        <div className="metric-value">{summary ? money(summary.income_statement.net_revenue) : '-'}</div>
        <div className="metric-helper">CMV {summary ? money(summary.income_statement.cmv) : '-'} · Juros {summary ? money(summary.income_statement.financial_expenses) : '-'}</div>
      </article>
      <article className="metric-card panel-surface">
        <div className="metric-label">Universo operacional</div>
        <div className="metric-value">{overview?.stats.product_count ?? 0}</div>
        <div className="metric-helper">Canais {overview?.stats.channel_count ?? 0} · Contas {overview?.stats.account_count ?? 0}</div>
      </article>
    </div>
  )
}