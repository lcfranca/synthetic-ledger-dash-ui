import { useDeferredValue } from 'react'
import ReactECharts from 'echarts-for-react'
import type { BarSeriesOption, DefaultLabelFormatterCallbackParams, EChartsOption, ScatterSeriesOption } from 'echarts'
import type { AccountCatalogRow, DashboardSummary, JournalEntry, ProductCatalogRow, SalesBreakdownRow, SalesWorkspace } from '../../entities/dashboard/api'
import { compact, daysCoverage, money, percent, quantity } from '../../shared/lib/format'
import { shortTs } from '../../shared/lib/time'

type Props = {
  summary?: DashboardSummary
  entries: JournalEntry[]
  accounts: AccountCatalogRow[]
  products: ProductCatalogRow[]
  salesWorkspace?: SalesWorkspace
}

const chartText = '#f4f1ea'
const chartMuted = '#c8c3b7'
const chartGrid = 'rgba(244, 241, 234, 0.08)'
const chartLine = '#f0602c'
const chartFill = 'rgba(240, 96, 44, 0.18)'

function chartBase(): EChartsOption {
  return {
    animationDuration: 280,
    animationDurationUpdate: 220,
    textStyle: {
      color: chartText,
      fontFamily: 'IBM Plex Mono, IBM Plex Sans Condensed, sans-serif',
    },
    grid: {
      left: 44,
      right: 22,
      top: 42,
      bottom: 34,
      containLabel: true,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0b0c0d',
      borderColor: 'rgba(240, 96, 44, 0.36)',
      textStyle: { color: chartText },
    },
  }
}

function axisValueLabel(value: string) {
  return value.length > 18 ? `${value.slice(0, 18)}…` : value
}

function moneyAxis(value: number) {
  return money(value).replace('R$', '').trim()
}

function sharePercent(value: number, total: number) {
  if (total <= 0) {
    return '-'
  }
  return percent((value / total) * 100, 1)
}

function waterfallLabelFormatter(params: DefaultLabelFormatterCallbackParams) {
  const rawValue = Array.isArray(params.value) ? params.value[0] : params.value
  return money(typeof rawValue === 'number' ? rawValue : Number(rawValue ?? 0))
}

function coverageLabelFormatter(params: DefaultLabelFormatterCallbackParams) {
  return axisValueLabel(typeof params.name === 'string' ? params.name : '')
}

function buildWaterfallOption(summary?: DashboardSummary): EChartsOption {
  const income = summary?.income_statement
  const revenue = income?.revenue ?? 0
  const returns = -(income?.returns ?? 0)
  const cmv = -(income?.cmv ?? 0)
  const expenses = -(income?.operating_expenses ?? 0)
  const netIncome = income?.net_income ?? 0
  const deltas = [revenue, returns, cmv, expenses, netIncome]
  const labels = ['Receita', 'Devolucoes', 'CMV', 'Despesas', 'Lucro']

  const bases: number[] = []
  let cursor = 0
  deltas.forEach((value, index) => {
    if (index === 0 || index === deltas.length - 1) {
      bases.push(0)
      cursor = index === 0 ? value : cursor
      return
    }
    bases.push(cursor)
    cursor += value
  })

  const waterfallData = deltas.map((value, index) => ({
    value,
    itemStyle: {
      color: index === deltas.length - 1 ? '#f4f1ea' : value >= 0 ? chartLine : '#8d8d8d',
    },
  }))

  const series: BarSeriesOption[] = [
    {
      type: 'bar',
      stack: 'total',
      silent: true,
      itemStyle: { color: 'transparent', borderColor: 'transparent' },
      emphasis: { itemStyle: { color: 'transparent' } },
      data: bases,
    },
    {
      type: 'bar',
      stack: 'total',
      barMaxWidth: 40,
      label: {
        show: true,
        position: 'top',
        color: chartMuted,
        formatter: waterfallLabelFormatter,
      },
      data: waterfallData,
    },
  ]

  return {
    ...chartBase(),
    title: {
      text: 'Motor de Resultado',
      subtext: 'Waterfall DRE corrente',
      left: 14,
      top: 10,
      textStyle: { color: chartText, fontSize: 14, fontWeight: 600 },
      subtextStyle: { color: chartMuted, fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { color: chartMuted },
      axisLine: { lineStyle: { color: chartGrid } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: chartMuted, formatter: (value: number) => moneyAxis(value) },
      splitLine: { lineStyle: { color: chartGrid } },
    },
    series,
  }
}

function buildChannelOption(salesWorkspace?: SalesWorkspace): EChartsOption {
  const rows = [...(salesWorkspace?.by_channel ?? [])].slice(0, 6).reverse()
  return {
    ...chartBase(),
    title: {
      text: 'Canais e Conversao Financeira',
      subtext: 'Net sales e pedidos por canal',
      left: 14,
      top: 10,
      textStyle: { color: chartText, fontSize: 14, fontWeight: 600 },
      subtextStyle: { color: chartMuted, fontSize: 11 },
    },
    legend: {
      right: 18,
      top: 12,
      textStyle: { color: chartMuted },
    },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: chartGrid } },
      axisLabel: { color: chartMuted, formatter: (value: number) => moneyAxis(value) },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => axisValueLabel(row.label)),
      axisLabel: { color: chartMuted },
      axisLine: { lineStyle: { color: chartGrid } },
    },
    series: [
      {
        name: 'Net sales',
        type: 'bar',
        data: rows.map((row) => row.net_sales),
        barMaxWidth: 18,
        itemStyle: { color: chartLine },
      },
      {
        name: 'Pedidos',
        type: 'line',
        xAxisIndex: 0,
        smooth: true,
        symbolSize: 8,
        data: rows.map((row) => row.order_count),
        itemStyle: { color: '#f4f1ea' },
        lineStyle: { color: '#f4f1ea', width: 2 },
      },
    ],
  }
}

