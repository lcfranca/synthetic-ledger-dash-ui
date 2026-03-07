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
- Os três painéis são orientados ao mesmo stream Kafka canônico de lançamentos (`LEDGER_ENTRIES_KAFKA_TOPIC`).
- O `storage_writer` deriva lançamentos contábeis uma única vez e publica no tópico canônico.
- ClickHouse é alimentado por fan-out Kafka no `storage_writer`.
- Druid consome o mesmo tópico via supervisor Kafka.
- Pinot consome o mesmo tópico via tabela realtime Kafka.

## Arquitetura modular dos painéis

Cada painel é isolado em sua própria API e frontend, mas todos compartilham o mesmo contrato de lançamentos e o mesmo backbone Kafka.

### Backplane comum

- Producer/Otel → `storage_writer`
- `storage_writer` → `LEDGER_ENTRIES_KAFKA_TOPIC`
- Consumidores independentes:
   - ClickHouse dashboard
   - Druid dashboard
   - Pinot dashboard

### Endpoints de debug do fan-out

- Último OTLP processado: `http://localhost:8090/debug/last-otlp`
- Fan-out Kafka para backends diretos: `http://localhost:8090/debug/kafka-fanout`
- Supervisor Kafka do Druid: `http://localhost:8090/debug/druid-supervisor`
- Bootstrap realtime do Pinot: `http://localhost:8090/debug/pinot-realtime`

## Primeiros passos

Antes da subida, escolha no `.env` quais stacks completas ficam ativas:

- `ACTIVE_STACKS=pinot`
- `RUN_PRODUCER_ON_START=false`

`ACTIVE_STACKS` aceita listas separadas por vírgula e sobe a stack inteira de cada tecnologia selecionada: backend, API e frontend. Exemplos:

- `ACTIVE_STACKS=clickhouse,pinot`
- `ACTIVE_STACKS=druid,pinot`

1. Suba ambiente local com um comando:
   - `make run`
2. Inicie a produção de eventos sintéticos:
   - `make populate`
3. Pare a produção de eventos quando quiser:
   - `make stop-populate`
4. Derrube e limpe completamente o ambiente local:
   - `make stop`
4. Acompanhe saúde dos serviços:
   - `make health`
5. Rode validações rápidas por painel:
   - `make health-clickhouse`
   - `make health-druid`
   - `make health-pinot`
   - `make smoke-all`

Ao final de `make run`, o projeto agora executa um smoke automático de subida para validar saúde do `master-data`, contrato do catálogo Pinot e, quando `RUN_PRODUCER_ON_START=true`, a aritmética de BP e DRE.

O produtor também passa a emitir eventos explícitos de `return` e `freight`, o que mantém contas de devoluções, fretes sobre vendas e despesas bancárias com movimento real no razão.

O alvo `run` cria `.env` automaticamente a partir de `.env.example` se necessário.

## Modo econômico

- O `.env.example` já vem em modo econômico com Pinot-only por padrão.
- `make run` sobe apenas os serviços derivados da variável `ACTIVE_STACKS`.
- `make stop` executa `down --remove-orphans --volumes --rmi local` e remove sobras do projeto para liberar portas, rede e volumes.
- Os limites de CPU/memória do `.env` foram recalibrados para um WSL com 15 GB de RAM e 4 GB de swap.

## Painel 1 — ClickHouse

### URLs

- Frontend: `http://localhost:5173`
- API: `http://localhost:8080/docs`
- Health: `http://localhost:8080/health`

### Fonte de dados

- Backend de leitura: ClickHouse
- Alimentação: fan-out Kafka do `storage_writer`
- Tabela: `ledger.entries`

### Verificações rápidas

1. `make health-clickhouse`
2. `make smoke-clickhouse`
3. Conexão analítica:
   - Host `localhost`
   - HTTP `8123`
   - Native `9000`
   - Database `ledger`

## Painel 2 — Druid

### URLs

- Frontend: `http://localhost:5174`
- API: `http://localhost:8081/docs`
- Router/UI: `http://localhost:8889`
- SQL endpoint: `http://localhost:8889/druid/v2/sql`
- Health API: `http://localhost:8081/health`
- Health Router: `http://localhost:8889/status/health`

### Fonte de dados

- Backend de leitura: Apache Druid
- Alimentação: supervisor Kafka no datasource `ledger_events`
- Debug: `http://localhost:8090/debug/druid-supervisor`

### Verificações rápidas

1. `make health-druid`
2. `make smoke-druid`
3. Validar serviços:
   - `docker compose ps druid-router druid-broker druid-coordinator druid-overlord druid-middlemanager`
4. Testar SQL:
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

## Painel 3 — Pinot

### URLs

- Frontend: `http://localhost:5175`
- API: `http://localhost:8082/docs`
- Controller UI: `http://localhost:9001`
- Broker SQL/API: `http://localhost:8099`
- Health API: `http://localhost:8082/health`

### Fonte de dados

- Backend de leitura: Apache Pinot
- Alimentação: tabela realtime Kafka `ledger_events`
- Debug: `http://localhost:8090/debug/pinot-realtime`
- Catálogo operacional agregado: `http://localhost:8082/api/v1/master-data/overview`

### Verificações rápidas

1. `make health-pinot`
2. `make smoke-pinot`
3. Validar serviços:
   - `docker compose ps pinot-zookeeper pinot-controller pinot-broker pinot-server api-pinot frontend-pinot`
4. Testar query no Broker:
   - `curl -X POST http://localhost:8099/query/sql -H 'Content-Type: application/json' -d '{"sql":"SELECT COUNT(*) AS c FROM ledger_events"}'`
5. Conferir eventos explícitos novos:
   - `curl -fsS 'http://localhost:8082/api/v1/dashboard/entries?limit=80' | grep 'ontology_event_type'`

### Master data e plano de contas

- O frontend Pinot agora expõe um painel dedicado de catálogo com identidade da empresa, canais, produtos e plano de contas.
- O plano de contas cobre caixa, bancos, tributos recuperáveis, estoque, fornecedores, tributos a recolher, receita, devoluções, CMV, frete e despesas bancárias.
- O card de fechamento do BP mostra, em tempo real, `Ativos` versus `Passivos + Patrimônio` e a `difference` calculada na API.

## Smoke contábil estrito

- `make smoke-startup` valida automaticamente o resumo expandido de qualquer backend ativo.
- Quando `RUN_PRODUCER_ON_START=true`, o smoke verifica:
   - `net_revenue = revenue - returns`
   - `net_income = net_revenue - expenses`
   - `assets.total = total_liabilities_and_equity`
   - `difference = 0`

## Versionamento de schema (AVRO)

- Schemas versionados em:
   - `shared/schemas/avro/accounting_event_v1.avsc`
   - `shared/schemas/avro/accounting_event_v2.avsc`
- O producer valida eventos contra AVRO via `SCHEMA_MAJOR_VERSION`.

## Conexões analíticas por painel

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
