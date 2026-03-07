export type ViewId = 'queue' | 'accounting' | 'accounts' | 'products'

export const dashboardViews: Array<{ id: ViewId; label: string; eyebrow: string; code: string }> = [
  { id: 'queue', label: 'Fila de eventos', eyebrow: 'Streaming', code: '01' },
  { id: 'accounting', label: 'BP + DRE', eyebrow: 'Financeiro', code: '02' },
  { id: 'accounts', label: 'Catalogo de contas', eyebrow: 'Audit docs', code: '03' },
  { id: 'products', label: 'Catalogo de produtos', eyebrow: 'Stock pulse', code: '04' },
]