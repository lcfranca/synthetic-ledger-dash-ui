import type { DashboardSummary, EntryFilters, WorkspaceSnapshot } from '../../entities/dashboard/api'
import type { ViewId } from '../../shared/config/dashboardViews'
import { shortTs } from '../../shared/lib/time'

type Props = {
  activeView?: ViewId
  currentFeed: string
  filters?: EntryFilters
  workspace?: WorkspaceSnapshot
  summary?: DashboardSummary
}

const headerByView: Record<ViewId, { eyebrow: string; title: string; subline: string }> = {
  queue: {
    eyebrow: 'Escrituracao operacional',
    title: 'Movimento contabil consolidado',
    subline: 'Lancamentos, documentos, contas e trilhas de origem em uma leitura continua.',
  },
  sales: {
    eyebrow: 'Receita comercial',
    title: 'Operacao comercial consolidada',
    subline: 'Pedidos, canais, compradores, volume e margem em leitura propria da area comercial.',
  },
  accounting: {
    eyebrow: 'Posicao financeira',
    title: 'Balanco e resultado consolidados',
    subline: 'Ativos, passivos e resultado corrente com fechamento continuo da operacao.',
  },
  accounts: {
    eyebrow: 'Plano contabil',
    title: 'Inventario corporativo de contas',
    subline: 'Papeis, grupos, saldos e orientacao de uso do plano contabil.',
  },
  products: {
    eyebrow: 'Malha de estoque',
    title: 'Catalogo de produtos e cobertura',
    subline: 'Demanda, cobertura, giro e reposicao em leitura unica de abastecimento.',
  },
}

function rangeLabel(filters?: EntryFilters) {
  if (filters?.start_at || filters?.end_at) {
    return `${shortTs(filters.start_at)} -> ${shortTs(filters.end_at)}`
  }
  if (filters?.as_of) {
    return `Posicao em ${shortTs(filters.as_of)}`
  }
  return 'Janela corrente'
}

export default function DashboardHeader({ activeView = 'queue', currentFeed, filters, workspace, summary }: Props) {
  const header = headerByView[activeView]

  return (
    <header className="panel shell-header frame-panel hero-header cinematic-panel">
      <div>
        <div className="meta-label">{header.eyebrow}</div>
        <h2>{header.title}</h2>
        <div className="hero-subline">{header.subline}</div>
      </div>
      <div className="header-time header-cluster">
        <div className="status-row"><span className="status-dot live" />{currentFeed}</div>
        <div>Atualizacao: {shortTs(workspace?.timestamp ?? summary?.timestamp)}</div>
        <div>Janela: {rangeLabel(filters)}</div>
      </div>
    </header>
  )
}