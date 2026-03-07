import type { ChangeEvent } from 'react'
import type { EntryFilters, FilterOptions } from '../../entities/dashboard/api'

type FilterSelectProps = {
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
  allLabel?: string
}

function FilterSelect({ label, value, onChange, options, allLabel = 'Todos' }: FilterSelectProps) {
  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value)

  return (
    <div className="filter-field">
      <label>{label}</label>
      <select value={value} onChange={handleChange}>
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
  const handleEntrySideChange = (event: ChangeEvent<HTMLSelectElement>) => setFilter('entry_side', event.target.value)
  const handleAsOfChange = (event: ChangeEvent<HTMLInputElement>) => setFilter('as_of', event.target.value)

  return (
    <section className="panel">
      <div className="panel-title-row">
        <h2>Filtros Operacionais</h2>
        <button className="ghost-action" onClick={clearFilters}>Limpar filtros</button>
      </div>

      <div className="filter-grid">
        <FilterSelect label="Produto" value={filters.product_name ?? ''} onChange={(value) => setFilter('product_name', value)} options={filterOptions?.product_names ?? []} />
        <FilterSelect label="Categoria do Produto" value={filters.product_category ?? ''} onChange={(value) => setFilter('product_category', value)} options={filterOptions?.product_categories ?? []} allLabel="Todas" />
        <FilterSelect label="Fornecedor" value={filters.supplier_name ?? ''} onChange={(value) => setFilter('supplier_name', value)} options={filterOptions?.supplier_names ?? []} />
        <FilterSelect label="Tipo de Evento" value={filters.event_type ?? ''} onChange={(value) => setFilter('event_type', value)} options={filterOptions?.event_types ?? []} />
        <FilterSelect label="Categoria de Lançamento" value={filters.entry_category ?? ''} onChange={(value) => setFilter('entry_category', value)} options={filterOptions?.entry_categories ?? []} allLabel="Todas" />
        <FilterSelect label="Conta Contábil" value={filters.account_code ?? ''} onChange={(value) => setFilter('account_code', value)} options={filterOptions?.account_codes ?? []} allLabel="Todas" />
        <FilterSelect label="Armazém" value={filters.warehouse_id ?? ''} onChange={(value) => setFilter('warehouse_id', value)} options={filterOptions?.warehouse_ids ?? []} />
        <div className="filter-field">
          <label>Tipo Lançamento</label>
          <select value={filters.entry_side ?? ''} onChange={handleEntrySideChange}>
            <option value="">Todos</option>
            <option value="debit">Débito</option>
            <option value="credit">Crédito</option>
          </select>
        </div>
        <FilterSelect label="Fonte Ontológica" value={filters.ontology_source ?? ''} onChange={(value) => setFilter('ontology_source', value)} options={filterOptions?.ontology_sources ?? []} allLabel="Todas" />
        <FilterSelect label="Canal de Venda" value={filters.channel ?? ''} onChange={(value) => setFilter('channel', value)} options={filterOptions?.channels ?? []} />
        <div className="filter-field">
          <label>As Of (Time-travel)</label>
          <input type="datetime-local" value={filters.as_of ?? ''} onChange={handleAsOfChange} />
        </div>
      </div>
    </section>
  )
}
