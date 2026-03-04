# Synthetic Ledger Dash UI Monorepo

Plataforma para geração de eventos contábeis sintéticos, ingestão por Kafka + OpenTelemetry Collector, persistência em múltiplos OLAP backends e dashboard near-real-time com foco em latência percebida.

Versão atual do projeto (configuração oficial): `pyproject.toml` (`project.version = 0.0.1-rc.1`).

## Estrutura

- `producer/`: gerador de eventos contábeis sintéticos em Python.
- `otel/`: configuração de ingestão e roteamento no OpenTelemetry Collector.
- `storage_writer/`: serviço de persistência fan-out para ClickHouse, Druid e Pinot.
- `api/`: camada de consulta agregada para o frontend.
- `api_druid/`: camada de consulta agregada para dashboard com backend Druid.
- `api_pinot/`: camada de consulta agregada para dashboard com backend Pinot.
- `frontend/`: dashboard near-real-time.
- `frontend_pinot/`: dashboard Pinot desacoplado e modular.
- `k8s/`: manifests base para execução em Kubernetes.
- `docs/`: documentação funcional e técnica.

## Regras Contábeis do Sistema

- Todo evento contábil gera lançamentos imutáveis de débito/crédito.
- Somente lançamentos alteram saldos de BP/DRE.
- Eventos de origem são mapeados em ontologia de lançamento (`ontology_event_type`, `ontology_description`, `ontology_source`).
- Auditoria e rastreabilidade com `event_id`, `trace_id`, `source_payload_hash`, `revision`, `valid_from`, `valid_to` e `is_current`.
- Time-travel via parâmetro `as_of` nos endpoints da API.
- Druid pode consumir lançamentos diretamente do Kafka (`DRUID_KAFKA_TOPIC`) via supervisor automático configurado no `storage_writer`.
- Para consumo Kafka no Druid, o endpoint de indexing/supervisor deve estar ativo (overlord/indexer disponível no cluster Druid).

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
   - Frontend (Druid): `http://localhost:5174`
   - API (Druid): `http://localhost:8081/docs`
   - Frontend (Pinot): `http://localhost:5175`
   - API (Pinot): `http://localhost:8082/docs`

O alvo `up` cria `.env` automaticamente a partir de `.env.example` se necessário.

Para diagnosticar supervisor Kafka do Druid:
- `http://localhost:8090/debug/druid-supervisor`

Para diagnosticar bootstrap realtime do Pinot:
- `http://localhost:8090/debug/pinot-realtime`

## Acesso ao Apache Pinot no navegador

Com a stack ativa (`make up`), os endpoints principais do Pinot são:

- Controller UI: `http://localhost:9001`
- Broker SQL/API: `http://localhost:8099`
- Dashboard Pinot dedicado: `http://localhost:5175`

### Passo a passo rápido

1. Validar serviços do Pinot:
   - `docker compose ps pinot-zookeeper pinot-controller pinot-broker api-pinot frontend-pinot`
2. Abrir Controller UI:
   - `http://localhost:9001`
3. Confirmar bootstrap no writer:
   - `curl http://localhost:8090/debug/pinot-realtime`
4. Testar query no Broker:
   - `curl -X POST http://localhost:8099/query/sql -H 'Content-Type: application/json' -d '{"sql":"SELECT COUNT(*) AS c FROM ledger_events"}'`
5. Abrir dashboard Pinot dedicado:
   - `http://localhost:5175`

## Acesso ao Apache Druid no navegador

Com a stack ativa (`make up`), o Router do Druid fica exposto em `localhost:8889`.

### URLs principais

- Console web do Druid (Router): `http://localhost:8889`
- Unified Console (quando disponível): `http://localhost:8889/unified-console.html`
- SQL endpoint (API): `http://localhost:8889/druid/v2/sql`
- Status de saúde (Router): `http://localhost:8889/status/health`

### Passo a passo rápido

1. Validar serviços Druid:
    - `docker compose ps druid-router druid-broker druid-coordinator druid-overlord druid-middlemanager`
2. Abrir o console no navegador:
   - `http://localhost:8889`
3. No menu de SQL da UI, testar rapidamente:
   - `SELECT COUNT(*) AS c FROM "ledger_events"`
4. Validar supervisor Kafka do datasource:
    - `curl http://localhost:8090/debug/druid-supervisor`
5. Testar SQL do datasource no Router (via terminal):
    - `curl -X POST http://localhost:8889/druid/v2/sql -H 'Content-Type: application/json' -d '{"query":"SELECT COUNT(*) AS c FROM \"ledger_events\""}'`

### Troubleshooting comum

- Erro `503` em `/druid/indexer/v1/supervisor`:
   - Overlord/Coordinator não estão prontos. Reinicie:
      - `docker compose restart druid-coordinator druid-overlord druid-router`
- Erro SQL `There are no available brokers`:
   - Broker não está saudável/registrado. Reinicie:
      - `docker compose restart druid-broker druid-router`
- Supervisor em `retrying` no writer:
   - Aguarde retries automáticos e confira:
      - `curl http://localhost:8090/debug/druid-supervisor`
   - Se necessário, reinicie writer após Druid estabilizar:
      - `docker compose restart storage-writer`

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

Avaliação state-of-the-art para frontend orientado a PUSH: [docs/frontend-push-state-of-the-art.md](docs/frontend-push-state-of-the-art.md).

Direção estética e semântica de produto: [docs/art_bible.md](docs/art_bible.md).
