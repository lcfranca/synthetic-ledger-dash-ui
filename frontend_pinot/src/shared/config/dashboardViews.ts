export type ViewId = 'queue' | 'sales' | 'accounting' | 'accounts' | 'products'

export const dashboardViews: Array<{ id: ViewId; label: string; eyebrow: string; code: string }> = [
  { id: 'queue', label: 'Fila de eventos', eyebrow: 'Streaming', code: '01' },
  { id: 'sales', label: 'Painel de vendas', eyebrow: 'Commerce ops', code: '02' },
  { id: 'accounting', label: 'BP + DRE', eyebrow: 'Financeiro', code: '03' },
  { id: 'accounts', label: 'Catalogo de contas', eyebrow: 'Audit docs', code: '04' },
  { id: 'products', label: 'Catalogo de produtos', eyebrow: 'Stock pulse', code: '05' },
]