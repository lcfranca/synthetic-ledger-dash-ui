import type { DashboardSummary, WorkspaceSnapshot } from '../../entities/dashboard/api'
import { dashboardViews, type ViewId } from '../../shared/config/dashboardViews'
import { shortTs } from '../../shared/lib/time'

type Props = {
  activeView: ViewId
  backend: string
  setActiveView: (view: ViewId) => void
  workspace?: WorkspaceSnapshot
  summary?: DashboardSummary
}

export default function SideRail({ activeView, backend, setActiveView, workspace, summary }: Props) {
  const activeViewMeta = dashboardViews.find((view) => view.id === activeView) ?? dashboardViews[0]

  return (
    <aside className="side-rail panel frame-panel">
      <div className="rail-head">
        <div className="meta-label">Synthetic ledger / command deck</div>
        <h1>Commerce block</h1>
        <p className="rail-copy">Blocos densos, linhas retas, tipografia industrial e operacao viva de vendas, estoque e contabilidade.</p>
      </div>

      <nav className="side-nav" aria-label="Dashboards">
        {dashboardViews.map((view) => (
          <button key={view.id} className={`nav-card ${activeView === view.id ? 'active' : ''}`} onClick={() => setActiveView(view.id)}>
            <span className="nav-code">/{view.code}</span>
            <span className="nav-eyebrow">{view.eyebrow}</span>
            <span className="nav-label">{view.label}</span>
          </button>
        ))}
      </nav>

      <div className="rail-status panel-surface">
        <div className="status-row"><span className="status-dot live" />Backend ativo</div>
        <strong>{backend}</strong>
        <div className="status-row">Janela de leitura</div>
        <strong>{shortTs(workspace?.timestamp ?? summary?.timestamp)}</strong>
        <div className="status-row">Vista selecionada</div>
        <strong>{activeViewMeta.label}</strong>
      </div>
    </aside>
  )
}