import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchFilterOptions, fetchSummary, type DashboardSummary, type EntryFilters } from '../entities/dashboard/api'
import FilterPanel from '../widgets/filter-panel/FilterPanel'
import KpiPanel from '../widgets/kpi-panel/KpiPanel'
import EntriesTable from '../widgets/entries-table/EntriesTable'

export default function App() {
  const [filters, setFilters] = useState<EntryFilters>({})

  const { data } = useQuery({
    queryKey: ['summary-pinot', filters],
    queryFn: () => fetchSummary(filters),
    refetchInterval: 5000
  })

  const { data: filterOptions } = useQuery({
    queryKey: ['filter-options-pinot'],
    queryFn: fetchFilterOptions,
    staleTime: 30000
  })

  const [live, setLive] = useState<DashboardSummary | null>(null)

  useEffect(() => {
    const ws = new WebSocket(`${window.location.origin.replace('http', 'ws')}/ws/metrics`)
    ws.onmessage = (event) => setLive(JSON.parse(event.data))
    return () => ws.close()
  }, [])

  const hasActiveFilters = Object.values(filters).some((value) => Boolean(value))
  const summary = hasActiveFilters ? data : (live ?? data)

  const setFilter = (name: keyof EntryFilters, value: string) => {
    setFilters((current: EntryFilters) => ({ ...current, [name]: value }))
  }

  const clearFilters = () => setFilters({})

  return (
    <main className="shield-app">
      <header className="panel shell-header">
        <div>
          <div className="meta-label">Synthetic Ledger Control Center</div>
          <h1>Dashboard Escudo Financeiro - Pinot</h1>
        </div>
        <div className="header-time">
          <div>Atualização: {summary?.timestamp ?? '-'}</div>
          <div>As Of: {summary?.as_of ?? '-'}</div>
          <div>Backend: {summary?.backend ?? 'pinot'}</div>
        </div>
      </header>

      <FilterPanel filters={filters} filterOptions={filterOptions} setFilter={setFilter} clearFilters={clearFilters} />
      <KpiPanel summary={summary} />
      <EntriesTable summary={summary} />
    </main>
  )
}
