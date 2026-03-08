import type { QueueFilters, FilterOptions } from '../../entities/dashboard/api'
import FilterPopover from '../../shared/ui/filter-popover/FilterPopover'

type Props = {
  filters: QueueFilters
  filterOptions?: FilterOptions
  setFilter: (name: keyof QueueFilters, value: string) => void
  clearFilters: () => void
}

export default function QueueFilterPanel({ filters, filterOptions, setFilter, clearFilters }: Props) {
  return (
    <section className="panel section-panel section-frame section-panel-queue">
      <div className="panel-title-row">
        <div>
          <div className="meta-label">Accounting query rail</div>
          <h2>Lançamentos Contábeis</h2>
        </div>
        <button className="ghost-action" onClick={clearFilters}>Resetar lançamentos</button>
      </div>

      <div className="panel-subcopy">Filtros exclusivos da trilha contábil: conta, lado, ontologia, armazém e recorte temporal do stream.</div>

      <div className="segmented-filter-grid queue-filter-grid">
        <FilterPopover label="Produto" value={filters.product_name ?? ''} placeholder="Todos os produtos" options={filterOptions?.product_names ?? []} onChange={(value) => setFilter('product_name', value)} />
        <FilterPopover label="Categoria" value={filters.product_category ?? ''} placeholder="Todas as categorias" options={filterOptions?.product_categories ?? []} onChange={(value) => setFilter('product_category', value)} />
        <FilterPopover label="Fornecedor" value={filters.supplier_name ?? ''} placeholder="Todos os fornecedores" options={filterOptions?.supplier_names ?? []} onChange={(value) => setFilter('supplier_name', value)} />
        <FilterPopover label="Evento" value={filters.event_type ?? ''} placeholder="Todos os eventos" options={filterOptions?.event_types ?? []} onChange={(value) => setFilter('event_type', value)} />
        <FilterPopover label="Categoria contábil" value={filters.entry_category ?? ''} placeholder="Todas as categorias" options={filterOptions?.entry_categories ?? []} onChange={(value) => setFilter('entry_category', value)} />
        <FilterPopover label="Conta" value={filters.account_code ?? ''} placeholder="Todas as contas" options={filterOptions?.account_codes ?? []} onChange={(value) => setFilter('account_code', value)} />
        <FilterPopover label="Armazém" value={filters.warehouse_id ?? ''} placeholder="Todos os armazéns" options={filterOptions?.warehouse_ids ?? []} onChange={(value) => setFilter('warehouse_id', value)} />
        <FilterPopover label="Canal" value={filters.channel ?? ''} placeholder="Todos os canais" options={filterOptions?.channels ?? []} onChange={(value) => setFilter('channel', value)} />
        <FilterPopover label="Origem" value={filters.ontology_source ?? ''} placeholder="Todas as origens" options={filterOptions?.ontology_sources ?? []} onChange={(value) => setFilter('ontology_source', value)} />
        <FilterPopover label="Lado" value={filters.entry_side ?? ''} placeholder="Débito ou crédito" options={['debit', 'credit']} onChange={(value) => setFilter('entry_side', value)} />
        <div className="filter-block filter-time-block">
          <div className="filter-block-label">Início</div>
          <input className="filter-datetime" type="datetime-local" value={(filters.start_at ?? '').slice(0, 16)} onChange={(event) => setFilter('start_at', event.target.value ? new Date(event.target.value).toISOString() : '')} />
        </div>
        <div className="filter-block filter-time-block">
          <div className="filter-block-label">Fim</div>
          <input className="filter-datetime" type="datetime-local" value={(filters.end_at ?? '').slice(0, 16)} onChange={(event) => setFilter('end_at', event.target.value ? new Date(event.target.value).toISOString() : '')} />
        </div>
      </div>
    </section>
  )
}