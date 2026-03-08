import type { DashboardSummary, JournalEntry } from '../../entities/dashboard/api'
import { compact, money, quantity, sideLabel } from '../../shared/lib/format'
import { shortTs } from '../../shared/lib/time'

type Props = {
  summary?: DashboardSummary
  entries: JournalEntry[]
}

export default function QueueView({ summary, entries }: Props) {
  const debits = entries.filter((item) => item.entry_side === 'debit').length
  const credits = entries.filter((item) => item.entry_side === 'credit').length

  return (
    <section className="panel section-panel frame-panel cinematic-panel">
      <div className="panel-title-row">
        <div>
          <div className="meta-label">Audit stream</div>
          <h2>Fila corrente de eventos</h2>
        </div>
        <div className="title-cluster">
          <span className="status-pill ok">Realtime</span>
          <div className="header-time compact-time">{shortTs(summary?.timestamp)}</div>
        </div>
      </div>

      <div className="metric-strip compact-strip audit-strip">
        <article className="metric-card compact-card panel-surface">
          <div className="metric-label">Lancamentos visiveis</div>
          <div className="metric-value">{compact(entries.length)}</div>
        </article>
        <article className="metric-card compact-card panel-surface">
          <div className="metric-label">Debitos</div>
          <div className="metric-value">{compact(debits)}</div>
        </article>
        <article className="metric-card compact-card panel-surface">
          <div className="metric-label">Creditos</div>
          <div className="metric-value">{compact(credits)}</div>
        </article>
      </div>

      <div className="table-wrap table-shell">
        <table className="data-table">
          <thead>
            <tr>
              <th>Horario</th>
              <th>Evento</th>
              <th>Pedido</th>
              <th>Cliente</th>
              <th>Produto</th>
              <th>Canal</th>
              <th>Conta</th>
              <th>Lado</th>
              <th>Qtd.</th>
              <th>Valor unit.</th>
              <th>Valor</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.entry_id}>
                <td>{shortTs(entry.occurred_at)}</td>
                <td>
                  <strong>{entry.ontology_event_type}</strong>
                  <div className="cell-meta">{entry.ontology_description}</div>
                </td>
                <td>
                  <strong>{entry.order_id || '-'}</strong>
                  <div className="cell-meta hash-line">{entry.sale_id || entry.trace_id}</div>
                </td>
                <td>
                  <strong>{entry.customer_name || entry.customer_email || entry.customer_id || '-'}</strong>
                  <div className="cell-meta">{entry.customer_cpf || '-'} · {entry.payment_method || '-'}</div>
                </td>
                <td>
                  <strong>{entry.product_name || entry.product_id || '-'}</strong>
                  <div className="cell-meta">{entry.product_category || '-'}</div>
                </td>
                <td>{entry.channel_name || entry.channel || '-'}</td>
                <td>
                  <strong>{entry.account_code}</strong>
                  <div className="cell-meta">{entry.account_name}</div>
                </td>
                <td><span className={`side-pill ${entry.entry_side}`}>{sideLabel(entry.entry_side)}</span></td>
                <td>{quantity(entry.quantity)}</td>
                <td>{money(entry.unit_price)}</td>
                <td>{money(entry.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}