function buildCoverageOption(products: ProductCatalogRow[]): EChartsOption {
  const rows = [...products]
    .sort((left, right) => (right.net_revenue_amount ?? 0) - (left.net_revenue_amount ?? 0))
    .slice(0, 8)

  const series: ScatterSeriesOption[] = [
    {
      type: 'scatter',
      symbolSize: (value: number[]) => Math.max(14, Math.min(42, Number(value[2]) / 45000)),
      itemStyle: { color: chartLine, opacity: 0.82 },
      label: {
        show: true,
        position: 'top',
        color: chartMuted,
        formatter: coverageLabelFormatter,
      },
      data: rows.map((row) => ({
        name: row.product_name,
        value: [row.coverage_days ?? 0, row.net_margin_pct ?? 0, row.net_revenue_amount ?? 0],
      })),
    },
  ]

  return {
    ...chartBase(),
    title: {
      text: 'Cobertura vs Rentabilidade',
      subtext: 'Bolhas por SKU prioritario',
      left: 14,
      top: 10,
      textStyle: { color: chartText, fontSize: 14, fontWeight: 600 },
      subtextStyle: { color: chartMuted, fontSize: 11 },
    },
    xAxis: {
      type: 'value',
      name: 'Cobertura (dias)',
      nameTextStyle: { color: chartMuted },
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: chartGrid } },
    },
    yAxis: {
      type: 'value',
      name: 'Margem liquida %',
      nameTextStyle: { color: chartMuted },
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: chartGrid } },
    },
    series,
  }
}

function buildBalanceOption(summary?: DashboardSummary): EChartsOption {
  const assets = summary?.balance_sheet.assets
  const liabilities = summary?.balance_sheet.liabilities
  const equity = summary?.balance_sheet.equity
  return {
    ...chartBase(),
    title: {
      text: 'Estrutura de Capital',
      subtext: 'Ativos, passivos e patrimonio',
      left: 14,
      top: 10,
      textStyle: { color: chartText, fontSize: 14, fontWeight: 600 },
      subtextStyle: { color: chartMuted, fontSize: 11 },
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: '#0b0c0d',
      borderColor: 'rgba(240, 96, 44, 0.36)',
      textStyle: { color: chartText },
    },
    legend: {
      orient: 'vertical',
      right: 16,
      top: 'center',
      textStyle: { color: chartMuted },
    },
    series: [
      {
        type: 'pie',
        radius: ['42%', '72%'],
        center: ['34%', '56%'],
        label: { color: chartMuted, formatter: '{b}' },
        itemStyle: {
          borderColor: '#0b0c0d',
          borderWidth: 2,
        },
        data: [
          { value: assets?.cash ?? 0, name: 'Caixa', itemStyle: { color: '#f0602c' } },
          { value: assets?.bank_accounts ?? 0, name: 'Bancos', itemStyle: { color: '#c86e48' } },
          { value: assets?.inventory ?? 0, name: 'Estoque', itemStyle: { color: '#f4f1ea' } },
          { value: liabilities?.tax_payable ?? 0, name: 'Tributos', itemStyle: { color: '#8a8176' } },
          { value: liabilities?.accounts_payable ?? 0, name: 'Fornecedores', itemStyle: { color: '#6f675d' } },
          { value: equity?.current_earnings ?? 0, name: 'Patrimonio', itemStyle: { color: '#b6b0a5' } },
        ],
      },
    ],
  }
}

