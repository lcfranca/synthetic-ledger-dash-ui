import type { DashboardSummary, JournalEntry } from '../../entities/dashboard/api'
import { compact, money, quantity, sideLabel } from '../../shared/lib/format'
import { shortTs } from '../../shared/lib/time'

type Props = {
  summary?: DashboardSummary
  entries: JournalEntry[]
  isRealtimePaused: boolean
  bufferedEventCount: number
  onToggleRealtime: () => void
}

export default function QueueView({ summary, entries, isRealtimePaused, bufferedEventCount, onToggleRealtime }: Props) {
  const debits = entries.filter((item) => item.entry_side === 'debit').length
  const credits = entries.filter((item) => item.entry_side === 'credit').length
  const uniqueAccounts = new Set(entries.map((item) => item.account_code)).size
  const eventMix = Object.entries(entries.reduce<Record<string, number>>((acc, entry) => {
    acc[entry.ontology_event_type] = (acc[entry.ontology_event_type] ?? 0) + 1
    return acc
  }, {})).sort((left, right) => right[1] - left[1]).slice(0, 6)
  const largestAccounts = Object.entries(entries.reduce<Record<string, number>>((acc, entry) => {
    acc[entry.account_code] = (acc[entry.account_code] ?? 0) + entry.amount
    return acc
  }, {})).sort((left, right) => right[1] - left[1]).slice(0, 6)

  return (
    <section className="section-stack">
      <section className="panel section-panel section-frame queue-command-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Accounting ledger rail</div>
            <h2>Lançamentos Contábeis</h2>
          </div>
          <div className="title-cluster">
            <button type="button" className={`status-pill status-pill-toggle ${isRealtimePaused ? 'warn' : 'ok'}`} onClick={onToggleRealtime}>
              {isRealtimePaused ? 'Congelado' : 'Continuo'}
            </button>
            <div className="header-time compact-time">{shortTs(summary?.timestamp)}</div>
          </div>
        </div>

        <div className="panel-subcopy">
          Navegação estável para auditoria operacional. Quando pausado, o stream congela a superfície atual e retoma depois aplicando o buffer acumulado.
          {isRealtimePaused && bufferedEventCount > 0 ? ` ${compact(bufferedEventCount)} eventos aguardando retomada.` : ''}
        </div>

        <div className="metric-strip compact-strip audit-strip">
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Lançamentos visíveis</div>
            <div className="metric-value">{compact(entries.length)}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Débitos</div>
            <div className="metric-value">{compact(debits)}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Créditos</div>
            <div className="metric-value">{compact(credits)}</div>
          </article>
          <article className="metric-card compact-card panel-surface">
            <div className="metric-label">Contas tocadas</div>
            <div className="metric-value">{compact(uniqueAccounts)}</div>
          </article>
        </div>
      </section>

      <section className="panel section-panel section-frame queue-ledger-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Ledger log</div>
            <h2>Rastro auditável de lançamentos</h2>
          </div>
          <div className="header-time compact-time">Evento, documento, conta, centro operacional, quantidade, valor e rastro técnico.</div>
        </div>

        <div className="table-wrap table-shell">
          <table className="data-table">
            <thead>
              <tr>
                <th>Horário</th>
                <th>Evento</th>
                <th>Documento</th>
                <th>Conta</th>
                <th>Lado</th>
                <th>Centro operacional</th>
                <th>Qtd.</th>
                <th>Unit.</th>
                <th>Valor</th>
                <th>Rastro</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.entry_id}>
                  <td>{shortTs(entry.occurred_at)}</td>
                  <td>
                    <strong>{entry.ontology_event_type}</strong>
                    <div className="cell-meta">{entry.ontology_source} · {entry.ontology_description}</div>
                  </td>
                  <td>
                    <strong>{entry.order_id || '-'}</strong>
                    <div className="cell-meta">rev {entry.revision} · entry {entry.entry_id.slice(0, 8)}</div>
                  </td>
                  <td>
                    <strong>{entry.account_code}</strong>
                    <div className="cell-meta">{entry.account_name} · {entry.account_role}</div>
                  </td>
                  <td><span className={`side-pill ${entry.entry_side}`}>{sideLabel(entry.entry_side)}</span></td>
                  <td>
                    <strong>{entry.product_name || entry.product_id || '-'}</strong>
                    <div className="cell-meta">{entry.warehouse_name} · {entry.channel_name || entry.channel || '-'}</div>
                  </td>
                  <td>{quantity(entry.quantity)}</td>
                  <td>{money(entry.unit_price)}</td>
                  <td>{money(entry.amount)}</td>
                  <td>
                    <strong>{entry.event_id.slice(0, 8)}</strong>
                    <div className="cell-meta hash-line">trace {entry.trace_id} · hash {entry.source_payload_hash.slice(0, 12)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="dual-insight-grid">
        <article className="panel section-panel section-frame">
          <div className="panel-title-row compact-panel-title">
            <div>
              <div className="meta-label">Ontologia</div>
              <h3>Mix de eventos</h3>
            </div>
          </div>
          <div className="breakdown-list">
            {eventMix.map(([label, value]) => (
              <div key={label} className="breakdown-row">
                <span>{label}</span>
                <strong>{compact(value)}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="panel section-panel section-frame">
          <div className="panel-title-row compact-panel-title">
            <div>
              <div className="meta-label">Contas</div>
              <h3>Maior pressão financeira</h3>
            </div>
          </div>
          <div className="breakdown-list">
            {largestAccounts.map(([label, value]) => (
              <div key={label} className="breakdown-row">
                <span>{label}</span>
                <strong>{money(value)}</strong>
              </div>
            ))}
          </div>
        </article>
      </section>
    </section>
  )
}