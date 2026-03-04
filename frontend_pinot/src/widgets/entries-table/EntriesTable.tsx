import type { DashboardSummary } from '../../entities/dashboard/api'
import { money, sideLabel } from '../../shared/lib/format'

type Props = {
  summary?: DashboardSummary | null
}

export default function EntriesTable({ summary }: Props) {
  return (
    <section className="panel">
      <h2>Fila de Lançamentos Débito/Crédito</h2>
      <div className="table-wrap">
        <table className="ledger-table">
          <thead>
            <tr>
              {['Ocorrido em', 'Tipo', 'Conta', 'Categoria', 'Produto', 'Fornecedor', 'Canal', 'Valor', 'Origem Ontológica', 'Descrição Ontológica', 'Event ID', 'Trace ID', 'Hash'].map((header) => (
                <th key={header}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(summary?.entries ?? []).map((entry) => (
              <tr key={entry.entry_id}>
                <td>{entry.occurred_at}</td>
                <td>{sideLabel(entry.entry_side)}</td>
                <td>{entry.account_code} - {entry.account_name}</td>
                <td>{entry.entry_category}</td>
                <td>{entry.product_id}</td>
                <td>{entry.supplier_id ?? '-'}</td>
                <td>{entry.channel}</td>
                <td>{money(entry.amount)}</td>
                <td>{entry.ontology_event_type} ({entry.ontology_source})</td>
                <td>{entry.ontology_description}</td>
                <td className="mono-text">{entry.event_id}</td>
                <td className="mono-text">{entry.trace_id}</td>
                <td className="mono-text">{entry.source_payload_hash.slice(0, 20)}...</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
