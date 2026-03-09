# Guia de Metricas e Estrategia de Coleta para Benchmark Individualizado

## 1. Proposito

Este documento define como coletar, de forma cientifica, reprodutivel e operacionalmente justa, as metricas de benchmark dos backends do projeto para o caso de uso especifico de alimentar paineis e frontends em tempo real por push.

O protocolo assume uma restricao pratica central do ambiente local: os backends nao podem operar todos simultaneamente sem contaminacao por disputa de CPU, memoria, disco e rede. Por isso, toda coleta deve ser individualizada por backend, em rodadas isoladas, guiadas por scripts e com janela maxima de 10 minutos por execucao.

## 2. Principios Metodologicos

### 2.1 Isolamento por backend

- Cada rodada ativa exatamente um backend em `ACTIVE_STACKS`.
- Nenhuma comparacao quantitativa deve misturar medições feitas com stacks concorrentes.

### 2.2 Janela maxima por rodada

- Cada rodada deve durar no maximo 10 minutos.
- Janela sugerida:
  - 2 minutos para bootstrap e warm-up.
  - 6 minutos para coleta.
  - 2 minutos para teardown e persistencia dos artefatos.

### 2.3 Repeticao minima

- Minimo de 3 rodadas por backend e por cenario.
- Idealmente 5 para reduzir sensibilidade a jitter local.

### 2.4 Mesmo contrato funcional

- Mesmo dataset logico.
- Mesmo conjunto de filtros.
- Mesmo criterio de aceitacao contabil.
- Mesmo frontend de referencia para a metrica visual.

### 2.5 Resultados sempre acompanhados de contexto

- Commit Git.
- Data/hora.
- Backend.
- Cenario.
- Duracao.
- Configuracao de ambiente.
- Limites de recurso.

## 3. Unidade Experimental

Cada unidade experimental corresponde a:

- 1 backend.
- 1 cenario.
- 1 rodada.
- 1 janela de ate 10 minutos.

Identificador recomendado:

```text
<timestamp>__<backend>__<cenario>__run-<n>
```

## 4. Fluxo Padrao de Coleta

### 4.1 Preparacao

1. Executar `make stop ENV_FILE=<env>`.
2. Confirmar ausencia de containers residuais.
3. Selecionar somente um backend em `ACTIVE_STACKS`.
4. Registrar `git rev-parse HEAD`.
5. Registrar o arquivo `.env` efetivo da rodada.

### 4.2 Bootstrap

1. Executar `make run ENV_FILE=<env>`.
2. Executar `make populate ENV_FILE=<env>` se o cenario exigir geracao ativa.
3. Aguardar estado minimo de saude.
4. Registrar tempo ate primeiro health verde.

### 4.3 Warm-up

1. Consumir `/health` e `/workspace` algumas vezes.
2. Confirmar se o frontend responde.
3. Confirmar que o stream websocket iniciou.

### 4.4 Coleta principal

1. Executar scripts de API.
2. Executar scripts de SQL nativo.
3. Executar scripts de websocket.
4. Executar coleta de `docker stats`.
5. Capturar debug endpoints internos.

### 4.5 Encerramento

1. Persistir arquivos brutos e consolidados.
2. Executar `make stop ENV_FILE=<env>`.
3. Limpar artefatos temporarios.

## 5. Duracao Recomendada por Rodada

| Fase | Duracao maxima | Objetivo |
| --- | --- | --- |
| Bootstrap | 120 s | stack operante e endpoint base respondendo |
| Warm-up | 90 s | reduzir artefatos de cold path |
| Coleta API/SQL/Websocket | 300 s | medicao principal |
| Recursos e debug final | 60 s | snapshot operacional da rodada |
| Teardown | 30 s | limpar ambiente |

Total alvo: 600 segundos.

## 6. Estrutura Recomendada de Scripts

### 6.1 Script mestre por backend

Nome sugerido:

- `scripts/benchmark/run_clickhouse_round.sh`
- `scripts/benchmark/run_druid_round.sh`
- `scripts/benchmark/run_pinot_round.sh`
- `scripts/benchmark/run_materialize_round.sh`

Responsabilidades:

