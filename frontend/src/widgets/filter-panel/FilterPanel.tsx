import type { EntryFilters, FilterOptions } from '../../entities/dashboard/api'

const TIMELINE_WINDOW_HOURS = 72
const TIMELINE_STEPS = 1000

function parseTimestamp(value?: string) {
  if (!value) {
    return undefined
  }
  const parsed = new Date(value).getTime()
  return Number.isFinite(parsed) ? parsed : undefined
}

function toLocalInputValue(value?: string) {
  if (!value) {
    return ''
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return ''
  }
  const offsetMs = parsed.getTimezoneOffset() * 60000
  return new Date(parsed.getTime() - offsetMs).toISOString().slice(0, 16)
}

function toIsoFromLocal(value: string) {
  if (!value) {
    return ''
  }
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '' : parsed.toISOString()
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function stepToTimestamp(step: number, minMs: number, maxMs: number) {
  const ratio = clamp(step, 0, TIMELINE_STEPS) / TIMELINE_STEPS
  return new Date(minMs + (maxMs - minMs) * ratio).toISOString()
}

function timestampToStep(value: string | undefined, minMs: number, maxMs: number) {
  const timestamp = parseTimestamp(value) ?? minMs
  const ratio = (timestamp - minMs) / Math.max(maxMs - minMs, 1)
  return Math.round(clamp(ratio, 0, 1) * TIMELINE_STEPS)
}

function timelineLabel(value?: string) {
  return value ? value.replace('T', ' ').replace('+00:00', ' UTC').slice(0, 16) : '-'
}

type FilterSelectProps = {
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
  allLabel?: string
}

function FilterSelect({ label, value, onChange, options, allLabel = 'Todos' }: FilterSelectProps) {
  return (
    <div className="filter-field panel-chip">
      <label>{label}</label>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{allLabel}</option>
        {options.map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
    </div>
  )
}

type Props = {
  filters: EntryFilters
  filterOptions?: FilterOptions
  setFilter: (name: keyof EntryFilters, value: string) => void
  clearFilters: () => void
}

export default function FilterPanel({ filters, filterOptions, setFilter, clearFilters }: Props) {
  const currentEndMs = Date.now()
  const explicitTimestamps = [parseTimestamp(filters.start_at), parseTimestamp(filters.end_at)].filter((value): value is number => value !== undefined)
  const timelineStartMs = explicitTimestamps.length > 0
    ? Math.min(...explicitTimestamps, currentEndMs - TIMELINE_WINDOW_HOURS * 60 * 60 * 1000)
    : currentEndMs - TIMELINE_WINDOW_HOURS * 60 * 60 * 1000
  const timelineEndMs = explicitTimestamps.length > 0 ? Math.max(...explicitTimestamps, currentEndMs) : currentEndMs
  const startStep = timestampToStep(filters.start_at, timelineStartMs, timelineEndMs)
  const endStep = timestampToStep(filters.end_at || new Date(timelineEndMs).toISOString(), timelineStartMs, timelineEndMs)

  const updateRange = (nextStartAt: string, nextEndAt: string) => {
    setFilter('as_of', '')
    setFilter('start_at', nextStartAt)
    setFilter('end_at', nextEndAt)
  }

  const handleStartInput = (value: string) => {
    const nextStartAt = toIsoFromLocal(value)
    const currentEndAt = filters.end_at || new Date(timelineEndMs).toISOString()
    if (nextStartAt && parseTimestamp(nextStartAt)! > parseTimestamp(currentEndAt)!) {
      updateRange(nextStartAt, nextStartAt)
      return
    }
    updateRange(nextStartAt, currentEndAt)
  }

  const handleEndInput = (value: string) => {
    const nextEndAt = toIsoFromLocal(value)
    const currentStartAt = filters.start_at || new Date(timelineStartMs).toISOString()
    if (nextEndAt && parseTimestamp(nextEndAt)! < parseTimestamp(currentStartAt)!) {
      updateRange(nextEndAt, nextEndAt)
      return
    }
    updateRange(currentStartAt, nextEndAt)
  }

  const handleStartSlider = (value: string) => {
    const nextStartAt = stepToTimestamp(Number(value), timelineStartMs, timelineEndMs)
    const currentEndAt = filters.end_at || new Date(timelineEndMs).toISOString()
    if (parseTimestamp(nextStartAt)! > parseTimestamp(currentEndAt)!) {
      updateRange(nextStartAt, nextStartAt)
      return
    }
    updateRange(nextStartAt, currentEndAt)
  }

  const handleEndSlider = (value: string) => {
    const nextEndAt = stepToTimestamp(Number(value), timelineStartMs, timelineEndMs)
    const currentStartAt = filters.start_at || new Date(timelineStartMs).toISOString()
    if (parseTimestamp(nextEndAt)! < parseTimestamp(currentStartAt)!) {
      updateRange(nextEndAt, nextEndAt)
      return
    }
    updateRange(currentStartAt, nextEndAt)
  }

  return (
    <section className="panel section-panel frame-panel">
      <div className="panel-title-row">
        <div>
          <div className="meta-label">Consulta operacional</div>
          <h2>Filtros da fila</h2>
        </div>
        <button className="ghost-action" onClick={clearFilters}>Resetar consulta</button>
      </div>

      <div className="filter-grid">
        <FilterSelect label="Produto" value={filters.product_name ?? ''} onChange={(value) => setFilter('product_name', value)} options={filterOptions?.product_names ?? []} />
        <FilterSelect label="Categoria" value={filters.product_category ?? ''} onChange={(value) => setFilter('product_category', value)} options={filterOptions?.product_categories ?? []} />
        <FilterSelect label="Fornecedor" value={filters.supplier_name ?? ''} onChange={(value) => setFilter('supplier_name', value)} options={filterOptions?.supplier_names ?? []} />
        <FilterSelect label="Tipo de evento" value={filters.event_type ?? ''} onChange={(value) => setFilter('event_type', value)} options={filterOptions?.event_types ?? []} />
        <FilterSelect label="Categoria contabil" value={filters.entry_category ?? ''} onChange={(value) => setFilter('entry_category', value)} options={filterOptions?.entry_categories ?? []} allLabel="Todas" />
        <FilterSelect label="Conta" value={filters.account_code ?? ''} onChange={(value) => setFilter('account_code', value)} options={filterOptions?.account_codes ?? []} allLabel="Todas" />
        <FilterSelect label="Armazem" value={filters.warehouse_id ?? ''} onChange={(value) => setFilter('warehouse_id', value)} options={filterOptions?.warehouse_ids ?? []} />
        <FilterSelect label="Canal" value={filters.channel ?? ''} onChange={(value) => setFilter('channel', value)} options={filterOptions?.channels ?? []} />
        <FilterSelect label="Origem" value={filters.ontology_source ?? ''} onChange={(value) => setFilter('ontology_source', value)} options={filterOptions?.ontology_sources ?? []} allLabel="Todas" />
        <div className="filter-field panel-chip">
          <label>Tipo de lancamento</label>
          <select value={filters.entry_side ?? ''} onChange={(event) => setFilter('entry_side', event.target.value)}>
            <option value="">Todos</option>
            <option value="debit">Debito</option>
            <option value="credit">Credito</option>
          </select>
        </div>
        <div className="time-range-panel panel-chip">
          <div className="time-range-head">
            <div>
              <label>Janela temporal</label>
              <div className="time-range-copy">A fila continua em push, mas só aceita eventos dentro do intervalo selecionado.</div>
            </div>
            <div className="time-range-status">{timelineLabel(filters.start_at)} ate {timelineLabel(filters.end_at || new Date(timelineEndMs).toISOString())}</div>
          </div>
          <div className="time-range-inputs">
            <div className="filter-field">
              <label>Inicio</label>
              <input type="datetime-local" value={toLocalInputValue(filters.start_at)} onChange={(event) => handleStartInput(event.target.value)} />
            </div>
            <div className="filter-field">
              <label>Fim</label>
              <input type="datetime-local" value={toLocalInputValue(filters.end_at || new Date(timelineEndMs).toISOString())} onChange={(event) => handleEndInput(event.target.value)} />
            </div>
          </div>
          <div className="time-range-slider-shell">
            <div className="time-range-track" />
            <div className="time-range-active" style={{ left: `${(Math.min(startStep, endStep) / TIMELINE_STEPS) * 100}%`, right: `${100 - (Math.max(startStep, endStep) / TIMELINE_STEPS) * 100}%` }} />
            <input className="time-range-slider" type="range" min="0" max={String(TIMELINE_STEPS)} value={startStep} onChange={(event) => handleStartSlider(event.target.value)} />
            <input className="time-range-slider" type="range" min="0" max={String(TIMELINE_STEPS)} value={endStep} onChange={(event) => handleEndSlider(event.target.value)} />
          </div>
          <div className="time-range-axis">
            <span>{timelineLabel(new Date(timelineStartMs).toISOString())}</span>
            <span>{timelineLabel(new Date(timelineEndMs).toISOString())}</span>
          </div>
        </div>
      </div>
    </section>
  )
}