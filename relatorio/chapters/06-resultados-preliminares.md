# Resultados Preliminares e Evidencia Experimental Ja Coletada

## 6.1 Objetivo desta secao

Esta secao nao apresenta ainda a bateria comparativa completa entre todos os backends. Seu objetivo e registrar, de forma cientificamente honesta, a evidencia real ja produzida no repositorio ao final da trilha de endurecimento do Materialize. Em vez de inserir placeholders, a secao se apoia em valores concretos extraidos do artefato de rodada `20260309T021556Z__materialize__validation-ready__run-4`, consolidado em `summary.csv` e `round_report.json`.

## 6.2 Contexto da rodada validada

A rodada consolidada foi executada com os seguintes metadados experimentais:

| Campo | Valor |
| --- | --- |
| Round ID | `20260309T021556Z__materialize__validation-ready__run-4` |
| Commit | `b1ca00e42747fe126e28bf27146b84cc829e4dbf` |
| Backend | `materialize` |
| Cenario | `validation-ready` |
| Duracao | 90 s |
| Frontend base URL | `http://localhost:5176` |
| API base URL | `http://localhost:8084` |
| Host profile | `Linux 6.6.87.2-microsoft-standard-WSL2 x86_64 GNU/Linux` |

Esses dados sao relevantes porque preservam rastreabilidade integral entre a escrita do manuscrito e o artefato operacional real.

## 6.3 Metricas consolidadas observadas

Os valores derivados principais da rodada foram os seguintes:

| Metrica | Valor observado |
| --- | ---: |
| `api_summary_p95_ms` | 1594.14 |
| `api_workspace_p95_ms` | 2052.29 |
| `sql_entries_count_p95_ms` | 909.33 |
| `sql_summary_by_role_p95_ms` | 908.56 |
| `frontend_time_to_first_meaningful_state_ms` | 180 |
| `snapshot_rate_per_second` | 2.3142 |
| `entry_rate_per_second` | 71.8664 |
| `balance_sheet_difference` | 0.0 |
| `health_transition_total` | 4 |

## 6.4 Interpretacao preliminar

Os resultados indicam, em primeiro lugar, que a trilha Materialize ja atingiu um patamar operacional suficientemente estavel para produzir uma rodada completa com artefatos consistentes, incluindo latencias HTTP, latencias SQL, metricas websocket e verificacao contabil. O fato de `balance_sheet_difference` permanecer em 0.0 e particularmente importante, pois elimina a possibilidade de interpretar os ganhos de convergencia como resultado de degradacao semantica do ledger.

Em segundo lugar, observa-se uma diferenca clara entre os tempos p95 de `summary` e `workspace`. O endpoint de workspace permanece mais oneroso, o que e coerente com a maior carga semantica e volumetrica desse contrato. Ainda assim, o frontend alcancou `frontend_time_to_first_meaningful_state_ms` de 180 ms, sugerindo que a estrategia de snapshot incremental autoritativo conseguiu dissociar parcialmente o tempo de utilidade percebida do custo das leituras mais pesadas do backend.

Em terceiro lugar, as consultas SQL nativas apresentaram p95 em torno de 909 ms para consultas equivalentes de contagem e resumo por papel contabil. Esse comportamento reforca a ideia de que o sistema incremental pode manter latencias de consulta ainda significativas, sem que isso comprometa necessariamente a prontidao visual inicial do painel. Essa dissociacao entre latencia interna e latencia percebida constitui um dos argumentos centrais deste relatorio.

## 6.5 Limites desta evidencia

Esses resultados nao autorizam conclusoes comparativas finais entre ClickHouse, Druid, Pinot e Materialize. Eles documentam apenas que a trilha Materialize ja produz evidencia empirica real, auditavel e contabilmente consistente. O proximo passo metodologico e repetir o mesmo protocolo sobre as demais stacks, preservando equivalencia de cenario, numero de rodadas e contrato funcional.

## 6.6 Implicacao para a continuidade do trabalho

A existencia de uma rodada validada com valores reais muda o status epistemico do projeto. O documento deixa de ser um plano puramente prospectivo e passa a registrar um benchmark efetivamente em operacao. Isso fortalece a narrativa analitica do manuscrito e orienta os capitulos seguintes para uma expansao comparativa, e nao para uma fase ainda especulativa de implementacao.