- subir stack;
- warm-up;
- chamar scripts especializados;
- agregar artefatos;
- derrubar stack.

### 6.2 Scripts especializados

- `collect_api_latencies.*`
- `collect_sql_latencies.*`
- `collect_ws_convergence.*`
- `collect_container_stats.*`
- `collect_debug_snapshots.*`
- `consolidate_round_results.*`

## 7. Metricas Nucleares

### 7.1 Bootstrap e disponibilidade

- `time_to_health_green_ms`
- `time_to_first_useful_snapshot_ms`
- `health_transition_count`
- `restart_count`

Como colher:

- polling controlado em `/health` com timestamp monotônico;
- logs do writer/gateway/API;
- `docker inspect` e `docker ps`.

### 7.2 Latencia de API

- p50, p95, p99 de `/api/v1/dashboard/summary`
- p50, p95, p99 de `/api/v1/dashboard/workspace`
- p50, p95 de `/api/v1/dashboard/entries`
- p50, p95 de `/api/v1/dashboard/filter-search`

Como colher:

- script HTTP com amostragem por 3 a 5 minutos;
- filtros fixos e filtros de alta cardinalidade;
- registrar status code, tamanho da resposta e tempo total.

Ferramentas sugeridas:

- `k6`
- `vegeta`
- `hey`
- Node com `fetch` e histogramas próprios

### 7.3 Latencia SQL nativa

- p50, p95, p99 de queries equivalentes a `summary`, `workspace` e visoes filtradas.

Como colher:

- ClickHouse: HTTP/TCP.
- Druid: `/druid/v2/sql`.
- Pinot: `/query/sql`.
- Materialize: pgwire.

Critério:

- usar consultas semanticamente equivalentes, mas respeitando o modelo nativo de cada backend.

### 7.4 Convergencia visual no frontend

- `event_to_snapshot_visible_ms`
- `snapshot_rate_per_second`
- `entry_to_queue_visible_ms`
- `sale_to_sales_workspace_visible_ms`
- `frontend_time_to_first_meaningful_state_ms`

Como colher:

- script websocket dedicado;
- timestamp do evento na origem;
- timestamp de `dashboard.snapshot` ou `entry.created` no cliente;
- opcionalmente instrumentacao do frontend via Performance API.

### 7.5 Corretude contabil

- `balance_sheet_difference`
- `assets_equals_liabilities_plus_equity`
- `net_income_consistency`
- `summary_entries_consistency`
- `duplicate_entry_rate`

Como colher:

- chamadas a `/summary` e `/workspace`;
- verificacoes de invariantes contabeis por script;
- amostragem de entries e reconciliação com agregados.

### 7.6 Integridade do contrato funcional

- populacao de `account_catalog`
- populacao de `product_catalog`
- disponibilidade de `sales_workspace`
- cobertura de filtros suportados
- taxa de respostas vazias indevidas

Como colher:

- smoke scripts estruturados;
- contagem de campos obrigatorios preenchidos;
- comparacao entre backend e contrato esperado.

### 7.7 Recursos computacionais

- `cpu_avg`
- `cpu_peak`
- `memory_avg_mb`
- `memory_peak_mb`
- `network_rx_tx`
- `disk_growth_mb`

Como colher:

- `docker stats --no-stream` em amostragem recorrente;
- `docker system df` e tamanhos de volume no inicio e fim da rodada;
- consolidacao por servico critico.

### 7.8 Robustez a replay e cold start

- `cold_start_to_green_ms`
- `replay_recovery_ms`
- `post_replay_difference`
- `warming_up_duration_ms`
- `degraded_or_error_transitions`

Como colher:

- rodadas especificas com restart completo;
- replay controlado do topico canonico;
- leitura de debug endpoints e health ao longo do tempo.

## 8. Metricas Especificas por Backend

### 8.1 ClickHouse

- tempo para tabelas e fan-out ficarem prontas;
- latencia de leitura sobre `ledger.entries`;
- estabilidade de ressync autoritativo no gateway.

Coleta adicional:

- `system.parts`, `system.merges`, `system.metrics`.

### 8.2 Druid

