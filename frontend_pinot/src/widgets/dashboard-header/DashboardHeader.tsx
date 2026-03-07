import type { DashboardSummary, WorkspaceSnapshot } from '../../entities/dashboard/api'
import { shortTs } from '../../shared/lib/time'

type Props = {
  currentFeed: string
  workspace?: WorkspaceSnapshot
  summary?: DashboardSummary
}

export default function DashboardHeader({ currentFeed, workspace, summary }: Props) {
  return (
    <header className="panel shell-header frame-panel hero-header cinematic-panel">
      <div>
        <div className="meta-label">Templates / simple workflow template</div>
        <h2>Painel espelhado entre stacks</h2>
        <div className="hero-subline">Branco de alto contraste, acento laranja, contorno seco e comportamento push-ready.</div>
      </div>
      <div className="header-time header-cluster">
        <div className="status-row"><span className="status-dot live" />{currentFeed}</div>
        <div>Atualizacao: {shortTs(workspace?.timestamp ?? summary?.timestamp)}</div>
        <div>As Of: {shortTs(summary?.as_of)}</div>
      </div>
    </header>
  )
}