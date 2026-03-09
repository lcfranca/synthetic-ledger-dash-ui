import { useState } from 'react'
import { useEntryFilters } from '../features/change-filter/model/useEntryFilters'
import { type EntryFilters, type QueueFilters, type SalesFilters } from '../entities/dashboard/api'
import { type ViewId } from '../shared/config/dashboardViews'
import { useDashboardSession } from '../processes/dashboard-session/model/useDashboardSession'
import QueueFilterPanel from '../widgets/filter-panel/QueueFilterPanel'
import SalesFilterPanel from '../widgets/filter-panel/SalesFilterPanel'
import QueueView from '../widgets/queue-view/QueueView'
import SalesView from '../widgets/sales-view/SalesView'
import AccountingView from '../widgets/accounting-view/AccountingView'
import AccountsView from '../widgets/accounts-view/AccountsView'
import ObservabilityView from '../widgets/observability-view/ObservabilityView'
import ProductsView from '../widgets/products-view/ProductsView'
import ShellMetrics from '../widgets/shell-metrics/ShellMetrics'
import DashboardHeader from '../widgets/dashboard-header/DashboardHeader'
import SideRail from '../widgets/side-rail/SideRail'

function resolveBackendConfig() {
  const configuredBackend = (import.meta.env.VITE_DASHBOARD_BACKEND ?? 'pinot').trim().toLowerCase()

  if (configuredBackend === 'druid' || configuredBackend === 'clickhouse' || configuredBackend === 'materialize') {
    return { defaultBackend: configuredBackend, queryKeyPrefix: configuredBackend }
  }

  return { defaultBackend: 'pinot', queryKeyPrefix: 'pinot' }
}

export default function App() {
  const [activeView, setActiveView] = useState<ViewId>('queue')
  const [isRealtimePaused, setIsRealtimePaused] = useState(false)
  const queueFiltersState = useEntryFilters<QueueFilters>()
  const salesFiltersState = useEntryFilters<SalesFilters>()
  const backendConfig = resolveBackendConfig()

  const usesSalesFilters = activeView === 'sales'

  const activeFilters: EntryFilters = usesSalesFilters
    ? { ...salesFiltersState.filters }
    : { ...queueFiltersState.filters }

  const activeHasFilters = usesSalesFilters ? salesFiltersState.hasActiveFilters : queueFiltersState.hasActiveFilters

  const session = useDashboardSession({ defaultBackend: backendConfig.defaultBackend, queryKeyPrefix: backendConfig.queryKeyPrefix, filters: activeFilters, hasActiveFilters: activeHasFilters, viewId: activeView, isRealtimePaused })

  return (
    <main className="dashboard-shell">
      <div className="ambient-grid" />

      <SideRail
        activeView={activeView}
        backend={session.backend}
        setActiveView={setActiveView}
        workspace={session.workspace}
        summary={session.summary}
      />

      <section className="content-column">
        <DashboardHeader activeView={activeView} currentFeed={session.currentFeed} filters={activeFilters} workspace={session.workspace} summary={session.summary} />

        <ShellMetrics summary={session.summary} overview={session.overview} backend={session.backend} feedMode={session.currentFeed} isRealtimePaused={isRealtimePaused} pendingRealtimeEvents={session.bufferedEventCount} onToggleRealtime={() => setIsRealtimePaused((current) => !current)} />

        {activeView !== 'sales' ? <QueueFilterPanel filters={queueFiltersState.filters} filterOptions={session.filterOptions} setFilter={queueFiltersState.setFilter} clearFilters={queueFiltersState.clearFilters} /> : null}
        {activeView === 'sales' ? <SalesFilterPanel filters={salesFiltersState.filters} filterOptions={session.filterOptions} setFilter={salesFiltersState.setFilter} clearFilters={salesFiltersState.clearFilters} /> : null}
        {activeView === 'queue' ? <QueueView summary={session.summary} entries={session.entries} isRealtimePaused={isRealtimePaused} bufferedEventCount={session.bufferedEventCount} onToggleRealtime={() => setIsRealtimePaused((current) => !current)} /> : null}
        {activeView === 'sales' ? <SalesView salesWorkspace={session.salesWorkspace} /> : null}
        {activeView === 'accounting' ? <AccountingView summary={session.summary} /> : null}
        {activeView === 'accounts' ? <AccountsView accounts={session.accounts} /> : null}
        {activeView === 'products' ? <ProductsView products={session.products} /> : null}
        {activeView === 'observability' ? <ObservabilityView summary={session.summary} entries={session.entries} accounts={session.accounts} products={session.products} salesWorkspace={session.salesWorkspace} /> : null}
      </section>
    </main>
  )
}
