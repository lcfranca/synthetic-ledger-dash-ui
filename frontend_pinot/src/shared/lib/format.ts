import type { JournalEntry } from '../../entities/dashboard/api'

export function money(value: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
}

export function sideLabel(side: JournalEntry['entry_side']) {
  return side === 'debit' ? 'Débito' : 'Crédito'
}
