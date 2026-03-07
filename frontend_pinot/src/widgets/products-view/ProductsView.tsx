import type { ProductCatalogRow } from '../../entities/dashboard/api'
import { productAudit } from '../../entities/dashboard/lib/realtime'
import { compact, daysCoverage, money, quantity } from '../../shared/lib/format'

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
            <div className="meta-label">Stock audit bus</div>
            <h2>Inventario de produtos</h2>
          </div>
          <div className="title-cluster">
            <span className="status-pill ok">Integrado ao razao</span>
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
            <div className="metric-helper">Baixa vinda de eventos sale + conta inventory</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Devolvidos</div>
            <div className="metric-value">{compact(audit.returned)}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Estoque atual</div>
            <div className="metric-value">{compact(audit.current)}</div>
            <div className="metric-helper">Reposicao pendente: {audit.restock}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Compra sugerida</div>
            <div className="metric-value">{compact(audit.suggestedPurchase)}</div>
            <div className="metric-helper">Volume total para recompor alvo</div>
          </article>
        </div>
      </section>

      <section className="panel section-panel frame-panel cinematic-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Rastro operacional</div>
            <h2>Catalogo e cobertura</h2>
          </div>
          <div className="header-time compact-time">Saida de estoque sempre refletida por evento</div>
        </div>

        <div className="table-wrap table-shell">
          <table className="data-table">
            <thead>
              <tr>
                <th>Produto</th>
                <th>Canais</th>
                <th>Preco venda</th>
                <th>Preco compra</th>
                <th>Inicial</th>
                <th>Estoque</th>
                <th>Vendido</th>
                <th>Devolvido</th>
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
                  <td>{money(product.average_sale_price)}</td>
                  <td>{money(product.average_purchase_price)}</td>
                  <td>{quantity(product.opening_stock_quantity ?? 0)}</td>
                  <td>{quantity(product.current_stock_quantity)}</td>
                  <td>{quantity(product.sold_quantity)}</td>
                  <td>{quantity(product.returned_quantity)}</td>
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