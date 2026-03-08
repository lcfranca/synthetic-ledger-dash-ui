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
        <div className="meta-label">Tantalex</div>
        <h1>Tantalex</h1>
        <p className="rail-copy">Operacao industrial, leitura densa e separacao rigida entre frente comercial, estoque, contas e resultado.</p>
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
        <div className="status-row"><span className="status-dot live" />Fonte de dados</div>
        <strong>{backend.toUpperCase()}</strong>
        <div className="status-row">Janela de leitura</div>
        <strong>{shortTs(workspace?.timestamp ?? summary?.timestamp)}</strong>
        <div className="status-row">Area ativa</div>
        <strong>{activeViewMeta.label}</strong>
      </div>
    </aside>
  )
}