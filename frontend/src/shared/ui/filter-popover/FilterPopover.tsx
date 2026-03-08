import * as Popover from '@radix-ui/react-popover'
import { useQuery } from '@tanstack/react-query'
import { Check, ChevronsUpDown, Search, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { fetchFilterSearch } from '../../../entities/dashboard/api'

type RemoteField = 'customer_name' | 'customer_cpf' | 'customer_email' | 'sale_id' | 'order_id'

type Props = {
  label: string
  value: string
  placeholder: string
  onChange: (value: string) => void
  options?: string[]
  allLabel?: string
  searchPlaceholder?: string
  remoteField?: RemoteField
}

export default function FilterPopover({
  label,
  value,
  placeholder,
  onChange,
  options = [],
  allLabel = 'Todos',
  searchPlaceholder = 'Buscar valor',
  remoteField,
}: Props) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')

  const remoteQuery = useQuery({
    queryKey: ['filter-popover-search', remoteField, search],
    queryFn: () => fetchFilterSearch(remoteField!, search),
    enabled: open && Boolean(remoteField) && search.trim().length >= 2,
    staleTime: 10000,
  })

  const localOptions = useMemo(() => {
    if (remoteField) {
      return remoteQuery.data ?? []
    }
    const term = search.trim().toLowerCase()
    if (!term) {
      return options.slice(0, 80)
    }
    return options.filter((item) => item.toLowerCase().includes(term)).slice(0, 80)
  }, [options, remoteField, remoteQuery.data, search])

  return (
    <div className="filter-block">
      <div className="filter-block-label">{label}</div>
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger asChild>
          <button type="button" className={`filter-trigger ${value ? 'is-active' : ''}`}>
            <span className="filter-trigger-text">{value || placeholder}</span>
            <ChevronsUpDown size={14} />
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content className="filter-popover" sideOffset={8} align="start">
            <div className="filter-popover-head">
              <strong>{label}</strong>
              <button type="button" className="filter-inline-action" onClick={() => { onChange(''); setSearch('') }}>
                <X size={12} /> limpar
              </button>
            </div>
            <div className="filter-search-shell">
              <Search size={14} />
              <input
                autoFocus
                type="search"
                value={search}
                placeholder={searchPlaceholder}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
            <div className="filter-options-list">
              <button type="button" className={`filter-option ${value === '' ? 'selected' : ''}`} onClick={() => { onChange(''); setOpen(false) }}>
                <span>{allLabel}</span>
                {value === '' ? <Check size={14} /> : null}
              </button>
              {localOptions.map((item) => (
                <button type="button" key={item} className={`filter-option ${value === item ? 'selected' : ''}`} onClick={() => { onChange(item); setOpen(false) }}>
                  <span>{item}</span>
                  {value === item ? <Check size={14} /> : null}
                </button>
              ))}
              {localOptions.length === 0 ? <div className="filter-empty-state">Nenhum valor encontrado.</div> : null}
            </div>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
    </div>
  )
}