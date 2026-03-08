import type { FilterOptions, SalesFilters } from '../../entities/dashboard/api'
import FilterPopover from '../../shared/ui/filter-popover/FilterPopover'

type Props = {
  filters: SalesFilters
  filterOptions?: FilterOptions
  setFilter: (name: keyof SalesFilters, value: string) => void
  clearFilters: () => void
}

export default function SalesFilterPanel({ filters, filterOptions, setFilter, clearFilters }: Props) {
  return (
    <section className="panel section-panel section-frame section-panel-sales">
      <div className="panel-title-row">
        <div>
          <div className="meta-label">Commerce query rail</div>
          <h2>Painel de vendas</h2>
        </div>
        <button className="ghost-action" onClick={clearFilters}>Resetar vendas</button>
      </div>

      <div className="panel-subcopy">Filtros exclusivos do cockpit comercial: comprador, pedido, sale_id, status, pagamento, canal e recorte de tempo.</div>

      <div className="segmented-filter-grid sales-filter-grid">
        <FilterPopover label="Cliente" value={filters.customer_name ?? ''} placeholder="Nome do comprador" remoteField="customer_name" searchPlaceholder="Buscar nome" onChange={(value) => setFilter('customer_name', value)} />
        <FilterPopover label="CPF" value={filters.customer_cpf ?? ''} placeholder="000.000.000-00" remoteField="customer_cpf" searchPlaceholder="Buscar CPF" onChange={(value) => setFilter('customer_cpf', value)} />
        <FilterPopover label="Email" value={filters.customer_email ?? ''} placeholder="cliente@gmail.com" remoteField="customer_email" searchPlaceholder="Buscar email" onChange={(value) => setFilter('customer_email', value)} />
        <FilterPopover label="Sale ID" value={filters.sale_id ?? ''} placeholder="SAL-0000001" remoteField="sale_id" searchPlaceholder="Buscar sale_id" onChange={(value) => setFilter('sale_id', value)} />
        <FilterPopover label="Pedido" value={filters.order_id ?? ''} placeholder="SO-0000001" remoteField="order_id" searchPlaceholder="Buscar pedido" onChange={(value) => setFilter('order_id', value)} />
        <FilterPopover label="Canal" value={filters.channel ?? ''} placeholder="Todos os canais" options={filterOptions?.channels ?? []} onChange={(value) => setFilter('channel', value)} />
        <FilterPopover label="Produto líder" value={filters.product_name ?? ''} placeholder="Todos os produtos" options={filterOptions?.product_names ?? []} onChange={(value) => setFilter('product_name', value)} />
        <FilterPopover label="Categoria" value={filters.product_category ?? ''} placeholder="Todas as categorias" options={filterOptions?.product_categories ?? []} onChange={(value) => setFilter('product_category', value)} />
        <FilterPopover label="Segmento" value={filters.customer_segment ?? ''} placeholder="Todos os segmentos" options={filterOptions?.customer_segments ?? []} onChange={(value) => setFilter('customer_segment', value)} />
        <FilterPopover label="Status" value={filters.order_status ?? ''} placeholder="Todos os status" options={filterOptions?.order_statuses ?? []} onChange={(value) => setFilter('order_status', value)} />
        <FilterPopover label="Pagamento" value={filters.payment_method ?? ''} placeholder="Todos os meios" options={filterOptions?.payment_methods ?? []} onChange={(value) => setFilter('payment_method', value)} />
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