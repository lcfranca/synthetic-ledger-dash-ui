import { useMemo, useState } from 'react'
import type { EntryFilters } from '../../../entities/dashboard/api'

export function useEntryFilters() {
  const [filters, setFilters] = useState<EntryFilters>({})

  const hasActiveFilters = useMemo(
    () => Object.values(filters).some((value) => Boolean(value)),
    [filters],
  )

  const setFilter = (name: keyof EntryFilters, value: string) => {
    setFilters((current) => ({ ...current, [name]: value }))
  }

  const clearFilters = () => setFilters({})

  return { filters, setFilter, clearFilters, hasActiveFilters }
}