- tempo para supervisor ativo;
- latencia de query no broker/router;
- estabilidade do ingestion lag.

Coleta adicional:

- status do supervisor;
- health do router/broker;
- contagem de segmentos.

### 8.3 Pinot

- tempo para tabela realtime ficar consumindo;
- latencia do broker SQL;
- estabilidade do push-first com projecao local.

Coleta adicional:

- status do controller;
- health de broker/server;
- consumo da realtime table.

### 8.4 Materialize

- `hydrated_rows`;
- `last_kafka_offset`;
- `view_lag_ms`;
- `freshness_ms`;
- `pending_retractions`;
- tempo ate `dashboard.snapshot` incremental autoritativo.

Coleta adicional:

- `/debug/materialize-bootstrap`;
- `/health` do `api_materialize`;
- consultas pgwire nas materialized views.

## 9. Cenarios Obrigatorios

### 9.1 Cenario A. Bootstrap operacional

- Objetivo: medir tempo para stack ficar utilizavel.
- Backend ativo: um por rodada.
- Saida: tempo ate health verde e tempo ate primeiro snapshot util.

### 9.2 Cenario B. Alta ingestao

- Objetivo: medir latencia e estabilidade sob fluxo intenso.
- Duração de coleta: 5 minutos.

### 9.3 Cenario C. Alta cardinalidade com filtros

- Objetivo: medir custo de filtros comerciais em `/workspace`.
- Filtros: `customer_name`, `product_name`, `channel`, `order_id`.

### 9.4 Cenario D. Replay e retracoes

- Objetivo: avaliar resiliencia a `return`, ajustes e replay do topico.

## 10. Artefatos por Rodada

Cada rodada deve gerar ao menos:

- `metadata.json`
- `api_latencies.json`
- `sql_latencies.json`
- `ws_metrics.json`
- `resources.json`
- `health_timeline.json`
- `debug_snapshots.json`
- `summary.csv`

## 11. Formato de Metadata da Rodada

Exemplo:

```json
{
  "commit": "<git-sha>",
  "backend": "materialize",
  "scenario": "high-ingestion",
  "started_at": "2026-03-08T22:00:00Z",
  "duration_seconds": 600,
  "env_file": ".env.materialize",
  "active_stacks": "materialize",
  "host_profile": {
    "cpu": "...",
    "memory": "..."
  }
}
```

## 12. Regras de Justica Experimental

- Nunca comparar medianas de rodadas com duracoes diferentes sem normalizacao.
- Nunca comparar backend cold start contra backend warm sem rotular explicitamente.
- Nunca aceitar resultado de desempenho com `balance_sheet.difference != 0`.
- Nunca usar media simples como unica estatistica; reportar percentis.
- Sempre registrar erros, retries e workarounds observados durante a rodada.

## 13. Ferramentas Recomendadas

- `make` para orquestracao.
- scripts `bash` para ciclo de vida da rodada.
- Node ou Python para coleta HTTP/websocket.
- `docker stats` para recursos.
- CSV/JSON para persistencia.
- opcionalmente `k6` ou `vegeta` para carga HTTP controlada.

## 14. Estrategia de Consolidacao dos Resultados

### 14.1 Nivel bruto

- manter todos os eventos coletados por timestamp.

### 14.2 Nivel consolidado

- agregar p50, p95, p99, maximo, minimo, taxa de erro e contagens.

### 14.3 Nivel analitico

- produzir scorecards executivo, engenharia e confiabilidade financeira.

## 15. Limites e Cuidados

- Ambiente local sofre interferencia do SO hospedeiro.
- Disco e cache podem influenciar rodadas subsequentes.
- Redes Docker podem introduzir jitter adicional.
- Alguns backends possuem processos assíncronos internos que exigem warm-up honesto.

## 16. Saida Esperada para Publicacao

Ao final, o benchmark deve produzir um conjunto suficientemente robusto para sustentar uma publicacao academica de alto nivel, contendo:

- metodologia explicita;
- cenarios reproduziveis;
- metricas multi-dimensionais;
- artefatos brutos auditaveis;
- comparacao entre paradigmas;
- discussao sobre validade, limitações e implicacoes arquiteturais.