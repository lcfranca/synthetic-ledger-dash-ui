import type { DashboardSummary } from '../../entities/dashboard/api'
import { money, percent } from '../../shared/lib/format'
import { shortTs } from '../../shared/lib/time'

type Props = {
  summary?: DashboardSummary
}

export default function AccountingView({ summary }: Props) {
  return (
    <section className="section-stack">
      <section className="panel section-panel frame-panel cinematic-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Posicao patrimonial</div>
            <h2>Balanco patrimonial</h2>
          </div>
          <div className="header-time compact-time">{shortTs(summary?.timestamp)}</div>
        </div>

        <div className="accounting-grid">
          <article className="statement-card panel-surface">
            <h3>Ativos</h3>
            <dl>
              <div><dt>Caixa</dt><dd>{summary ? money(summary.balance_sheet.assets.cash) : '-'}</dd></div>
              <div><dt>Bancos</dt><dd>{summary ? money(summary.balance_sheet.assets.bank_accounts) : '-'}</dd></div>
              <div><dt>Impostos recuperaveis</dt><dd>{summary ? money(summary.balance_sheet.assets.recoverable_tax) : '-'}</dd></div>
              <div><dt>Estoque</dt><dd>{summary ? money(summary.balance_sheet.assets.inventory) : '-'}</dd></div>
              <div className="statement-total"><dt>Total ativo</dt><dd>{summary ? money(summary.balance_sheet.assets.total) : '-'}</dd></div>
            </dl>
          </article>
          <article className="statement-card panel-surface">
            <h3>Passivos e patrimonio</h3>
            <dl>
              <div><dt>Fornecedores</dt><dd>{summary ? money(summary.balance_sheet.liabilities.accounts_payable) : '-'}</dd></div>
              <div><dt>Impostos a recolher</dt><dd>{summary ? money(summary.balance_sheet.liabilities.tax_payable) : '-'}</dd></div>
              <div><dt>Total passivo</dt><dd>{summary ? money(summary.balance_sheet.liabilities.total) : '-'}</dd></div>
              <div><dt>Lucros correntes</dt><dd>{summary ? money(summary.balance_sheet.equity.current_earnings) : '-'}</dd></div>
              <div className="statement-total"><dt>Passivo + PL</dt><dd>{summary ? money(summary.balance_sheet.total_liabilities_and_equity) : '-'}</dd></div>
            </dl>
          </article>
        </div>
      </section>

      <section className="panel section-panel frame-panel cinematic-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Resultado operacional</div>
            <h2>Demonstracao de resultado</h2>
          </div>
          <div className={`difference-badge ${(summary?.balance_sheet.difference ?? 0) === 0 ? 'good' : 'warn'}`}>
            Fechamento: {summary ? money(summary.balance_sheet.difference) : '-'}
          </div>
        </div>

        <div className="accounting-grid">
          <article className="statement-card wide-card panel-surface">
            <dl>
              <div><dt>Receita bruta</dt><dd>{summary ? money(summary.income_statement.revenue) : '-'}</dd></div>
              <div><dt>Devolucoes</dt><dd>{summary ? money(summary.income_statement.returns) : '-'}</dd></div>
              <div><dt>Indice de devolucao</dt><dd>{summary ? percent(summary.income_statement.return_rate_pct) : '-'}</dd></div>
              <div><dt>Receita liquida</dt><dd>{summary ? money(summary.income_statement.net_revenue) : '-'}</dd></div>
              <div><dt>CMV</dt><dd>{summary ? money(summary.income_statement.cmv) : '-'}</dd></div>
              <div><dt>Lucro bruto</dt><dd>{summary ? money(summary.income_statement.gross_profit) : '-'}</dd></div>
              <div><dt>Margem bruta</dt><dd>{summary ? percent(summary.income_statement.gross_margin_pct) : '-'}</dd></div>
              <div><dt>Comissoes</dt><dd>{summary ? money(summary.income_statement.marketplace_fees) : '-'}</dd></div>
              <div><dt>Frete outbound</dt><dd>{summary ? money(summary.income_statement.freight_out) : '-'}</dd></div>
              <div><dt>Tarifas bancarias</dt><dd>{summary ? money(summary.income_statement.bank_fees) : '-'}</dd></div>
              <div><dt>Outras despesas</dt><dd>{summary ? money(summary.income_statement.other_expenses) : '-'}</dd></div>
              <div><dt>Despesa operacional / RL</dt><dd>{summary ? percent(summary.income_statement.expense_ratio_pct) : '-'}</dd></div>
              <div><dt>Margem liquida</dt><dd>{summary ? percent(summary.income_statement.net_margin_pct) : '-'}</dd></div>
              <div className="statement-total"><dt>Resultado liquido</dt><dd>{summary ? money(summary.income_statement.net_income) : '-'}</dd></div>
            </dl>
          </article>
        </div>
      </section>
    </section>
  )
}