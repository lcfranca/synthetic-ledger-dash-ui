# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,
and this project adheres to Semantic Versioning.

## [Unreleased]

### Changed
- Versão oficial do projeto passou para `pyproject.toml` (`0.0.1-rc.1`) como arquivo de configuração principal.
- Dashboard deixou de ser apenas agregados e passou a exibir fila em tempo real de lançamentos Débito/Crédito com ontologia e trilha de auditoria.
- API passou a derivar BP/DRE exclusivamente da tabela de lançamentos (`ledger.entries`) e incluiu suporte a time-travel via `as_of`.
- Pipeline de ingestão passou a transformar eventos em lançamentos contábeis imutáveis com campos de auditoria, rastreabilidade e revisão temporal.

### Added
- `docs/art_bible.md` com direção estética do projeto (padrão art bible) e ontologia de lançamentos.
- Endpoints de histórico de lançamentos e payload websocket com resumo + entradas recentes.
- Roteiro operacional para acesso ao Pinot:
	- Navegador: `http://localhost:9001` (Pinot Controller UI) para status de cluster, tabelas e segmentos.
	- SQL via navegador: `http://localhost:8099` (Pinot Broker) para API/queries HTTP.
	- SQL via cliente (DBeaver/DataGrip): host `localhost`, porta `8099`, database `default`, protocolo Pinot/Trino compatível conforme driver do cliente.
- Nova API dedicada do Pinot em `api_pinot/` com endpoints de dashboard e websocket (`/ws/metrics`).
- Nova UI dedicada do Pinot em `frontend_pinot/`, modular e desacoplada das UIs de ClickHouse e Druid.

### Fixed
- Bootstrap do supervisor Kafka no Druid ajustado para seguir redirect HTTP (`307`) e manter ingestão estável.
- Endpoints websocket das APIs (`api` e `api-druid`) ajustados para desconexão segura sem erro de fechamento duplicado.
- Bootstrap de tabela realtime do Pinot via Kafka adicionado ao `storage_writer`, com retry e endpoint de debug (`/debug/pinot-realtime`).

## [0.0.1] - 2026-03-03

### Added
- Scaffold completo de monorepo com serviços `producer`, `otel`, `storage_writer`, `api`, `frontend`, `k8s` e `shared`.
- Documentação técnica state-of-the-art em `docs/architecture-state-of-the-art.md`.
- Contrato de evento contábil em JSON Schema e AVRO versionado (`v1` e `v2`).
- Comandos operacionais no `Makefile`: `up`, `down`, `populate`, `stop-populate`, `logs`, `ps`, `rebuild`, `health`.
- Configuração Docker Compose com Kafka, OTEL Collector, ClickHouse, Druid, Pinot, API, frontend e producer.
- Endpoint WebSocket para métricas near-real-time na API (`/ws/metrics`).
- Configuração de proxy Nginx no frontend para `/api` e `/ws`.
- Inicialização de schema/tabela e usuários no ClickHouse para ambiente local.
- Variáveis de ambiente com parâmetros de conexão para DBeaver em `.env` e `.env.example`.
- Endpoint de debug em `storage_writer` para inspeção do último payload OTLP (`/debug/last-otlp`).

### Changed
- Producer passou a publicar payload OTLP protobuf compatível com ingestão do OpenTelemetry Collector.
- Validação de eventos no producer com schema AVRO selecionado por `SCHEMA_MAJOR_VERSION`.
- Pipeline OTEL ajustado para maior estabilidade (batch/timeout/retry).
- Lógica de ingestão OTLP no `storage_writer` robustecida para JSON/protobuf e conteúdo comprimido.
- Escrita no ClickHouse reforçada com criação idempotente de schema/tabela e normalização de timestamp.

### Fixed
- Ordem de inicialização e saúde de dependências no Docker Compose para reduzir falhas de bootstrap.
- Falhas de frontend sem dados por ausência de proxy reverso para API/WebSocket.
- Falhas de parsing OTLP que causavam `500` no `storage_writer`.
- Erros de conexão e inconsistências de imagem/porta no ambiente local.
