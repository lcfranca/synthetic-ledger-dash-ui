import type { ProductCatalogRow } from '../../entities/dashboard/api'
import { productAudit } from '../../entities/dashboard/lib/realtime'
import { compact, daysCoverage, money, percent, quantity } from '../../shared/lib/format'

type Props = {
  products: ProductCatalogRow[]
}

export default function ProductsView({ products }: Props) {
  const audit = productAudit(products)

  return (
    <section className="section-stack">
      <section className="panel section-panel frame-panel cinematic-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Malha de abastecimento</div>
            <h2>Inventario de produtos</h2>
          </div>
          <div className="title-cluster">
            <span className="status-pill ok">Leitura integrada</span>
            <div className="header-time compact-time">{products.length} SKUs</div>
          </div>
        </div>

        <div className="metric-strip audit-strip">
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Estoque inicial</div>
            <div className="metric-value">{compact(audit.opening)}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Vendidos</div>
            <div className="metric-value">{compact(audit.sold)}</div>
            <div className="metric-helper">Volume liquido apos devolucoes</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Devolvidos</div>
            <div className="metric-value">{compact(audit.returned)}</div>
            <div className="metric-helper">Taxa de retorno {percent(audit.returnRatePct)}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Estoque atual</div>
            <div className="metric-value">{compact(audit.current)}</div>
            <div className="metric-helper">Reposicao pendente: {audit.restock}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Margem bruta</div>
            <div className="metric-value">{percent(audit.grossMarginPct)}</div>
            <div className="metric-helper">Lucro bruto {money(audit.grossProfit)}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Margem liquida</div>
            <div className="metric-value">{percent(audit.netMarginPct)}</div>
            <div className="metric-helper">Resultado liquido {money(audit.netProfit)}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Receita liquida</div>
            <div className="metric-value">{money(audit.netRevenue)}</div>
            <div className="metric-helper">Compra sugerida {compact(audit.suggestedPurchase)} un</div>
          </article>
        </div>
      </section>

      <section className="panel section-panel frame-panel cinematic-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Cobertura e reposicao</div>
            <h2>Catalogo e cobertura</h2>
          </div>
          <div className="header-time compact-time">Cobertura, giro e reposicao por SKU</div>
        </div>

        <div className="table-wrap table-shell">
          <table className="data-table">
            <thead>
              <tr>
                <th>Produto</th>
                <th>Canais</th>
                <th>Precos</th>
                <th>Inicial</th>
                <th>Estoque</th>
                <th>Vend. bruta</th>
                <th>Devolvido</th>
                <th>Vend. liquida</th>
                <th>Receita liquida</th>
                <th>Margens</th>
                <th>Cobertura</th>
                <th>Reposicao</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.product_id}>
                  <td>
                    <strong>{product.product_name}</strong>
                    <div className="cell-meta">{product.product_category} · {product.product_brand}</div>
                  </td>
                  <td>{product.registered_channels.join(', ')}</td>
                  <td>
                    <strong>{money(product.average_sale_price)}</strong>
                    <div className="cell-meta">Compra {money(product.average_purchase_price)}</div>
                  </td>
                  <td>{quantity(product.opening_stock_quantity ?? 0)}</td>
                  <td>{quantity(product.current_stock_quantity)}</td>
                  <td>{quantity(product.sold_quantity)}</td>
                  <td>
                    <strong>{quantity(product.returned_quantity)}</strong>
                    <div className="cell-meta">{percent(product.return_rate_pct)} da venda bruta</div>
                  </td>
                  <td>{quantity(product.net_sold_quantity)}</td>
                  <td>
                    <strong>{money(product.net_revenue_amount)}</strong>
                    <div className="cell-meta">CMV {money(product.cogs_amount)}</div>
                  </td>
                  <td>
                    <strong>{percent(product.gross_margin_pct)}</strong>
                    <div className="cell-meta">Liquida {percent(product.net_margin_pct)} · lucro {money(product.net_profit_amount)}</div>
                  </td>
                  <td>
                    <strong>{daysCoverage(product.coverage_days)}</strong>
                    <div className="cell-meta">Demanda {quantity(product.daily_demand_units)} un/dia</div>
                  </td>
                  <td>
                    <span className={`status-pill ${product.needs_restock ? 'warn' : 'ok'}`}>
                      {product.needs_restock ? `${quantity(product.suggested_purchase_quantity)} un · ${product.suggested_purchase_supplier_name}` : 'Cobertura saudavel'}
                    </span>
                    <div className="cell-meta">{product.purchase_recommendation}</div>
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