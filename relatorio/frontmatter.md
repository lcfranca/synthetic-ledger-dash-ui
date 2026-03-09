# Resumo Executivo

Este relatorio analisa como diferentes familias de backends analiticos e incrementais se comportam quando usadas como camada de serving para paineis gerenciais near-real-time orientados por eventos. O problema avaliado nao se reduz a latencia SQL isolada; ele envolve a distancia entre o evento canonico de negocio e a disponibilidade de um estado derivado semantica e contabilmente confiavel no frontend. Para enfrentar esse problema, o documento consolida um benchmark reprodutivel sobre um repositorio monolitico que integra producer, OpenTelemetry Collector, Kafka, storage writer, APIs especializadas, gateway realtime e frontends por backend. O corpus tecnologico comparado abrange ClickHouse, Apache Druid, Apache Pinot e Materialize, cobrindo tanto motores hot-analytic quanto sistemas incremental-streaming. A metodologia experimental opera por rodadas individualizadas, com coleta de metricas de bootstrap, latencia de API, latencia SQL, convergencia websocket, corretude contabil e consumo de recursos. Como evidencia preliminar concreta, a trilha Materialize foi validada com coleta real, produzindo p95 de 1594.14 ms para o endpoint de resumo, p95 de 2052.29 ms para o workspace, p95 em torno de 909 ms para consultas SQL equivalentes e latencia de 180 ms para o primeiro estado meaningful no frontend, mantendo diferenca contabil igual a 0.0. O resultado principal deste relatorio e organizar, de forma impessoal e auditavel, a base tecnica necessaria para a comparacao entre paradigmas de serving, e nao apenas entre produtos.

**Palavras-chave:** benchmark de backends, dashboards em tempo real, event sourcing, OLAP, incremental view maintenance, Materialize, ClickHouse, Druid, Pinot.

# Executive Summary

This report analyzes how different families of analytical and incremental backends behave when used as the serving layer for event-driven near-real-time management dashboards. The evaluated problem is not limited to isolated SQL latency; it concerns the distance between the canonical business event and the availability of a semantically and financially reliable derived state in the frontend. To address this problem, the document consolidates a reproducible benchmark built on top of a monorepo integrating producer, OpenTelemetry Collector, Kafka, storage writer, specialized APIs, realtime gateway and backend-specific frontends. The technological corpus includes ClickHouse, Apache Druid, Apache Pinot and Materialize, therefore covering both hot-analytic engines and incremental-streaming systems. The experimental methodology is organized as isolated rounds, collecting metrics for bootstrap, API latency, SQL latency, websocket convergence, accounting correctness and resource consumption. As concrete preliminary evidence, the Materialize track was validated with real measurements, producing a p95 of 1594.14 ms for the summary endpoint, a p95 of 2052.29 ms for the workspace endpoint, SQL p95 values near 909 ms for equivalent queries, and 180 ms for the first meaningful frontend state, while preserving a 0.0 accounting difference. The main contribution of this report is to organize the technical evidence in an impersonal and auditable form, enabling comparison between serving paradigms rather than merely between products.

**Keywords:** backend benchmarking, real-time dashboards, event sourcing, OLAP, incremental view maintenance, Materialize, ClickHouse, Druid, Pinot.

# Nota de Escopo

Este pacote organiza em uma unica pasta os arquivos-fonte do relatorio, o template de compilacao e o PDF resultante, com base no estado atual do benchmark implementado no repositorio.

## Criterios editoriais

- O texto adota formato de relatorio tecnico impessoal.
- As afirmacoes factuais devem permanecer ancoradas em artefatos observaveis do repositorio.
- Informacoes pessoais, institucionais ou geograficas nao verificadas foram removidas do documento.