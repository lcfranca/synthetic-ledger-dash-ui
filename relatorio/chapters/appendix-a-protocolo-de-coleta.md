# Apendice A. Protocolo de Coleta

## Proposito

Este apendice resume o protocolo de coleta adotado para o benchmark individualizado dos backends do projeto, preservando sua funcao como referencia operacional e metodologica do manuscrito.

## Principios

1. Cada rodada ativa exatamente um backend em `ACTIVE_STACKS`.
2. Nenhuma comparacao quantitativa deve misturar medicoes feitas com stacks concorrentes.
3. Cada rodada deve durar no maximo 10 minutos.
4. Resultados devem sempre registrar commit Git, backend, cenario, duracao e configuracao efetiva do ambiente.

## Fluxo padrao

1. Preparacao do ambiente e limpeza de residuos.
2. Subida da stack e populacao do cenario.
3. Espera por health minimo e aquecimento.
4. Coleta de API, SQL, websocket, health e recursos.
5. Consolidacao dos artefatos e teardown.

## Scripts implementados

- `scripts/benchmark/run_round.sh`
- `scripts/benchmark/run_clickhouse_round.sh`
- `scripts/benchmark/run_druid_round.sh`
- `scripts/benchmark/run_pinot_round.sh`
- `scripts/benchmark/run_materialize_round.sh`
- `scripts/benchmark/collect_api_latencies.py`
- `scripts/benchmark/collect_sql_latencies.py`
- `scripts/benchmark/collect_ws_convergence.mjs`
- `scripts/benchmark/collect_container_stats.py`
- `scripts/benchmark/collect_health_timeline.py`
- `scripts/benchmark/collect_debug_snapshots.py`
- `scripts/benchmark/consolidate_round_results.py`

## Observacao metodologica

O protocolo nao busca apenas medir consultas. Ele mede o sistema completo, incluindo bootstrap, saude operacional, reconvergencia visual e corretude contabil.