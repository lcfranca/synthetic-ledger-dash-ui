import type { AccountCatalogRow } from '../../entities/dashboard/api'
import { money } from '../../shared/lib/format'

type Props = {
  accounts: AccountCatalogRow[]
}

export default function AccountsView({ accounts }: Props) {
  return (
    <section className="panel section-panel frame-panel cinematic-panel">
      <div className="panel-title-row">
        <div>
          <div className="meta-label">Plano contabil</div>
          <h2>Inventario de contas</h2>
        </div>
        <div className="header-time compact-time">{accounts.length} contas</div>
      </div>

      <div className="table-wrap table-shell">
        <table className="data-table">
          <thead>
            <tr>
              <th>Conta</th>
              <th>Papel</th>
              <th>Secao</th>
              <th>Grupo</th>
              <th>Saldo</th>
              <th>Lancamentos</th>
              <th>Documentacao</th>
              <th>Uso</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((account) => (
              <tr key={account.account_code}>
                <td>
                  <strong>{account.account_code}</strong>
                  <div className="cell-meta">{account.account_name}</div>
                </td>
                <td>{account.account_role}</td>
                <td>{account.statement_section}</td>
                <td>{account.financial_statement_group}</td>
                <td>{money(account.current_balance)}</td>
                <td>{account.entry_count}</td>
                <td>{account.documentation}</td>
                <td>{account.usage_notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}