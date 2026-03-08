import type { DashboardSummary, EntryFilters, WorkspaceSnapshot } from '../../entities/dashboard/api'
import { shortTs } from '../../shared/lib/time'

type Props = {
  currentFeed: string
  filters?: EntryFilters
  workspace?: WorkspaceSnapshot
  summary?: DashboardSummary
}

function rangeLabel(filters?: EntryFilters) {
  if (filters?.start_at || filters?.end_at) {
    return `${shortTs(filters.start_at)} -> ${shortTs(filters.end_at)}`
  }
  if (filters?.as_of) {
    return `As Of ${shortTs(filters.as_of)}`
  }
  return 'Janela aberta em tempo real'
}

export default function DashboardHeader({ currentFeed, filters, workspace, summary }: Props) {
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
        <div>Janela: {rangeLabel(filters)}</div>
      </div>
    </header>
  )
}