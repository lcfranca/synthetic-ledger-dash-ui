# Apendice B. Especificacao Canonica dos Artefatos

Cada rodada de benchmark deve produzir um conjunto uniforme de arquivos, permitindo auditoria, reprocessamento e comparacao longitudinal.

## Artefatos obrigatorios

- `metadata.json`
- `api_latencies.json`
- `sql_latencies.json`
- `ws_metrics.json`
- `resources.json`
- `health_timeline.json`
- `debug_snapshots.json`
- `round_report.json`
- `summary.csv`

## Estrutura logica do consolidado

O artefato canonico de rodada e `round_report.json`, cuja estrutura minima e:

```json
{
  "metadata": {},
  "api_latencies": {},
  "sql_latencies": {},
  "ws_metrics": {},
  "resources": {},
  "health_timeline": {},
  "debug_snapshots": {},
  "derived_metrics": {}
}
```

## Colunas transversais do CSV

O `summary.csv` deve conter ao menos as seguintes colunas:

- `round_id`
- `commit`
- `backend`
- `scenario`
- `run_number`
- `started_at`
- `duration_seconds`
- `api_summary_p95_ms`
- `api_workspace_p95_ms`
- `sql_entries_count_p95_ms`
- `sql_summary_by_role_p95_ms`
- `frontend_time_to_first_meaningful_state_ms`
- `snapshot_rate_per_second`
- `entry_rate_per_second`
- `balance_sheet_difference`
- `health_transition_total`

## Regra semantica

Todos os campos devem refletir valores realmente observados. Quando um valor nao estiver disponivel, ele deve aparecer como `null` no JSON e permanecer vazio no CSV. Nao se admitem placeholders textuais em artefatos experimentais finais.