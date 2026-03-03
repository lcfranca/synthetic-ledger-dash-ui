# Synthetic Ledger Dash UI Monorepo

Plataforma para geração de eventos contábeis sintéticos, ingestão por Kafka + OpenTelemetry Collector, persistência em múltiplos OLAP backends e dashboard near-real-time com foco em latência percebida.

## Estrutura

- `producer/`: gerador de eventos contábeis sintéticos em Python.
- `otel/`: configuração de ingestão e roteamento no OpenTelemetry Collector.
- `storage_writer/`: serviço de persistência fan-out para ClickHouse, Druid e Pinot.
- `api/`: camada de consulta agregada para o frontend.
- `frontend/`: dashboard near-real-time.
- `k8s/`: manifests base para execução em Kubernetes.
- `docs/`: documentação funcional e técnica.

## Primeiros passos

1. Suba ambiente local com um comando:
   - `make up`
2. Inicie a produção de eventos sintéticos:
   - `make populate`
3. Pare a produção de eventos quando quiser:
   - `make stop-populate`
4. Acompanhe saúde dos serviços:
   - `make health`
5. Acesse:
   - Frontend: `http://localhost:5173`
   - API: `http://localhost:8080/docs`

O alvo `up` cria `.env` automaticamente a partir de `.env.example` se necessário.

## Versionamento de schema (AVRO)

- Schemas versionados em:
   - `shared/schemas/avro/accounting_event_v1.avsc`
   - `shared/schemas/avro/accounting_event_v2.avsc`
- O producer valida eventos contra AVRO via `SCHEMA_MAJOR_VERSION`.

## DBeaver (conexões)

### ClickHouse
- Host: `localhost`
- HTTP Port: `8123`
- Native Port: `9000`
- Database/Schema: `ledger`
- User app: `ledger_app`
- Password app: `ledger_app_pass`
- User readonly: `ledger_ro`
- Password readonly: `ledger_ro_pass`

### Pinot (Broker)
- Host: `localhost`
- Port: `8099`
- Table: `ledger_events`
- Observação: `PINOT_USER`/`PINOT_PASSWORD` estão no `.env` para padronização, mas o container local padrão não força autenticação.

### Druid (Router)
- Host: `localhost`
- Port: `8889`
- Datasource: `ledger_events`
- Observação: autenticação também não é imposta no quickstart local.

## Documentação técnica

Veja [docs/architecture-state-of-the-art.md](docs/architecture-state-of-the-art.md).
