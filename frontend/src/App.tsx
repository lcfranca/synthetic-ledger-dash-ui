import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchFilterOptions, fetchSummary, type DashboardSummary, type EntryFilters, type JournalEntry } from './api'

function money(value: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
}

function sideLabel(side: JournalEntry['entry_side']) {
  return side === 'debit' ? 'Débito' : 'Crédito'
}

type FilterSelectProps = {
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
  allLabel?: string
}

function FilterSelect({ label, value, onChange, options, allLabel = 'Todos' }: FilterSelectProps) {
  return (
    <div className="filter-field">
      <label>{label}</label>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{allLabel}</option>
        {options.map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
    </div>
  )
}

export default function App() {
  const [filters, setFilters] = useState<EntryFilters>({})

  const { data } = useQuery({
    queryKey: ['summary', filters],
    queryFn: () => fetchSummary(filters),
    refetchInterval: 5000
  })

  const { data: filterOptions } = useQuery({
    queryKey: ['filter-options'],
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
    setFilters((current) => ({ ...current, [name]: value }))
  }

  const clearFilters = () => setFilters({})

  return (
    <main className="shield-app">
      <header className="panel shell-header">
        <div>
          <div className="meta-label">
            Synthetic Ledger Control Center
          </div>
          <h1>Dashboard Escudo Financeiro</h1>
        </div>
        <div className="header-time">
          <div>Atualização: {summary?.timestamp ?? '-'}</div>
          <div>As Of: {summary?.as_of ?? '-'}</div>
        </div>
      </header>

      <section className="panel">
        <div className="panel-title-row">
          <h2>Filtros Operacionais</h2>
          <button className="ghost-action" onClick={clearFilters}>
            Limpar filtros
          </button>
        </div>

        <div className="filter-grid">
          <FilterSelect label="Produto" value={filters.product_id ?? ''} onChange={(value) => setFilter('product_id', value)} options={filterOptions?.product_ids ?? []} />
          <FilterSelect label="Fornecedor" value={filters.supplier_id ?? ''} onChange={(value) => setFilter('supplier_id', value)} options={filterOptions?.supplier_ids ?? []} />
          <FilterSelect label="Tipo de Evento" value={filters.event_type ?? ''} onChange={(value) => setFilter('event_type', value)} options={filterOptions?.event_types ?? []} />
          <FilterSelect label="Categoria de Lançamento" value={filters.entry_category ?? ''} onChange={(value) => setFilter('entry_category', value)} options={filterOptions?.entry_categories ?? []} allLabel="Todas" />
          <FilterSelect label="Conta Contábil" value={filters.account_code ?? ''} onChange={(value) => setFilter('account_code', value)} options={filterOptions?.account_codes ?? []} allLabel="Todas" />
          <FilterSelect label="Armazém" value={filters.warehouse_id ?? ''} onChange={(value) => setFilter('warehouse_id', value)} options={filterOptions?.warehouse_ids ?? []} />
          <div className="filter-field">
            <label>Tipo Lançamento</label>
            <select value={filters.entry_side ?? ''} onChange={(event) => setFilter('entry_side', event.target.value)}>
              <option value="">Todos</option>
              <option value="debit">Débito</option>
              <option value="credit">Crédito</option>
            </select>
          </div>
          <FilterSelect label="Fonte Ontológica" value={filters.ontology_source ?? ''} onChange={(value) => setFilter('ontology_source', value)} options={filterOptions?.ontology_sources ?? []} allLabel="Todas" />
          <FilterSelect label="Canal" value={filters.channel ?? ''} onChange={(value) => setFilter('channel', value)} options={filterOptions?.channels ?? []} />
          <div className="filter-field">
            <label>As Of (Time-travel)</label>
            <input type="datetime-local" value={filters.as_of ?? ''} onChange={(event) => setFilter('as_of', event.target.value)} />
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>KPIs Contábeis</h2>
        <div className="metric-grid">
          <article className="metric-card">
            <div className="metric-label">Caixa</div>
            <div className="metric-value">{summary ? money(summary.balance_sheet.assets.cash) : '-'}</div>
          </article>
          <article className="metric-card">
            <div className="metric-label">Estoque</div>
            <div className="metric-value">{summary ? money(summary.balance_sheet.assets.inventory) : '-'}</div>
          </article>
          <article className="metric-card metric-card--accent">
            <div className="metric-label">Receita</div>
            <div className="metric-value">{summary ? money(summary.income_statement.revenue) : '-'}</div>
          </article>
          <article className="metric-card">
            <div className="metric-label">CMV</div>
            <div className="metric-value">{summary ? money(summary.income_statement.cmv) : '-'}</div>
          </article>
          <article className="metric-card">
            <div className="metric-label">Resultado Líquido</div>
            <div className="metric-value">{summary ? money(summary.income_statement.net_income) : '-'}</div>
          </article>
        </div>
      </section>

      <section className="panel">
        <h2>
          Fila de Lançamentos Débito/Crédito
        </h2>
        <div className="table-wrap">
          <table className="ledger-table">
            <thead>
              <tr>
                {['Ocorrido em', 'Tipo', 'Conta', 'Categoria', 'Produto', 'Fornecedor', 'Canal', 'Valor', 'Origem Ontológica', 'Descrição Ontológica', 'Event ID', 'Trace ID', 'Hash'].map((header) => (
                  <th key={header}>
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(summary?.entries ?? []).map((entry) => (
                <tr key={entry.entry_id}>
                  <td>{entry.occurred_at}</td>
                  <td>{sideLabel(entry.entry_side)}</td>
                  <td>{entry.account_code} - {entry.account_name}</td>
                  <td>{entry.entry_category}</td>
                  <td>{entry.product_id}</td>
                  <td>{entry.supplier_id ?? '-'}</td>
                  <td>{entry.channel}</td>
                  <td>{money(entry.amount)}</td>
                  <td>{entry.ontology_event_type} ({entry.ontology_source})</td>
                  <td>{entry.ontology_description}</td>
                  <td className="mono-text">{entry.event_id}</td>
                  <td className="mono-text">{entry.trace_id}</td>
                  <td className="mono-text">{entry.source_payload_hash.slice(0, 20)}...</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
