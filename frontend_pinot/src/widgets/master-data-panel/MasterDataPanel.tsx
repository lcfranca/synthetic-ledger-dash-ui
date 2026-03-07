import type { MasterDataOverview } from '../../entities/dashboard/api'
import { money } from '../../shared/lib/format'

type Props = {
  overview?: MasterDataOverview
}

const percentFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1
})

const decimalFormatter = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2
})

function stockTotal(initialStock: Record<string, number>) {
  return Object.values(initialStock).reduce((total, value) => total + Number(value), 0)
}

export default function MasterDataPanel({ overview }: Props) {
  if (!overview) return null

  const { company, stats, channels, products, accounts } = overview
  const channelsById = new Map(channels.map((channel) => [channel.channel_id, channel.channel_name]))

  return (
    <section className="panel catalog-panel">
      <div className="panel-title-row">
        <div>
          <h2>Catalogo Operacional</h2>
          <div className="catalog-subtitle">Master data corporativo exposto pela stack Pinot</div>
        </div>
        <div className="catalog-subtitle">{company.trade_name} · {company.segment}</div>
      </div>

      <div className="catalog-stat-grid">
        <article className="catalog-stat-card">
          <div className="metric-label">Produtos</div>
          <div className="metric-value">{stats.product_count}</div>
        </article>
        <article className="catalog-stat-card">
          <div className="metric-label">Canais</div>
          <div className="metric-value">{stats.channel_count}</div>
        </article>
        <article className="catalog-stat-card">
          <div className="metric-label">Contas</div>
          <div className="metric-value">{stats.account_count}</div>
        </article>
        <article className="catalog-stat-card">
          <div className="metric-label">Estoques Iniciais</div>
          <div className="metric-value">{stats.opening_inventory_units}</div>
        </article>
      </div>

      <div className="catalog-detail-grid">
        <article className="catalog-card identity-card">
          <div className="meta-label">Identidade</div>
          <h3>{company.trade_name}</h3>
          <p>{company.description}</p>
          <dl className="catalog-definition-list">
            <div>
              <dt>Razao social</dt>
              <dd>{company.legal_name}</dd>
            </div>
            <div>
              <dt>Sede</dt>
              <dd>{company.headquarters_city}/{company.headquarters_state}</dd>
            </div>
            <div>
              <dt>Moeda</dt>
              <dd>{company.currency}</dd>
            </div>
            <div>
              <dt>Fornecedores</dt>
              <dd>{stats.supplier_count}</dd>
            </div>
            <div>
              <dt>Armazens</dt>
              <dd>{stats.warehouse_count}</dd>
            </div>
          </dl>
        </article>

        <article className="catalog-card">
          <div className="meta-label">Canais de Venda</div>
          <div className="channel-grid">
            {channels.map((channel) => (
              <div key={channel.channel_id} className="channel-card">
                <div className="channel-card-header">
                  <strong>{channel.channel_name}</strong>
                  <span className="pill">{channel.channel_type}</span>
                </div>
                <div className="channel-meta-row">
                  <span>Comissao</span>
                  <span>{percentFormatter.format(channel.commission_rate)}</span>
                </div>
                <div className="channel-meta-row">
                  <span>Repasse</span>
                  <span>{channel.settlement_days} dias</span>
                </div>
                <div className="channel-meta-row">
                  <span>Multiplicador</span>
                  <span>{decimalFormatter.format(channel.price_multiplier)}x</span>
                </div>
              </div>
            ))}
          </div>
        </article>
      </div>

      <div className="catalog-table-grid">
        <article className="catalog-card">
          <div className="meta-label">Produtos</div>
          <div className="table-wrap catalog-table-wrap">
            <table className="catalog-table">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Fornecedor</th>
                  <th>Armazem Base</th>
                  <th>Custo</th>
                  <th>Preco</th>
                  <th>Estoque Inicial</th>
                  <th>Canais</th>
                </tr>
              </thead>
              <tbody>
                {products.map((product) => (
                  <tr key={product.product_id}>
                    <td>
                      <strong>{product.product_name}</strong>
                      <div className="subtle-value">{product.product_category} · {product.product_brand}</div>
                    </td>
                    <td>{product.supplier_name}</td>
                    <td>{product.warehouse_name}</td>
                    <td>{money(product.base_cost)}</td>
                    <td>{money(product.base_price)}</td>
                    <td>{stockTotal(product.initial_stock)}</td>
                    <td>
                      <div className="tag-list">
                        {product.channel_ids.map((channelId) => (
                          <span key={channelId} className="pill pill--compact">{channelsById.get(channelId) ?? channelId}</span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="catalog-card">
          <div className="meta-label">Plano de Contas</div>
          <div className="table-wrap catalog-table-wrap">
            <table className="catalog-table">
              <thead>
                <tr>
                  <th>Codigo</th>
                  <th>Conta</th>
                  <th>Secao</th>
                  <th>Role</th>
                  <th>Categoria</th>
                  <th>Lado Normal</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => (
                  <tr key={account.account_code}>
                    <td className="mono-text">{account.account_code}</td>
                    <td>{account.account_name}</td>
                    <td>{account.statement_section}</td>
                    <td>{account.account_role}</td>
                    <td>{account.entry_category}</td>
                    <td>{account.normal_side}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </div>
    </section>
  )
}