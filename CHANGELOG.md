# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,
and this project adheres to Semantic Versioning.

## [Unreleased]

### Changed
- Versão de release candidata definida em `VERSION` como `0.0.1-rc.1`.

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
