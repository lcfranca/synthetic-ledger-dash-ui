import type { JournalEntry } from '../../entities/dashboard/api'

export function money(value: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value ?? 0))
}

export function quantity(value: number) {
  return new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 3 }).format(Number(value ?? 0))
}

export function compact(value: number) {
  return new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 }).format(Number(value ?? 0))
}

export function percent(value?: number | null, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-'
  }
  return `${new Intl.NumberFormat('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value ?? 0))}%`
}

export function daysCoverage(value?: number | null) {
  if (value === null || value === undefined) {
    return '-'
  }
  return `${new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 1 }).format(Number(value ?? 0))} dias`
}

export function sideLabel(side: JournalEntry['entry_side']) {
  return side === 'debit' ? 'Debito' : 'Credito'
}
