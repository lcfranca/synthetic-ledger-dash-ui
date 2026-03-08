import type { SalesBreakdownRow, SalesWorkspace } from '../../entities/dashboard/api'
import { compact, money, quantity } from '../../shared/lib/format'
import { shortTs } from '../../shared/lib/time'

type Props = {
  salesWorkspace?: SalesWorkspace
}

function SalesBars({ title, subtitle, rows, valueKey }: { title: string; subtitle: string; rows: SalesBreakdownRow[]; valueKey: 'net_sales' | 'gross_sales' | 'order_count' }) {
  const values = rows.map((row) => Number(row[valueKey] ?? 0))
  const maxValue = Math.max(...values, 1)

  return (
    <article className="panel-surface sales-chart-card">
      <div className="panel-title-row compact-panel-title">
        <div>
          <div className="meta-label">Realtime chart</div>
          <h3>{title}</h3>
        </div>
        <div className="header-time compact-time">{subtitle}</div>
      </div>
      <div className="sales-bars">
        {rows.map((row) => {
          const value = Number(row[valueKey] ?? 0)
          return (
            <div key={row.label} className="sales-bar-row">
              <div className="sales-bar-meta">
                <strong>{row.label}</strong>
                <span>{valueKey === 'order_count' ? compact(value) : money(value)}</span>
              </div>
              <div className="sales-bar-track">
                <div className="sales-bar-fill" style={{ width: `${(value / maxValue) * 100}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </article>
  )
}

export default function SalesView({ salesWorkspace }: Props) {
  const kpis = salesWorkspace?.kpis
  const sales = salesWorkspace?.sales ?? []
  const byChannel = salesWorkspace?.by_channel ?? []
  const byProduct = salesWorkspace?.by_product ?? []
  const byStatus = salesWorkspace?.by_status ?? []

  return (
    <section className="section-stack">
      <section className="panel section-panel frame-panel cinematic-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Commerce stream</div>
            <h2>Painel de vendas em tempo real</h2>
          </div>
          <div className="title-cluster">
            <span className="status-pill ok">Live commerce</span>
            <div className="header-time compact-time">{compact(kpis?.order_count ?? 0)} pedidos rastreados</div>
          </div>
        </div>

        <div className="metric-strip sales-strip">
          <article className="metric-card accent-card panel-surface">
            <div className="metric-label">GMV bruto</div>
            <div className="metric-value">{money(kpis?.gross_sales ?? 0)}</div>
            <div className="metric-helper">Receita liquida {money(kpis?.net_sales ?? 0)}</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Pedidos</div>
            <div className="metric-value">{compact(kpis?.order_count ?? 0)}</div>
            <div className="metric-helper">Ticket medio {money(kpis?.average_ticket ?? 0)}</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Compradores unicos</div>
            <div className="metric-value">{compact(kpis?.unique_customers ?? 0)}</div>
            <div className="metric-helper">Itens por pedido {quantity(kpis?.avg_items_per_order ?? 0)}</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Unidades expedidas</div>
            <div className="metric-value">{quantity(kpis?.units_sold ?? 0)}</div>
            <div className="metric-helper">Status monitorados {compact(byStatus.length)}</div>
          </article>
        </div>
      </section>

      <section className="sales-charts-grid">
        <SalesBars title="Venda por canal" subtitle="Net sales" rows={byChannel} valueKey="net_sales" />
        <SalesBars title="Venda por produto" subtitle="Gross sales" rows={byProduct} valueKey="gross_sales" />
      </section>

      <section className="panel section-panel frame-panel cinematic-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Order ledger</div>
            <h2>Lista de vendas</h2>
          </div>
          <div className="header-time compact-time">Origem, comprador, metodo de pagamento, canal e composicao do carrinho em uma linha.</div>
        </div>

        <div className="table-wrap table-shell">
          <table className="data-table">
            <thead>
              <tr>
                <th>Horario</th>
                <th>Comprador</th>
                <th>Venda</th>
                <th>Canal</th>
                <th>Pagamento</th>
                <th>Status</th>
                <th>Carrinho</th>
                <th>Net</th>
                <th>Margem</th>
              </tr>
            </thead>
            <tbody>
              {sales.map((sale) => (
                <tr key={sale.sale_id}>
                  <td>{shortTs(sale.occurred_at)}</td>
                  <td>
                    <strong>{sale.customer_name || sale.customer_email || sale.customer_id || '-'}</strong>
                    <div className="cell-meta">{sale.customer_cpf || '-'} · {sale.customer_email || '-'}</div>
                  </td>
                  <td>
                    <strong>{sale.sale_id}</strong>
                    <div className="cell-meta">Pedido {sale.order_id} · {sale.lead_product || '-'} +{Math.max(sale.product_mix - 1, 0)}</div>
                  </td>
                  <td>
                    <strong>{sale.channel_name || sale.channel}</strong>
                    <div className="cell-meta">{sale.order_origin || '-'} · {sale.device_type || '-'}</div>
                  </td>
                  <td>
                    <strong>{sale.payment_method || '-'}</strong>
                    <div className="cell-meta">{sale.payment_installments}x · cupom {sale.coupon_code || 'sem cupom'}</div>
                  </td>
                  <td>
                    <span className="status-pill ok">{sale.order_status || '-'}</span>
                    <div className="cell-meta">{sale.freight_service || '-'} · {sale.sales_region || '-'}</div>
                  </td>
                  <td>
                    <strong>{quantity(sale.quantity)}</strong>
                    <div className="cell-meta">{sale.cart_items_count} itens · desconto {money(sale.cart_discount)}</div>
                  </td>
                  <td>
                    <strong>{money(sale.net_amount)}</strong>
                    <div className="cell-meta">Bruto {money(sale.gross_amount)} · taxa {money(sale.marketplace_fee_amount)}</div>
                  </td>
                  <td>
                    <strong>{money(sale.net_amount - sale.cmv)}</strong>
                    <div className="cell-meta">CMV {money(sale.cmv)} · tributo {money(sale.tax_amount)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  )
}