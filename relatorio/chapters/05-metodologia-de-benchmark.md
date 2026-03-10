# Metodologia de Benchmark

## Tipo de pesquisa

Esta pesquisa adota caráter experimental aplicado, com comparação controlada entre backends submetidos ao mesmo contrato funcional. O objetivo não é apenas obter números de latência, mas construir evidência empírica auditável sobre como diferentes paradigmas de serving se comportam sob um mesmo problema de negócio.

## Unidade experimental

Cada unidade experimental corresponde a uma rodada individualizada por backend e por cenário, executada em ambiente local controlado. O protocolo assume uma restrição pragmática importante: as stacks não devem concorrer simultaneamente pela mesma CPU, memória, disco e rede, pois isso contaminaria a comparação. Assim, a regra central é o isolamento por backend.

O identificador canônico de rodada adota o formato:

`<timestamp>__<backend>__<cenario>__run-<n>`

## Janela temporal da rodada

Na versão do protocolo efetivamente utilizada para a bateria conclusiva deste relatório, os tempos não foram tratados como literais soltos. Eles são materializados no código por constantes nomeadas e copiados para `metadata.json` sob a chave `phase_budget_seconds`, o que permite auditoria posterior da configuração aplicada em cada rodada.

Para as rodadas `report-conclusion`, executadas neste manuscrito, a parametrização observada foi a seguinte:

| Parametro protocolar | Valor efetivo | Origem operacional |
| --- | ---: | --- |
| `collection_seconds` | 270 s | argumento da rodada |
| `bootstrap_wait` | 180 s | `BENCHMARK_DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS` |
| `backend_readiness_wait` | 240 s | `BENCHMARK_DEFAULT_BACKEND_TIMEOUT_SECONDS` |
| `warmup` | 10 s | `BENCHMARK_DEFAULT_WARMUP_SECONDS` |
| `per_probe_segment` | 90 s | `max(collection_seconds / 3, BENCHMARK_MIN_SEGMENT_SECONDS)` |
| `BENCHMARK_MIN_SEGMENT_SECONDS` | 45 s | piso operacional do coletor |

Essa explicitude é metodologicamente relevante. Em vez de postular números arbitrários na escrita, o relatório passa a herdar os budgets reais do protocolo executado.

## Fluxo operacional da coleta

O protocolo de coleta segue cinco etapas.

### Preparação

1. Executar `make stop ENV_FILE=<env>`.
2. Garantir ausencia de containers residuais.
3. Ativar exatamente um backend em `ACTIVE_STACKS`.
4. Registrar commit Git e configuracao efetiva de ambiente.

### Bootstrap

1. Gerar um arquivo de ambiente derivado de `.env.example`, ativando exatamente um backend.
2. Resolver o conjunto de servicos por meio de `scripts/stack-selection.sh`.
3. Subir a stack via `docker compose --env-file <env> up --build -d ...`.
4. Executar `make populate ENV_FILE=<env>` para iniciar a geracao ativa de eventos e popular a trilha observada.
5. Aguardar estado minimo de saude para `master-data`, `storage-writer`, `realtime-gateway`, API do backend, frontend e endpoint de debug.

Essa variante foi necessária para preservar equivalência metodológica entre as stacks. O alvo genérico `make run` acoplava a coleta a um smoke test que, no caso de Druid, podia reprovar o sistema antes da materialização do datasource. A orquestração de benchmark foi, portanto, desacoplada do smoke genérico de desenvolvimento sem abrir mão de health checks explícitos.

### Warm-up

1. Consumir endpoints de health, summary e workspace.
2. Confirmar que o frontend responde.
3. Confirmar que o websocket iniciou.

### Coleta principal

1. Coletar latencias reais de API.
2. Coletar latencias reais de SQL nativo.
3. Coletar convergencia websocket e latencia percebida.
4. Coletar recursos computacionais dos containers.
5. Registrar timeline de health.

### Encerramento

1. Capturar snapshots finais de debug, preservando inclusive falhas HTTP residuais como artefatos auditaveis quando algum endpoint de observabilidade nao responder com sucesso.
2. Consolidar os artefatos em JSON e CSV.
3. Derrubar a stack com `make stop`.

## Métricas nucleares

O benchmark combina seis famílias de métricas.

### Bootstrap e disponibilidade

- `time_to_health_green_ms`
- `time_to_first_useful_snapshot_ms`
- `health_transition_count`
- `restart_count`

### Latência de API

- p50, p95 e p99 de `summary`
- p50, p95 e p99 de `workspace`
- p50 e p95 de `entries`
- p50 e p95 de `filter-search`

### Latência SQL nativa

- p50, p95 e p99 de consultas semanticamente equivalentes a resumo, workspace ou visões filtradas

### Convergência visual no frontend

- `event_to_snapshot_visible_ms`
- `snapshot_rate_per_second`
- `entry_to_queue_visible_ms`
- `sale_to_sales_workspace_visible_ms`
- `frontend_time_to_first_meaningful_state_ms`

### Corretude contábil

- `balance_sheet_difference`
- equivalência entre ativos e passivos mais patrimônio
- consistencia entre agregados e entries
- taxa de duplicidade indevida

### Recursos computacionais

- `cpu_avg`
- `cpu_peak`
- `memory_avg_mb`
- `memory_peak_mb`
- tráfego de rede
- crescimento de disco

## Artefatos canônicos da rodada

Cada rodada deve produzir o seguinte conjunto mínimo de arquivos:

- `metadata.json`
- `api_latencies.json`
- `sql_latencies.json`
- `ws_metrics.json`
- `resources.json`
- `health_timeline.json`
- `debug_snapshots.json`
- `round_report.json`
- `summary.csv`

O arquivo `round_report.json` agrega os resultados brutos e derivados da rodada. O arquivo `summary.csv` sintetiza as colunas transversais necessárias para comparação estatística e composição de tabelas do manuscrito.

## Implementação concreta no repositório

O protocolo foi implementado por meio dos scripts localizados em `scripts/benchmark/`. O script `run_round.sh` orquestra a execução integral da rodada. Wrappers dedicados selecionam o backend. Scripts Python e Node coletam API, SQL, websocket, recursos, health e snapshots finais. Por fim, `consolidate_round_results.py` gera `round_report.json` e `summary.csv` no formato padrão. Como os budgets de fase são gravados em metadados, cada tabela do manuscrito pode ser confrontada diretamente com a configuração operada em tempo de execução.

Essa implementação é essencial para a validade da pesquisa, pois reduz a dependência de execução manual, melhora a reprodutibilidade e preserva rastreabilidade entre rodadas, configurações e commits.

## Ameaças à validade

Permanecem ameaças conhecidas à validade interna e externa: jitter do ambiente local, cache de disco, aquecimento assimétrico entre stacks, contenção residual de recursos e diferenças de custo operacional que não se refletem imediatamente em latência de consulta. Em vez de ocultar tais fatores, o protocolo os incorpora como parte do objeto de estudo, sobretudo por meio de timeline de health, artefatos de recursos e separação entre cold start e warm state.

## Fecho metodológico

A metodologia adotada transforma o benchmark em um experimento de sistema completo. O objeto observado não é apenas a consulta SQL, mas o ciclo que liga evento, ledger, backend, API, gateway e interface visual. Essa escolha é coerente com a pergunta científica do trabalho e sustenta a interpretação dos resultados em termos arquiteturais.