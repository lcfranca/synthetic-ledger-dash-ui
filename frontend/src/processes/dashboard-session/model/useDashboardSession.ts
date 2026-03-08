import { useQuery } from '@tanstack/react-query'
import {
  fetchFilterOptions,
  fetchSummary,
  fetchWorkspaceSnapshot,
} from '../../../entities/dashboard/api'
import { feedLabel } from '../../../entities/dashboard/lib/realtime'
import { useEntryFilters } from '../../../features/change-filter/model/useEntryFilters'
import { useRealtimeDashboard } from '../../../features/subscribe-stream/model/useRealtimeDashboard'

type Params = {
  defaultBackend: string
  queryKeyPrefix: string
}

export function useDashboardSession({ defaultBackend, queryKeyPrefix }: Params) {
  const { filters, setFilter, clearFilters, hasActiveFilters } = useEntryFilters()

  const summaryQuery = useQuery({
    queryKey: [queryKeyPrefix, 'summary', filters],
    queryFn: () => fetchSummary(filters),
  })

  const filterOptionsQuery = useQuery({
    queryKey: [queryKeyPrefix, 'filter-options'],
    queryFn: fetchFilterOptions,
    staleTime: 30000,
  })

  const workspaceQuery = useQuery({
    queryKey: [queryKeyPrefix, 'workspace', filters],
    queryFn: () => fetchWorkspaceSnapshot(filters),
  })

  const { liveWorkspace, socketStatus } = useRealtimeDashboard({
    backend: workspaceQuery.data?.backend ?? defaultBackend,
    filters,
    initialWorkspace: workspaceQuery.data,
  })

  const workspace = liveWorkspace ?? workspaceQuery.data
  const summary = workspace?.summary ?? summaryQuery.data
  const entries = workspace?.entries ?? summary?.entries ?? summaryQuery.data?.entries ?? []
  const backend = workspace?.backend ?? summary?.backend ?? defaultBackend
  const currentFeed = feedLabel(socketStatus, liveWorkspace, hasActiveFilters)

  return {
    filters,
    setFilter,
    clearFilters,
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
  }
}