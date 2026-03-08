export type ViewId = 'queue' | 'sales' | 'accounting' | 'accounts' | 'products' | 'observability'

export const dashboardViews: Array<{ id: ViewId; label: string; eyebrow: string; code: string }> = [
  { id: 'queue', label: 'Lancamentos Contabeis', eyebrow: 'Escrituracao', code: '01' },
  { id: 'sales', label: 'Operacao Comercial', eyebrow: 'Receita', code: '02' },
  { id: 'accounting', label: 'Balanco e Resultado', eyebrow: 'Financeiro', code: '03' },
  { id: 'accounts', label: 'Plano de Contas', eyebrow: 'Estrutura', code: '04' },
  { id: 'products', label: 'Produtos e Cobertura', eyebrow: 'Abastecimento', code: '05' },
  { id: 'observability', label: 'Observabilidade Executiva', eyebrow: 'Telemetry', code: '06' },
]