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
          <div className="meta-label">Leitura comercial</div>
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
  const isFallback = salesWorkspace?.data_mode === 'pinot_order_fallback'
  const margin = sales.reduce((acc, sale) => acc + (sale.net_amount - sale.cmv), 0)
  const totalDiscount = sales.reduce((acc, sale) => acc + sale.cart_discount, 0)
  const byPayment = Object.values(sales.reduce<Record<string, SalesBreakdownRow>>((acc, sale) => {
    const key = sale.payment_method || 'nao_informado'
    if (!acc[key]) {
      acc[key] = { label: key, order_count: 0, gross_sales: 0, net_sales: 0, quantity: 0 }
    }
    acc[key].order_count += 1
    acc[key].gross_sales = Number(acc[key].gross_sales ?? 0) + sale.gross_amount
    acc[key].net_sales += sale.net_amount
    acc[key].quantity = Number(acc[key].quantity ?? 0) + sale.quantity
    return acc
  }, {})).sort((left, right) => right.net_sales - left.net_sales).slice(0, 6)
  const liveTape = sales.slice(0, 6)

  if (!salesWorkspace || (!sales.length && !kpis?.order_count)) {
    return (
      <section className="panel section-panel section-frame sales-ledger-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Receita comercial</div>
            <h2>Dados comerciais indisponiveis nesta janela</h2>
          </div>
        </div>
        <div className="panel-empty-state">Nenhum registro comercial foi consolidado no recorte atual.</div>
      </section>
    )
  }

  return (
    <section className="section-stack">
      <section className="panel section-panel section-frame sales-command-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Receita comercial</div>
            <h2>Operacao comercial consolidada</h2>
          </div>
          <div className="title-cluster">
            <span className="status-pill ok">Leitura continua</span>
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
            <div className="metric-value">{isFallback ? 'N/D' : compact(kpis?.unique_customers ?? 0)}</div>
            <div className="metric-helper">Itens por pedido {quantity(kpis?.avg_items_per_order ?? 0)}</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Unidades expedidas</div>
            <div className="metric-value">{quantity(kpis?.units_sold ?? 0)}</div>
            <div className="metric-helper">Status monitorados {compact(byStatus.length)}</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Margem comercial</div>
            <div className="metric-value">{money(margin)}</div>
            <div className="metric-helper">Resultado após CMV do mix vendido</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Desconto capturado</div>
            <div className="metric-value">{money(totalDiscount)}</div>
            <div className="metric-helper">Cupom e markdown distribuídos no carrinho</div>
          </article>
        </div>

        {isFallback ? <div className="panel-subcopy">Alguns atributos comerciais ainda nao foram consolidados nesta janela. A leitura segue disponivel por pedido, produto, canal, quantidade e receita.</div> : null}

        <div className="sales-ticker-strip">
          {liveTape.map((sale) => (
            <div key={sale.sale_id || sale.order_id} className="ticker-card">
              <span>{sale.order_status || 'pedido'} · {shortTs(sale.occurred_at)}</span>
              <strong>{sale.sale_id || sale.order_id}</strong>
              <em>{sale.channel_name || sale.channel} · {money(sale.net_amount)}</em>
              <div className="ticker-note">{isFallback ? (sale.lead_product || '-') : (sale.customer_name || sale.customer_email || 'cliente nao identificado')}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="sales-charts-grid">
        <SalesBars title="Venda por canal" subtitle="Net sales" rows={byChannel} valueKey="net_sales" />
        <SalesBars title="Venda por produto" subtitle="Gross sales" rows={byProduct} valueKey="gross_sales" />
        {isFallback ? (
          <article className="panel section-panel section-frame">
            <div className="panel-title-row compact-panel-title">
              <div>
                <div className="meta-label">Campos parciais</div>
                <h3>Dimensoes comerciais parciais</h3>
              </div>
            </div>
            <div className="panel-subcopy">A leitura comercial segue disponivel por pedido, produto, canal, quantidade e receita enquanto os demais atributos sao consolidados.</div>
          </article>
        ) : (
          <>
            <SalesBars title="Status do pedido" subtitle="Pedidos" rows={byStatus} valueKey="order_count" />
            <SalesBars title="Pagamento" subtitle="Net sales" rows={byPayment} valueKey="net_sales" />
          </>
        )}
      </section>

      <section className="panel section-panel section-frame sales-ledger-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Pedidos e compradores</div>
            <h2>Lista de vendas</h2>
          </div>
          <div className="header-time compact-time">Comprador, pedido, canal, pagamento, status, composição do carrinho e margem comercial.</div>
        </div>

        <div className="table-wrap table-shell">
          <table className="data-table">
            <thead>
              {isFallback ? (
                <tr>
                  <th>Horario</th>
                  <th>Pedido</th>
                  <th>Produto lider</th>
                  <th>Canal</th>
                  <th>Mix</th>
                  <th>Qtd.</th>
                  <th>Receita</th>
                  <th>Margem</th>
                </tr>
              ) : (
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
              )}
            </thead>
            <tbody>
              {sales.map((sale) => (
                isFallback ? (
                  <tr key={sale.sale_id || sale.order_id}>
                    <td>{shortTs(sale.occurred_at)}</td>
                    <td>
                      <strong>{sale.order_id}</strong>
                      <div className="cell-meta">Chave comercial provisória do Pinot</div>
                    </td>
                    <td>
                      <strong>{sale.lead_product || '-'}</strong>
                      <div className="cell-meta">Mix de {Math.max(sale.product_mix, 1)} SKU(s)</div>
                    </td>
                    <td>{sale.channel_name || sale.channel}</td>
                    <td>{compact(sale.cart_items_count || sale.product_mix || 1)}</td>
                    <td>{quantity(sale.quantity)}</td>
                    <td>{money(sale.net_amount)}</td>
                    <td>{money(sale.net_amount - sale.cmv)}</td>
                  </tr>
                ) : (
                  <tr key={sale.sale_id || sale.order_id}>
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
                )
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  )
}