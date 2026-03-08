import { useQuery } from '@tanstack/react-query'
import {
  type EntryFilters,
  fetchFilterOptions,
  fetchSummary,
  fetchWorkspaceSnapshot,
} from '../../../entities/dashboard/api'
import { feedLabel } from '../../../entities/dashboard/lib/realtime'
import { useRealtimeDashboard } from '../../../features/subscribe-stream/model/useRealtimeDashboard'
import type { ViewId } from '../../../shared/config/dashboardViews'

type Params = {
  defaultBackend: string
  queryKeyPrefix: string
  filters: EntryFilters
  hasActiveFilters?: boolean
  viewId: ViewId
  isRealtimePaused?: boolean
}

export function useDashboardSession({ defaultBackend, queryKeyPrefix, filters, hasActiveFilters = false, viewId, isRealtimePaused = false }: Params) {
  const enableRealtime = true
  const realtimeMode = viewId === 'queue' ? 'mixed' : 'snapshot-only'
  const workspaceRefreshInterval = isRealtimePaused ? false : 180000

  const summaryQuery = useQuery({
    queryKey: [queryKeyPrefix, 'summary', filters],
    queryFn: () => fetchSummary(filters),
    refetchOnWindowFocus: false,
  })

  const filterOptionsQuery = useQuery({
    queryKey: [queryKeyPrefix, 'filter-options'],
    queryFn: fetchFilterOptions,
    staleTime: 30000,
    refetchOnWindowFocus: false,
  })

  const workspaceQuery = useQuery({
    queryKey: [queryKeyPrefix, 'workspace', filters],
    queryFn: () => fetchWorkspaceSnapshot(filters),
    staleTime: viewId === 'queue' ? 0 : 4000,
    refetchInterval: workspaceRefreshInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
  })

  const { liveWorkspace, socketStatus, bufferedEventCount } = useRealtimeDashboard({
    backend: workspaceQuery.data?.backend ?? defaultBackend,
    filters,
    initialWorkspace: workspaceQuery.data,
    isPaused: isRealtimePaused,
    enabled: enableRealtime,
    mode: realtimeMode,
  })

  const queueWorkspace = liveWorkspace ?? workspaceQuery.data
  const workspace = liveWorkspace ?? workspaceQuery.data
  const summary = workspace?.summary ?? summaryQuery.data
  const entries = workspace?.entries ?? summary?.entries ?? summaryQuery.data?.entries ?? []
  const backend = workspace?.backend ?? summary?.backend ?? defaultBackend
  const currentFeed = feedLabel({
    socketStatus,
    liveWorkspace: queueWorkspace ?? null,
    hasActiveFilters,
    isPaused: isRealtimePaused,
    bufferedEventCount,
    viewId,
  })

  return {
    hasActiveFilters,
    filterOptions: filterOptionsQuery.data,
    workspace,
    summary,
    entries,
    overview: workspace?.master_data,
    accounts: workspace?.account_catalog ?? [],
    products: workspace?.product_catalog ?? [],
    salesWorkspace: workspace?.sales_workspace,
    backend,
    currentFeed,
    bufferedEventCount,
  }
}