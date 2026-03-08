import { useMemo, useState } from 'react'
import type { EntryFilters } from '../../../entities/dashboard/api'

export function useEntryFilters<TFilters extends Partial<EntryFilters> = EntryFilters>() {
  const [filters, setFilters] = useState<TFilters>({} as TFilters)

  const hasActiveFilters = useMemo(
    () => Object.values(filters).some((value) => Boolean(value)),
    [filters],
  )

  const setFilter = (name: keyof TFilters, value: string) => {
    setFilters((current) => ({ ...current, [name]: value }))
  }

  const clearFilters = () => setFilters({} as TFilters)

  return { filters, setFilter, clearFilters, hasActiveFilters }
}