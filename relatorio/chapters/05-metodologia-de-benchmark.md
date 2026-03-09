# Metodologia de Benchmark

## 5.1 Tipo de pesquisa

Esta pesquisa adota carater experimental aplicado, com comparacao controlada entre backends submetidos ao mesmo contrato funcional. O objetivo nao e apenas obter numeros de latencia, mas construir evidencia empirica auditavel sobre como diferentes paradigmas de serving se comportam sob um mesmo problema de negocio.

## 5.2 Unidade experimental

Cada unidade experimental corresponde a uma rodada individualizada por backend e por cenario, executada em ambiente local controlado. O protocolo assume uma restricao pragmatica importante: as stacks nao devem concorrer simultaneamente pela mesma CPU, memoria, disco e rede, pois isso contaminaria a comparacao. Assim, a regra central e o isolamento por backend.

O identificador canonico de rodada adota o formato:

`<timestamp>__<backend>__<cenario>__run-<n>`

## 5.3 Janela temporal da rodada

Cada rodada possui janela maxima de 10 minutos, distribuida entre bootstrap, warm-up, coleta principal, captura de recursos e teardown. O protocolo recomendado e o seguinte:

| Fase | Duracao maxima | Objetivo |
| --- | --- | --- |
| Bootstrap | 120 s | tornar a stack operante e atingir health minimo |
| Warm-up | 90 s | reduzir efeitos de cold path |
| Coleta principal | 300 s | medir API, SQL e websocket |
| Recursos e debug final | 60 s | capturar estado operacional consolidado |
| Teardown | 30 s | limpar ambiente e persistir artefatos |

## 5.4 Fluxo operacional da coleta

O protocolo de coleta segue cinco etapas.

### 5.4.1 Preparacao

1. Executar `make stop ENV_FILE=<env>`.
2. Garantir ausencia de containers residuais.
3. Ativar exatamente um backend em `ACTIVE_STACKS`.
4. Registrar commit Git e configuracao efetiva de ambiente.

### 5.4.2 Bootstrap

1. Executar `make run ENV_FILE=<env>`.
2. Executar `make populate ENV_FILE=<env>` quando o cenario exigir geracao ativa.
3. Aguardar estado minimo de saude para APIs, frontend e endpoints de debug.

### 5.4.3 Warm-up

1. Consumir endpoints de health, summary e workspace.
2. Confirmar que o frontend responde.
3. Confirmar que o websocket iniciou.

### 5.4.4 Coleta principal

1. Coletar latencias reais de API.
2. Coletar latencias reais de SQL nativo.
3. Coletar convergencia websocket e latencia percebida.
4. Coletar recursos computacionais dos containers.
5. Registrar timeline de health.

### 5.4.5 Encerramento

1. Capturar snapshots finais de debug.
2. Consolidar os artefatos em JSON e CSV.
3. Derrubar a stack com `make stop`.

## 5.5 Metricas nucleares

O benchmark combina seis familias de metricas.

### 5.5.1 Bootstrap e disponibilidade

- `time_to_health_green_ms`
- `time_to_first_useful_snapshot_ms`
- `health_transition_count`
- `restart_count`

### 5.5.2 Latencia de API

- p50, p95 e p99 de `summary`
- p50, p95 e p99 de `workspace`
- p50 e p95 de `entries`
- p50 e p95 de `filter-search`

### 5.5.3 Latencia SQL nativa

- p50, p95 e p99 de consultas semanticamente equivalentes a resumo, workspace ou visoes filtradas

### 5.5.4 Convergencia visual no frontend

- `event_to_snapshot_visible_ms`
- `snapshot_rate_per_second`
- `entry_to_queue_visible_ms`
- `sale_to_sales_workspace_visible_ms`
- `frontend_time_to_first_meaningful_state_ms`

### 5.5.5 Corretude contabil

- `balance_sheet_difference`
- equivalencia entre ativos e passivos mais patrimonio
- consistencia entre agregados e entries
- taxa de duplicidade indevida

### 5.5.6 Recursos computacionais

- `cpu_avg`
- `cpu_peak`
- `memory_avg_mb`
- `memory_peak_mb`
- trafego de rede
- crescimento de disco

## 5.6 Artefatos canonicos da rodada

Cada rodada deve produzir o seguinte conjunto minimo de arquivos:

- `metadata.json`
- `api_latencies.json`
- `sql_latencies.json`
- `ws_metrics.json`
- `resources.json`
- `health_timeline.json`
- `debug_snapshots.json`
- `round_report.json`
- `summary.csv`

O arquivo `round_report.json` agrega os resultados brutos e derivados da rodada. O arquivo `summary.csv` sintetiza as colunas transversais necessarias para comparacao estatistica e composicao de tabelas do manuscrito.

## 5.7 Implementacao concreta no repositorio

O protocolo foi implementado por meio dos scripts localizados em `scripts/benchmark/`. O script `run_round.sh` orquestra a execucao integral da rodada. Wrappers dedicados selecionam o backend. Scripts Python e Node coletam API, SQL, websocket, recursos, health e snapshots finais. Por fim, `consolidate_round_results.py` gera `round_report.json` e `summary.csv` no formato padrao.

Essa implementacao e essencial para a validade da pesquisa, pois reduz a dependencia de execucao manual, melhora a reprodutibilidade e preserva rastreabilidade entre rodadas, configuracoes e commits.

## 5.8 Ameacas a validade

Permanecem ameacas conhecidas a validade interna e externa: jitter do ambiente local, cache de disco, aquecimento assimetrico entre stacks, contencao residual de recursos e diferencas de custo operacional que nao se refletem imediatamente em latencia de consulta. Em vez de ocultar tais fatores, o protocolo os incorpora como parte do objeto de estudo, sobretudo por meio de timeline de health, artefatos de recursos e separacao entre cold start e warm state.

## 5.9 Fecho metodologico

A metodologia adotada transforma o benchmark em um experimento de sistema completo. O objeto observado nao e apenas a consulta SQL, mas o ciclo que liga evento, ledger, backend, API, gateway e interface visual. Essa escolha e coerente com a pergunta cientifica do trabalho e sustenta a interpretacao dos resultados em termos arquiteturais.