function buildPulseOption(entries: JournalEntry[]): EChartsOption {
  const minuteMap = new Map<string, { bucket: string; label: string; total: number; sales: number; purchases: number }>()
  entries.forEach((entry) => {
    const bucket = entry.occurred_at.slice(0, 16)
    const slot = minuteMap.get(bucket) ?? { bucket, label: entry.occurred_at.slice(11, 16), total: 0, sales: 0, purchases: 0 }
    slot.total += 1
    if (entry.ontology_event_type === 'sale') {
      slot.sales += 1
    }
    if (entry.ontology_event_type === 'purchase') {
      slot.purchases += 1
    }
    minuteMap.set(bucket, slot)
  })
  const rows = [...minuteMap.values()].sort((left, right) => left.bucket.localeCompare(right.bucket))
  return {
    ...chartBase(),
    title: {
      text: 'Pulso Operacional',
      subtext: 'Cadencia recente do stream',
      left: 14,
      top: 10,
      textStyle: { color: chartText, fontSize: 14, fontWeight: 600 },
      subtextStyle: { color: chartMuted, fontSize: 11 },
    },
    legend: { right: 18, top: 12, textStyle: { color: chartMuted } },
    xAxis: {
      type: 'category',
      data: rows.map((row) => row.label),
      axisLabel: { color: chartMuted },
      axisLine: { lineStyle: { color: chartGrid } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: chartMuted },
      splitLine: { lineStyle: { color: chartGrid } },
    },
    series: [
      {
        name: 'Eventos',
        type: 'line',
        smooth: true,
        areaStyle: { color: chartFill },
        lineStyle: { color: chartLine, width: 2 },
        itemStyle: { color: chartLine },
        data: rows.map((row) => row.total),
      },
      {
        name: 'Vendas',
        type: 'bar',
        barMaxWidth: 14,
        itemStyle: { color: '#f4f1ea' },
        data: rows.map((row) => row.sales),
      },
      {
        name: 'Compras',
        type: 'bar',
        barMaxWidth: 14,
        itemStyle: { color: '#8a8176' },
        data: rows.map((row) => row.purchases),
      },
    ],
  }
}

function buildAccountsOption(accounts: AccountCatalogRow[]): EChartsOption {
  const rows = [...accounts]
    .sort((left, right) => Math.abs(right.current_balance) - Math.abs(left.current_balance))
    .slice(0, 8)
    .reverse()
  return {
    ...chartBase(),
    title: {
      text: 'Contas de Maior Pressao',
      subtext: 'Saldos absolutos mais relevantes',
      left: 14,
      top: 10,
      textStyle: { color: chartText, fontSize: 14, fontWeight: 600 },
      subtextStyle: { color: chartMuted, fontSize: 11 },
    },
    xAxis: {
      type: 'value',
      axisLabel: { color: chartMuted, formatter: (value: number) => moneyAxis(value) },
      splitLine: { lineStyle: { color: chartGrid } },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => axisValueLabel(row.account_name)),
      axisLabel: { color: chartMuted },
      axisLine: { lineStyle: { color: chartGrid } },
    },
    series: [
      {
        type: 'bar',
        barMaxWidth: 20,
        data: rows.map((row) => ({
          value: Math.abs(row.current_balance),
          itemStyle: { color: row.current_balance >= 0 ? chartLine : '#8a8176' },
        })),
      },
    ],
  }
}

