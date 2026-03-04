import { useEffect, useState, type CSSProperties } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchFilterOptions, fetchSummary, type DashboardSummary, type EntryFilters, type JournalEntry } from './api'

function money(value: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
}

function sideLabel(side: JournalEntry['entry_side']) {
  return side === 'debit' ? 'Débito' : 'Crédito'
}

export default function App() {
  const [filters, setFilters] = useState<EntryFilters>({})

  const { data } = useQuery({
    queryKey: ['summary', filters],
    queryFn: () => fetchSummary(filters),
    refetchInterval: 5000
  })

  const { data: filterOptions } = useQuery({
    queryKey: ['filter-options'],
    queryFn: fetchFilterOptions,
    staleTime: 30000
  })

  const [live, setLive] = useState<DashboardSummary | null>(null)

  useEffect(() => {
    const ws = new WebSocket(`${window.location.origin.replace('http', 'ws')}/ws/metrics`)
    ws.onmessage = (event) => setLive(JSON.parse(event.data))
    return () => ws.close()
  }, [])

  const hasActiveFilters = Object.values(filters).some((value) => Boolean(value))
  const summary = hasActiveFilters ? data : (live ?? data)

  const setFilter = (name: keyof EntryFilters, value: string) => {
    setFilters((current) => ({ ...current, [name]: value }))
  }

  const clearFilters = () => setFilters({})

  const appStyle: CSSProperties = {
    minHeight: '100vh',
    background: '#070b11',
    color: '#dbe6f4',
    fontFamily: 'Inter, Segoe UI, system-ui, sans-serif',
    padding: '20px 24px 28px'
  }

  const panelStyle: CSSProperties = {
    background: 'linear-gradient(180deg, rgba(15,20,30,0.96) 0%, rgba(10,14,21,0.96) 100%)',
    border: '1px solid #1f2d3f',
    borderRadius: 6,
    boxShadow: 'inset 0 0 0 1px rgba(77,106,139,0.2)',
    padding: 14,
    marginBottom: 14
  }

  const metricGrid: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: 10,
    marginTop: 10
  }

  const metricCard: CSSProperties = {
    border: '1px solid #223247',
    borderRadius: 4,
    background: '#0c131d',
    padding: '10px 12px'
  }

  const inputStyle: CSSProperties = {
    background: '#0b1119',
    color: '#dbe6f4',
    border: '1px solid #27374d',
    borderRadius: 4,
    padding: '8px 10px',
    fontSize: 13
  }

  const labelStyle: CSSProperties = {
    fontSize: 11,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    color: '#7f97b3',
    marginBottom: 4,
    display: 'block'
  }

  return (
    <main style={appStyle}>
      <header style={{ ...panelStyle, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 11, color: '#8ca5c1', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            Synthetic Ledger Control Center
          </div>
          <h1 style={{ margin: '6px 0 0', fontSize: 26, letterSpacing: '0.02em' }}>Dashboard Escudo Financeiro</h1>
        </div>
        <div style={{ textAlign: 'right', fontSize: 12, color: '#93aac3' }}>
          <div>Atualização: {summary?.timestamp ?? '-'}</div>
          <div>As Of: {summary?.as_of ?? '-'}</div>
        </div>
      </header>

      <section style={panelStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ margin: 0, fontSize: 15, letterSpacing: '0.06em', textTransform: 'uppercase' }}>Filtros Operacionais</h2>
          <button
            onClick={clearFilters}
            style={{ ...inputStyle, cursor: 'pointer', padding: '8px 12px', textTransform: 'uppercase', letterSpacing: '0.08em' }}
          >
            Limpar filtros
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
          <div>
            <label style={labelStyle}>Produto</label>
            <select style={inputStyle} value={filters.product_id ?? ''} onChange={(e) => setFilter('product_id', e.target.value)}>
              <option value="">Todos</option>
              {(filterOptions?.product_ids ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Fornecedor</label>
            <select style={inputStyle} value={filters.supplier_id ?? ''} onChange={(e) => setFilter('supplier_id', e.target.value)}>
              <option value="">Todos</option>
              {(filterOptions?.supplier_ids ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Tipo de Evento</label>
            <select style={inputStyle} value={filters.event_type ?? ''} onChange={(e) => setFilter('event_type', e.target.value)}>
              <option value="">Todos</option>
              {(filterOptions?.event_types ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Categoria Lançamento</label>
            <select style={inputStyle} value={filters.entry_category ?? ''} onChange={(e) => setFilter('entry_category', e.target.value)}>
              <option value="">Todas</option>
              {(filterOptions?.entry_categories ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Conta Contábil</label>
            <select style={inputStyle} value={filters.account_code ?? ''} onChange={(e) => setFilter('account_code', e.target.value)}>
              <option value="">Todas</option>
              {(filterOptions?.account_codes ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Armazém</label>
            <select style={inputStyle} value={filters.warehouse_id ?? ''} onChange={(e) => setFilter('warehouse_id', e.target.value)}>
              <option value="">Todos</option>
              {(filterOptions?.warehouse_ids ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Tipo Lançamento</label>
            <select style={inputStyle} value={filters.entry_side ?? ''} onChange={(e) => setFilter('entry_side', e.target.value)}>
              <option value="">Todos</option>
              <option value="debit">Débito</option>
              <option value="credit">Crédito</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>Fonte Ontológica</label>
            <select style={inputStyle} value={filters.ontology_source ?? ''} onChange={(e) => setFilter('ontology_source', e.target.value)}>
              <option value="">Todas</option>
              {(filterOptions?.ontology_sources ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Canal</label>
            <select style={inputStyle} value={filters.channel ?? ''} onChange={(e) => setFilter('channel', e.target.value)}>
              <option value="">Todos</option>
              {(filterOptions?.channels ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>As Of (Time-travel)</label>
            <input
              style={inputStyle}
              type="datetime-local"
              value={filters.as_of ?? ''}
              onChange={(e) => setFilter('as_of', e.target.value)}
            />
          </div>
        </div>
      </section>

      <section style={panelStyle}>
        <h2 style={{ margin: 0, fontSize: 15, letterSpacing: '0.06em', textTransform: 'uppercase' }}>KPIs Contábeis</h2>
        <div style={metricGrid}>
          <article style={metricCard}>
            <div style={{ fontSize: 11, color: '#8aa0bb', textTransform: 'uppercase' }}>Caixa</div>
            <div style={{ fontSize: 20, marginTop: 4 }}>{summary ? money(summary.balance_sheet.assets.cash) : '-'}</div>
          </article>
          <article style={metricCard}>
            <div style={{ fontSize: 11, color: '#8aa0bb', textTransform: 'uppercase' }}>Estoque</div>
            <div style={{ fontSize: 20, marginTop: 4 }}>{summary ? money(summary.balance_sheet.assets.inventory) : '-'}</div>
          </article>
          <article style={metricCard}>
            <div style={{ fontSize: 11, color: '#8aa0bb', textTransform: 'uppercase' }}>Receita</div>
            <div style={{ fontSize: 20, marginTop: 4 }}>{summary ? money(summary.income_statement.revenue) : '-'}</div>
          </article>
          <article style={metricCard}>
            <div style={{ fontSize: 11, color: '#8aa0bb', textTransform: 'uppercase' }}>CMV</div>
            <div style={{ fontSize: 20, marginTop: 4 }}>{summary ? money(summary.income_statement.cmv) : '-'}</div>
          </article>
          <article style={metricCard}>
            <div style={{ fontSize: 11, color: '#8aa0bb', textTransform: 'uppercase' }}>Resultado Líquido</div>
            <div style={{ fontSize: 20, marginTop: 4 }}>{summary ? money(summary.income_statement.net_income) : '-'}</div>
          </article>
        </div>
      </section>

      <section style={panelStyle}>
        <h2 style={{ margin: '0 0 8px', fontSize: 15, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          Fila de Lançamentos Débito/Crédito
        </h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'separate', borderSpacing: 0, width: '100%', minWidth: 1700, fontSize: 12 }}>
            <thead>
              <tr>
                {['Ocorrido em', 'Tipo', 'Conta', 'Categoria', 'Produto', 'Fornecedor', 'Canal', 'Valor', 'Origem Ontológica', 'Descrição Ontológica', 'Event ID', 'Trace ID', 'Hash'].map((header) => (
                  <th key={header} style={{ textAlign: 'left', padding: '9px 10px', borderBottom: '1px solid #233348', color: '#88a0ba', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500 }}>
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(summary?.entries ?? []).map((entry) => (
                <tr key={entry.entry_id} style={{ background: 'rgba(11,16,24,0.85)' }}>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{entry.occurred_at}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{sideLabel(entry.entry_side)}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{entry.account_code} - {entry.account_name}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{entry.entry_category}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{entry.product_id}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{entry.supplier_id ?? '-'}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{entry.channel}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{money(entry.amount)}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{entry.ontology_event_type} ({entry.ontology_source})</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b' }}>{entry.ontology_description}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b', color: '#8ba6c5' }}>{entry.event_id}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b', color: '#8ba6c5' }}>{entry.trace_id}</td>
                  <td style={{ padding: '8px 10px', borderBottom: '1px solid #1d2a3b', color: '#8ba6c5' }}>{entry.source_payload_hash.slice(0, 20)}...</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}
