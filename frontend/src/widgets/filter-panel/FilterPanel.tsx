import type { EntryFilters, FilterOptions } from '../../entities/dashboard/api'

type FilterSelectProps = {
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
  allLabel?: string
}

function FilterSelect({ label, value, onChange, options, allLabel = 'Todos' }: FilterSelectProps) {
  return (
    <div className="filter-field panel-chip">
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

type Props = {
  filters: EntryFilters
  filterOptions?: FilterOptions
  setFilter: (name: keyof EntryFilters, value: string) => void
  clearFilters: () => void
}

export default function FilterPanel({ filters, filterOptions, setFilter, clearFilters }: Props) {
  return (
    <section className="panel section-panel frame-panel">
      <div className="panel-title-row">
        <div>
          <div className="meta-label">Consulta operacional</div>
          <h2>Filtros da fila</h2>
        </div>
        <button className="ghost-action" onClick={clearFilters}>Resetar consulta</button>
      </div>

      <div className="filter-grid">
        <FilterSelect label="Produto" value={filters.product_name ?? ''} onChange={(value) => setFilter('product_name', value)} options={filterOptions?.product_names ?? []} />
        <FilterSelect label="Categoria" value={filters.product_category ?? ''} onChange={(value) => setFilter('product_category', value)} options={filterOptions?.product_categories ?? []} />
        <FilterSelect label="Fornecedor" value={filters.supplier_name ?? ''} onChange={(value) => setFilter('supplier_name', value)} options={filterOptions?.supplier_names ?? []} />
        <FilterSelect label="Tipo de evento" value={filters.event_type ?? ''} onChange={(value) => setFilter('event_type', value)} options={filterOptions?.event_types ?? []} />
        <FilterSelect label="Categoria contabil" value={filters.entry_category ?? ''} onChange={(value) => setFilter('entry_category', value)} options={filterOptions?.entry_categories ?? []} allLabel="Todas" />
        <FilterSelect label="Conta" value={filters.account_code ?? ''} onChange={(value) => setFilter('account_code', value)} options={filterOptions?.account_codes ?? []} allLabel="Todas" />
        <FilterSelect label="Armazem" value={filters.warehouse_id ?? ''} onChange={(value) => setFilter('warehouse_id', value)} options={filterOptions?.warehouse_ids ?? []} />
        <FilterSelect label="Canal" value={filters.channel ?? ''} onChange={(value) => setFilter('channel', value)} options={filterOptions?.channels ?? []} />
        <FilterSelect label="Origem" value={filters.ontology_source ?? ''} onChange={(value) => setFilter('ontology_source', value)} options={filterOptions?.ontology_sources ?? []} allLabel="Todas" />
        <div className="filter-field panel-chip">
          <label>Tipo de lancamento</label>
          <select value={filters.entry_side ?? ''} onChange={(event) => setFilter('entry_side', event.target.value)}>
            <option value="">Todos</option>
            <option value="debit">Debito</option>
            <option value="credit">Credito</option>
          </select>
        </div>
        <div className="filter-field panel-chip">
          <label>As Of</label>
          <input type="datetime-local" value={filters.as_of ?? ''} onChange={(event) => setFilter('as_of', event.target.value)} />
        </div>
      </div>
    </section>
  )
}