function topPaymentLabel(byPayment: SalesBreakdownRow[]) {
  const lead = byPayment[0]
  if (!lead) {
    return '-'
  }
  return axisValueLabel(lead.label)
}

export default function ObservabilityView({ summary, entries, accounts, products, salesWorkspace }: Props) {
  const deferredEntries = useDeferredValue(entries)
  const deferredAccounts = useDeferredValue(accounts)
  const deferredProducts = useDeferredValue(products)
  const deferredSalesWorkspace = useDeferredValue(salesWorkspace)
  const byPayment = deferredSalesWorkspace?.by_payment ?? []
  const byChannel = deferredSalesWorkspace?.by_channel ?? []
  const netSalesTotal = deferredSalesWorkspace?.kpis.net_sales ?? 0
  const operationalLiquidity = (summary?.balance_sheet.assets.cash ?? 0) + (summary?.balance_sheet.assets.bank_accounts ?? 0)

  const inventoryCoverage = deferredProducts.filter((product) => (product.coverage_days ?? 0) <= 7).length
  const marginSpread = deferredProducts.length > 0
    ? Math.max(...deferredProducts.map((product) => product.net_margin_pct ?? 0)) - Math.min(...deferredProducts.map((product) => product.net_margin_pct ?? 0))
    : 0
  const transactionMix = deferredEntries.reduce((acc, entry) => {
    acc[entry.ontology_event_type] = (acc[entry.ontology_event_type] ?? 0) + 1
    return acc
  }, {} as Record<string, number>)
  const restockAgenda = [...deferredProducts]
    .filter((product) => product.needs_restock || (product.coverage_days ?? 0) <= 7)
    .sort((left, right) => (right.suggested_purchase_quantity ?? 0) - (left.suggested_purchase_quantity ?? 0))
    .slice(0, 8)
  const channelScorecard = [...byChannel]
    .sort((left, right) => right.net_sales - left.net_sales)
    .slice(0, 8)
  const pressureAccounts = [...deferredAccounts]
    .sort((left, right) => Math.abs(right.current_balance) - Math.abs(left.current_balance))
    .slice(0, 8)
  const recentSignals = deferredEntries.slice(0, 8)

  return (
    <section className="section-stack">
      <section className="panel section-panel section-frame observability-command-panel">
        <div className="panel-title-row">
          <div>
            <div className="meta-label">Enterprise telemetry</div>
            <h2>Observabilidade executiva multi-camada</h2>
          </div>
          <div className="title-cluster">
            <span className="status-pill ok">Push-first</span>
            <div className="header-time compact-time">Stream vivo para margem, risco, giro e pressao de capital.</div>
          </div>
        </div>

        <div className="metric-strip observability-strip">
          <article className="metric-card accent-card panel-surface">
            <div className="metric-label">Lucro corrente</div>
            <div className="metric-value">{money(summary?.income_statement.net_income ?? 0)}</div>
            <div className="metric-helper">Margem liquida {percent(summary?.income_statement.net_margin_pct)}</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Receita monitorada</div>
            <div className="metric-value">{money(summary?.income_statement.net_revenue ?? 0)}</div>
            <div className="metric-helper">Gross profit {money(summary?.income_statement.gross_profit ?? 0)}</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Margem comercial</div>
            <div className="metric-value">{money(deferredSalesWorkspace?.kpis.gross_margin ?? 0)}</div>
            <div className="metric-helper">Margem agregada do recorte, sem depender da fita limitada de pedidos</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Liquidez operacional</div>
            <div className="metric-value">{money(operationalLiquidity)}</div>
            <div className="metric-helper">Caixa + bancos frente a settle, frete e fornecedores</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">SKUs em tensao</div>
            <div className="metric-value">{compact(inventoryCoverage)}</div>
            <div className="metric-helper">Cobertura inferior a 7 dias</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Dispersao de margem</div>
            <div className="metric-value">{percent(marginSpread, 1)}</div>
            <div className="metric-helper">Amplitude entre melhor e pior SKU</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Ordens rastreadas</div>
            <div className="metric-value">{compact(deferredSalesWorkspace?.kpis.order_count ?? 0)}</div>
            <div className="metric-helper">Ticket medio {money(deferredSalesWorkspace?.kpis.average_ticket ?? 0)}</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Pagamento lider</div>
            <div className="metric-value small-text">{topPaymentLabel(byPayment)}</div>
            <div className="metric-helper">{byPayment[0] ? `${money(byPayment[0].net_sales)} · ${sharePercent(byPayment[0].net_sales, netSalesTotal)}` : 'Sem composicao consolidada nesta janela'}</div>
          </article>
          <article className="metric-card panel-surface">
            <div className="metric-label">Mix do stream</div>
            <div className="metric-value">{compact(deferredEntries.length)}</div>
            <div className="metric-helper">Sale {compact(transactionMix.sale ?? 0)} · Purchase {compact(transactionMix.purchase ?? 0)}</div>
          </article>
        </div>

        <div className="panel-subcopy">O conjunto abaixo privilegia governanca gerencial: motor de resultado, alocacao de capital, elasticidade de canal, tensao de estoque, pulso operacional e concentracao contabil. Pagamentos e KPIs comerciais agora usam agregados cumulativos do backend no recorte selecionado, sem depender da lista parcial de pedidos exibidos.</div>
      </section>

      <section className="observability-grid">
        <article className="panel section-panel section-frame observability-chart-card">
          <ReactECharts option={buildWaterfallOption(summary)} notMerge lazyUpdate className="observability-chart" />
        </article>
        <article className="panel section-panel section-frame observability-chart-card">
          <ReactECharts option={buildBalanceOption(summary)} notMerge lazyUpdate className="observability-chart" />
        </article>
        <article className="panel section-panel section-frame observability-chart-card">
          <ReactECharts option={buildChannelOption(deferredSalesWorkspace)} notMerge lazyUpdate className="observability-chart" />
        </article>
        <article className="panel section-panel section-frame observability-chart-card">
          <ReactECharts option={buildCoverageOption(deferredProducts)} notMerge lazyUpdate className="observability-chart" />
        </article>
        <article className="panel section-panel section-frame observability-chart-card observability-chart-card-wide">
          <ReactECharts option={buildPulseOption(deferredEntries)} notMerge lazyUpdate className="observability-chart" />
        </article>
        <article className="panel section-panel section-frame observability-chart-card">
          <ReactECharts option={buildAccountsOption(deferredAccounts)} notMerge lazyUpdate className="observability-chart" />
        </article>
      </section>

      <section className="observability-table-grid">
        <article className="panel section-panel section-frame observability-table-card">
          <div className="panel-title-row compact-panel-title">
            <div>
              <div className="meta-label">Collections</div>
              <h3>Trilhos de pagamento</h3>
            </div>
            <div className="header-time compact-time">Receita acumulada por meio de pagamento no recorte atual.</div>
          </div>
          <div className="table-wrap table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Pagamento</th>
                  <th>Net sales</th>
                  <th>Pedidos</th>
                  <th>Share</th>
                </tr>
              </thead>
              <tbody>
                {byPayment.length ? byPayment.map((row) => (
                  <tr key={row.label}>
                    <td><strong>{row.label}</strong></td>
                    <td>{money(row.net_sales)}</td>
                    <td>{compact(row.order_count)}</td>
                    <td>{sharePercent(row.net_sales, netSalesTotal)}</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={4}>Sem consolidacao de pagamento disponivel nesta janela.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel section-panel section-frame observability-table-card">
          <div className="panel-title-row compact-panel-title">
            <div>
              <div className="meta-label">Commercial scorecard</div>
              <h3>Canais em execucao</h3>
            </div>
            <div className="header-time compact-time">Canal, volume, pedidos e ticket medio efetivo.</div>
          </div>
          <div className="table-wrap table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Canal</th>
                  <th>Net sales</th>
                  <th>Pedidos</th>
                  <th>Ticket</th>
                </tr>
              </thead>
              <tbody>
                {channelScorecard.map((row) => (
                  <tr key={row.label}>
                    <td><strong>{row.label}</strong></td>
                    <td>{money(row.net_sales)}</td>
                    <td>{compact(row.order_count)}</td>
                    <td>{money(row.order_count ? row.net_sales / row.order_count : 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel section-panel section-frame observability-table-card">
          <div className="panel-title-row compact-panel-title">
            <div>
              <div className="meta-label">Supply control</div>
              <h3>Agenda de ressuprimento</h3>
            </div>
            <div className="header-time compact-time">SKUs com menor folga operacional e maior necessidade de compra.</div>
          </div>
          <div className="table-wrap table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Cobertura</th>
                  <th>Margem</th>
                  <th>Compra sugerida</th>
                </tr>
              </thead>
              <tbody>
                {restockAgenda.map((product) => (
                  <tr key={product.product_id}>
                    <td>
                      <strong>{product.product_name}</strong>
                      <div className="cell-meta">{product.suggested_purchase_supplier_name}</div>
                    </td>
                    <td>{daysCoverage(product.coverage_days)}</td>
                    <td>{percent(product.net_margin_pct)}</td>
                    <td>{quantity(product.suggested_purchase_quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel section-panel section-frame observability-table-card">
          <div className="panel-title-row compact-panel-title">
            <div>
              <div className="meta-label">Ledger watch</div>
              <h3>Sinais recentes do razao</h3>
            </div>
            <div className="header-time compact-time">Amostra viva do append-only contabil ordenada por evento mais recente.</div>
          </div>
          <div className="table-wrap table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Horario</th>
                  <th>Evento</th>
                  <th>Conta</th>
                  <th>Valor</th>
                </tr>
              </thead>
              <tbody>
                {recentSignals.map((entry) => (
                  <tr key={entry.entry_id}>
                    <td>{shortTs(entry.occurred_at)}</td>
                    <td>
                      <strong>{entry.ontology_event_type}</strong>
                      <div className="cell-meta">{entry.product_name || entry.channel_name || '-'}</div>
                    </td>
                    <td>
                      <strong>{entry.account_name}</strong>
                      <div className="cell-meta">{entry.entry_side} · {entry.entry_category}</div>
                    </td>
                    <td>{money(entry.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <section className="panel section-panel section-frame observability-footnote-panel">
        <div className="panel-title-row compact-panel-title">
          <div>
            <div className="meta-label">Executive readout</div>
            <h3>Indicadores imediatos para a gestao</h3>
          </div>
        </div>
        <div className="observability-readout-grid">
          <div className="panel-surface observability-readout-card">
            <div className="metric-label">Liquidez operacional</div>
            <strong>{money((summary?.balance_sheet.assets.cash ?? 0) + (summary?.balance_sheet.assets.bank_accounts ?? 0))}</strong>
            <div className="cell-meta">Caixa + bancos sustentando settle, frete e fornecedores.</div>
          </div>
          <div className="panel-surface observability-readout-card">
            <div className="metric-label">Estoque em cobertura</div>
            <strong>{quantity(deferredProducts.filter((product) => (product.coverage_days ?? 0) >= 5).length)}</strong>
            <div className="cell-meta">SKUs com folga operacional aceitavel para o ritmo atual.</div>
          </div>
          <div className="panel-surface observability-readout-card">
            <div className="metric-label">Ticket comercial</div>
            <strong>{money(deferredSalesWorkspace?.kpis.average_ticket ?? 0)}</strong>
            <div className="cell-meta">Leitura sintetica para ritmo de monetizacao do mix.</div>
          </div>
          <div className="panel-surface observability-readout-card">
            <div className="metric-label">Cobertura media</div>
            <strong>{daysCoverage(deferredProducts.length ? deferredProducts.reduce((acc, product) => acc + (product.coverage_days ?? 0), 0) / deferredProducts.length : 0)}</strong>
            <div className="cell-meta">Media de folego entre venda, estoque e ressuprimento.</div>
          </div>
          <div className="panel-surface observability-readout-card">
            <div className="metric-label">Contas sob pressao</div>
            <strong>{compact(pressureAccounts.length)}</strong>
            <div className="cell-meta">Top contas por saldo absoluto para leitura imediata de pressao financeira.</div>
          </div>
          <div className="panel-surface observability-readout-card">
            <div className="metric-label">Pagamento dominante</div>
            <strong>{topPaymentLabel(byPayment)}</strong>
            <div className="cell-meta">Share lider {byPayment[0] ? sharePercent(byPayment[0].net_sales, netSalesTotal) : '-' } da receita liquida monitorada.</div>
          </div>
        </div>
      </section>
    </section>
  )
}