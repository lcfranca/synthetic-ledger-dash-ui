import type {
  DashboardEnvelope,
  EntryCreatedEnvelope,
  ProductCatalogRow,
  RealtimeEnvelope,
  JournalEntry,
  WorkspaceSnapshot,
} from '../api'

export function isEntryCreatedEnvelope(payload: RealtimeEnvelope | WorkspaceSnapshot): payload is EntryCreatedEnvelope {
  return 'event_type' in payload && payload.event_type === 'entry.created'
}

export function isDashboardEnvelope(payload: RealtimeEnvelope | WorkspaceSnapshot): payload is DashboardEnvelope {
  return 'event_type' in payload && payload.event_type === 'dashboard.snapshot'
}

export function feedLabel(socketStatus: string, liveWorkspace: WorkspaceSnapshot | null, hasActiveFilters: boolean) {
  if (hasActiveFilters) {
    return 'Snapshot filtrado'
  }
  if (socketStatus === 'open' && liveWorkspace) {
    return 'Push gateway + delta Kafka'
  }
  if (socketStatus === 'connecting') {
    return 'Conectando ao gateway push'
  }
  if (socketStatus === 'error') {
    return 'Fallback por snapshot bootstrap'
  }
  return 'Bootstrap por polling'
}

export function withRealtimeEntry(workspace: WorkspaceSnapshot | null, entry: JournalEntry, backend: string, ts: string) {
  if (!workspace) {
    return workspace
  }
  const nextEntries = [entry, ...workspace.entries.filter((item) => item.entry_id !== entry.entry_id)].slice(0, 30)
  return {
    ...workspace,
    backend,
    timestamp: ts,
    entries: nextEntries,
    summary: {
      ...workspace.summary,
      backend,
      timestamp: ts,
      entries: nextEntries,
    },
  }
}

export function productAudit(products: ProductCatalogRow[]) {
  const opening = products.reduce((total, item) => total + Number(item.opening_stock_quantity ?? 0), 0)
  const current = products.reduce((total, item) => total + Number(item.current_stock_quantity ?? 0), 0)
  const sold = products.reduce((total, item) => total + Number(item.sold_quantity ?? 0), 0)
  const returned = products.reduce((total, item) => total + Number(item.returned_quantity ?? 0), 0)
  const restock = products.filter((item) => item.needs_restock).length
  const suggestedPurchase = products.reduce((total, item) => total + Number(item.suggested_purchase_quantity ?? 0), 0)
  return { opening, current, sold, returned, restock, suggestedPurchase }
}