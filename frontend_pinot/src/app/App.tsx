import { useState } from 'react'
import { type ViewId } from '../shared/config/dashboardViews'
import { useDashboardSession } from '../processes/dashboard-session/model/useDashboardSession'
import FilterPanel from '../widgets/filter-panel/FilterPanel'
import QueueView from '../widgets/queue-view/QueueView'
import SalesView from '../widgets/sales-view/SalesView'
import AccountingView from '../widgets/accounting-view/AccountingView'
import AccountsView from '../widgets/accounts-view/AccountsView'
import ProductsView from '../widgets/products-view/ProductsView'
import ShellMetrics from '../widgets/shell-metrics/ShellMetrics'
import DashboardHeader from '../widgets/dashboard-header/DashboardHeader'
import SideRail from '../widgets/side-rail/SideRail'

export default function App() {
  const [activeView, setActiveView] = useState<ViewId>('queue')
  const session = useDashboardSession({ defaultBackend: 'pinot', queryKeyPrefix: 'pinot' })

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
        <DashboardHeader currentFeed={session.currentFeed} filters={session.filters} workspace={session.workspace} summary={session.summary} />

        <ShellMetrics summary={session.summary} overview={session.overview} backend={session.backend} feedMode={session.currentFeed} />

        {activeView === 'queue' || activeView === 'sales' ? <FilterPanel filters={session.filters} filterOptions={session.filterOptions} setFilter={session.setFilter} clearFilters={session.clearFilters} /> : null}
        {activeView === 'queue' ? <QueueView summary={session.summary} entries={session.entries} /> : null}
        {activeView === 'sales' ? <SalesView salesWorkspace={session.salesWorkspace} /> : null}
        {activeView === 'accounting' ? <AccountingView summary={session.summary} /> : null}
        {activeView === 'accounts' ? <AccountsView accounts={session.accounts} /> : null}
        {activeView === 'products' ? <ProductsView products={session.products} /> : null}
      </section>
    </main>
  )
}
