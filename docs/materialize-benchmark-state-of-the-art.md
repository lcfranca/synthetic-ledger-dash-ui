# Materialize no Benchmark: Mudancas Estrategicas, Conceituais e Arquiteturais

## 1. Premissa

Introduzir Materialize neste benchmark nao e apenas adicionar mais um backend OLAP. Materialize muda a classe do experimento: sai de um benchmark entre motores de leitura analitica e entra em comparacao com um sistema de incremental view maintenance orientado a streams.

Isso obriga o benchmark a separar com mais rigor tres camadas:

- verdade canonica do evento
- materializacao incremental consultavel
- continuidade visual do frontend

ClickHouse, Pinot e Druid participam hoje principalmente como backends de leitura e materializacao. Materialize, por sua natureza, tende a ocupar uma posicao intermediaria entre stream processor, banco de views incrementais e serving layer.

## 2. Mudanca Estrategica

Para o benchmark continuar justo, Materialize nao pode ser encaixado como se fosse apenas mais um adaptador SQL. Ele exige uma pista propria de avaliacao.

O benchmark passa a precisar de dois eixos comparativos:

1. bancos de consulta quente e materializacao analitica: ClickHouse, Pinot, Druid
2. banco de derivacao incremental streaming-first: Materialize

Sem essa separacao, o resultado seria conceitualmente viciado. Materialize sera naturalmente melhor em propagacao incremental de views se receber queries e topologias desenhadas para esse paradigma, enquanto ClickHouse e Pinot serao naturalmente mais fortes em serving analitico, scans, agregacoes livres e read models mais desacoplados.

## 3. Mudanca Conceitual

Hoje o repositorio assume um fluxo dominante:

- produtor emite evento canonico
- storage-writer deriva ledger entries
- backend consulta snapshot materializado
- websocket preserva continuidade visual

Com Materialize, surge uma alternativa legitima:

- produtor emite evento canonico
- fluxo entra em fonte streaming relacional
- views incrementais mantidas continuamente servem o snapshot
- frontend pode consumir snapshots incrementais muito mais proximos do fluxo

Isso significa que o benchmark precisa responder a uma pergunta mais refinada:

O sistema quer comparar motores de consulta sobre read models ja escritos, ou motores que tambem sao parte do proprio mecanismo de manutencao incremental do read model?

Materialize cai fortemente no segundo caso.

## 4. Mudancas Arquiteturais Necessarias

### 4.1. Nova topologia de ingestao

Materialize deve receber uma trilha propria a partir do ledger canonico, nao a partir de snapshots REST.

A topologia recomendada para o benchmark e:

- Kafka continua como barramento canonico
- `ledger-entries-v1` vira fonte primaria para Materialize
- Materialize define sources, envelopes e views derivadas para BP, DRE, sales workspace e catalogos
- a API Materialize consulta views incrementais especializadas

Em outras palavras, Materialize deve entrar no benchmark no mesmo nivel em que hoje o ClickHouse recebe replay do ledger, mas com modelagem de views incrementais nativas.

### 4.2. API dedicada

Nao e recomendavel esconder Materialize atras de um adaptador identico aos outros sem extensoes. O backend deve ter rota propria, por exemplo:

- `api_materialize/`

Motivos:

- Materialize tem semantica especifica de fonte, view e refresh incremental
- algumas queries vao precisar ser reescritas para aproveitar views materializadas nativas
- o benchmark deve permitir diagnostico proprio de lag, hydration e invalidez incremental

### 4.3. Frontend com estrategia propria

Materialize pede um frontend proprio ou um modo proprio do frontend compartilhado.

O comportamento recomendado e:

- websocket continua sendo responsavel pela continuidade perceptual
- snapshots do Materialize passam a ser usados como ancora autoritativa incremental de alta frequencia
- o frontend precisa expor explicitamente quando esta em `incremental-authoritative mode`

Isso e diferente de Pinot, onde o push-first puro funciona bem, e diferente de ClickHouse, onde um modo hibrido push + authoritative resync e mais robusto.

### 4.4. Observabilidade adicional

Materialize exige metricas novas no benchmark:

- lag entre Kafka offset e view consultavel
- custo de manutencao incremental por view
- impacto de cardinalidade crescente sobre recomputacao incremental
- latencia entre evento e visibilidade em view derivada
- estabilidade de joins incrementais e agregacoes por janela

Sem isso, o benchmark ficaria superficial e penalizaria ou favoreceria Materialize injustamente.

## 5. Mudancas no Contrato de Benchmark

O benchmark precisa passar a registrar, por backend:

- tipo de read model: pull-analytic, hot-analytic, incremental-streaming
- mecanismo principal de convergencia visual: local projection, snapshot quente, incremental view
- custo operacional local
- complexidade de modelagem contábil incremental

Para Materialize, devem existir cenarios dedicados:

- alta ingestao com joins incrementais
- alta cardinalidade em dimensoes comerciais
- atualizacao de BP/DRE sob pressao de eventos compostos
- impacto de retractions, returns e ajustes financeiros

## 6. Mudancas no Storage Writer

O `storage_writer` precisa ganhar um adapter proprio, mas o papel desse adapter deve ser diferente.

Em vez de apenas inserir linhas finais, ele deve ser capaz de:

- declarar ou bootstrapar sources/views no Materialize
- opcionalmente publicar a trilha canonica com metadata suficiente para deduplicacao
- manter um contrato claro de idempotencia para replays

O adapter para Materialize deve ser isolado dos adapters de write-heavy batch-like. Caso contrario, o benchmark vai desperdiçar a principal vantagem do sistema.

## 7. Mudancas no Modelo de Benchmarking

Para manter justica experimental, o benchmark deve explicitar que existem agora duas categorias:

### Categoria A: motores de consulta/materializacao

- ClickHouse
- Pinot
- Druid

### Categoria B: motores de manutencao incremental de views

- Materialize

Depois, uma terceira visao comparativa pode consolidar tudo sob criterios transversais:

- tempo para primeira leitura util
- latencia de convergencia do painel
- robustez sob replay
- custo cognitivo de operacao
- poder de modelagem contabil

## 8. Juizo Arquitetural

Materialize faz sentido neste benchmark se o objetivo for medir nao apenas quem responde queries rapido, mas quem melhor reduz a distancia entre evento canonico e estado derivado consultavel.

Ele nao substitui automaticamente ClickHouse ou Pinot. Em vez disso, introduz uma nova hipotese de arquitetura:

talvez o backend mais justo para este problema nao seja apenas um OLAP quente, mas um sistema de views incrementais que viva mais perto do stream.

Se essa hipotese for incorporada, o benchmark sobe de nivel e passa a comparar paradigmas, nao apenas produtos.

## 9. Recomendacao Pratica

Para a introducao correta do Materialize neste repositorio:

1. criar `api_materialize` e `materialize_adapter`
2. alimentar Materialize diretamente a partir de `ledger-entries-v1`
3. modelar views incrementais dedicadas para summary, entries, sales workspace, accounts e products
4. introduzir um modo frontend proprio: `materialize-authoritative`
5. expandir o benchmark com metricas de lag incremental, retractions e custo de view maintenance

Sem essas mudancas, Materialize entraria no benchmark de forma conceitualmente injusta e arquiteturalmente subutilizada.

## 10. Plano de Implementacao em Checklist

- [x] 1. Criar a pista paralela de infraestrutura do Materialize no `docker-compose.yaml`, com `materialized`, `api-materialize` e `frontend-materialize`, portas dedicadas e limites de memoria/CPU separados dos stacks analiticos.
- [x] 2. Expandir `scripts/stack-selection.sh`, `Makefile` e variaveis de ambiente para aceitar `materialize` em `ACTIVE_STACKS`, resolvendo services, health checks, smoke tests e frontend dedicado sem afetar ClickHouse, Druid e Pinot.
- [x] 3. Definir um namespace isolado de configuracao no `.env.example` para Materialize: broker Kafka, URL SQL, usuario/senha, database, schema, lag targets e tuning de compaction/checkpoint apropriados ao ambiente local.
- [x] 4. Implementar um adapter de bootstrap em `storage_writer` com papel proprio para Materialize: criar conexoes Kafka, sources, tables de staging, views materializadas e contratos de idempotencia/replay em vez de escrever snapshots finais linha a linha.
- [x] 5. Modelar uma trilha canonica `ledger-entries-v1` para Materialize com envelope, deduplicacao por `entry_id` e semantica de upsert/retraction para returns, ajustes e revisoes financeiras.
- [x] 6. Criar `api_materialize/` como backend dedicado, com queries desenhadas para ler views incrementais especializadas de `summary`, `entries`, `sales_workspace`, `accounts_catalog` e `products_catalog`, sem adaptar Materialize como se fosse apenas mais um SQL backend generico.
- [x] 7. Expor no `api_materialize` metricas de prontidao e observabilidade especificas: lag entre offset Kafka e visibilidade SQL, idade da ultima atualizacao por view, hidracao inicial, retractions pendentes e custo de refresh incremental.
- [x] 8. Estender `realtime_gateway` para suportar `materialize` como backend autoritativo streaming-first, com snapshots incrementais de alta frequencia, telemetria propria e filtros suportados alinhados as views realmente materializadas.
- [x] 9. Criar um frontend proprio `frontend-materialize` ou um modo dedicado no frontend compartilhado com identidade explicita de `materialize-authoritative`, exibindo ao usuario quando o painel esta ancorado em incremental views e quando esta apenas em projecao local temporaria.
- [x] 10. Espalhar o modo Materialize nos frontends das outras stacks como opcao comparativa, preservando a mesma taxonomia visual de feed, lag, authoritative snapshot e observabilidade para que a avaliacao entre paradigmas seja justa.
- [x] 11. Implementar health/smoke/verify especificos no `Makefile`: `health-materialize`, `smoke-materialize`, `verify-stream-materialize` e `verify-projection-materialize`, com probes de websocket e de SQL incremental.
- [x] 12. Criar um conjunto de objetos SQL state-of-the-art no Materialize: sources Kafka, tables de normalizacao, materialized views por dominio contabil e indices apropriados aos filtros usados nos dashboards.
- [x] 13. Projetar cenarios de benchmark dedicados ao paradigma incremental: alta ingestao, alta cardinalidade, joins incrementais entre ledger e master data, retractions por devolucao e pressao de replay de offsets antigos.
- [x] 14. Registrar no benchmark metadados por backend para comparacao justa: categoria do motor, mecanismo dominante de convergencia visual, custo operacional, custo cognitivo e robustez a replay/cold start.
- [x] 15. Validar o Materialize no seu maximo potencial antes da comparacao final: ajustar topologia de views, reduzir consultas ad hoc na API, usar snapshots incrementais autoritativos no gateway e eliminar qualquer dependencia desnecessaria de polling REST.

Status operacional atual da trilha Materialize:

- `make run ENV_FILE=.env.materialize` sobe a pista dedicada com `materialized`, `storage-writer`, `api-materialize`, `realtime-gateway` e `frontend-materialize`.
- `make populate ENV_FILE=.env.materialize` alimenta a trilha canonica e permite a hidratacao das views incrementais.
- `make smoke-materialize ENV_FILE=.env.materialize` retorna summary, entries e readiness com dados reais.
- `make health-materialize ENV_FILE=.env.materialize` confirma API, frontend, bootstrap Materialize, realtime stream e realtime projection em runtime local.

## 11. Cenarios de Benchmark Incremental Fechados

Para que Materialize entre na comparacao como motor de manutencao incremental de views, o benchmark passa a registrar os quatro cenarios abaixo como trilha oficial da categoria `incremental-streaming`:

### Cenario A. Alta ingestao com snapshot autoritativo incremental

- Objetivo: medir latencia entre `entry.created` no Kafka e `dashboard.snapshot` consultavel no frontend Materialize.
- Carga: produtor com alta taxa de eventos e `RUN_PRODUCER_ON_START=true`.
- Leituras medidas: `/health` do `api-materialize`, `/debug/materialize-bootstrap` e stream websocket do gateway em `frontend-materialize`.
- Metricas obrigatorias: `view_lag_ms`, `freshness_ms`, tempo para primeiro snapshot util, taxa de snapshots emitidos por segundo e backlog de hidratacao.

### Cenario B. Alta cardinalidade comercial

- Objetivo: medir o custo de manter views incrementais quando `customer_name`, `product_name`, `channel` e `order_id` crescem rapidamente.
- Carga: geracao de vendas com combinacoes amplas de dimensoes comerciais e filtros ativos por recorte.
- Leituras medidas: `sales_workspace`, `products_catalog`, `accounts_catalog` e `workspace` filtrado via gateway autoritativo.
- Metricas obrigatorias: latencia p50/p95 do snapshot filtrado, crescimento de lag incremental, estabilidade de joins e custo de cold filter bootstrap.

### Cenario C. Joins incrementais entre ledger e master data

- Objetivo: verificar se a trilha continua consistente quando os dashboards dependem de enriquecimento por contas, produtos e contexto comercial.
- Carga: fluxo de ledger com master data ativo e consultas concorrentes por visoes `summary`, `workspace` e catálogos.
- Leituras medidas: API Materialize, `master-data` overview e snapshots websocket por backend `materialize`.
- Metricas obrigatorias: tempo para convergencia apos update de dimensao, estabilidade de agregacao por conta/produto e idade da ultima view consultavel.

### Cenario D. Retracoes e replay de offsets antigos

- Objetivo: medir resiliência da trilha incremental sob devolucoes, ajustes financeiros e reprocessamento.
- Carga: eventos de `return`, ajustes de revisao e replay controlado do topico canonico `ledger-entries-v1`.
- Leituras medidas: `summary`, `entries`, `workspace`, observabilidade do gateway e bootstrap do Materialize.
- Metricas obrigatorias: tempo de reconvergencia, `pending_retractions`, robustez a replay/cold start e diferença contabil final do BP.

## 12. Registro de Metadados do Benchmark

O benchmark comparativo passa a usar o seguinte registro de metadados por backend para classificar corretamente o paradigma de cada stack antes da comparacao final:

O registro versionado fica em `docs/benchmark-backend-registry.yaml` para que cenarios e metadados possam ser consumidos pelo benchmark sem depender apenas desta narrativa arquitetural.

| Backend | Categoria | Read model dominante | Convergencia visual dominante | Custo operacional local | Custo cognitivo | Robustez a replay/cold start |
| --- | --- | --- | --- | --- | --- | --- |
| ClickHouse | hot-analytic | snapshot consultavel derivado por fan-out Kafka | push + authoritative resync no gateway | medio | medio | alta em replay, media em cold start de stack completa |
| Druid | hot-analytic | datasource realtime orientado a ingestao continua | push + authoritative filtered snapshot | alto | alto | media, com sensibilidade maior a supervisor/router/metadata |
| Pinot | hot-analytic | realtime table Kafka com serving SQL de baixa latencia | push-first com projecao local no frontend | medio | medio | media-alta, com dependencia de bootstrap do realtime table |
| Materialize | incremental-streaming | views incrementais autoritativas sobre `ledger-entries-v1` | snapshot autoritativo incremental no gateway | medio | medio-alto | alta, desde que source/view bootstrap e hydration estejam saudaveis |

Campos obrigatorios por execucao de benchmark:

- `backend_category`: `hot-analytic` ou `incremental-streaming`.
- `visual_convergence_mode`: `local-projection`, `authoritative-resync` ou `authoritative-incremental-snapshot`.
- `operational_cost_local`: estimativa qualitativa da complexidade de containers, memoria e orchestracao local.
- `cognitive_cost`: custo de modelagem e troubleshooting para manter o backend em estado produtivo.
- `replay_cold_start_grade`: classificacao final da robustez a replay, bootstrap e hidratação inicial.

## 13. Fechamento do Item 15

O estado atual da trilha Materialize fecha o item 15 com as seguintes decisoes operacionais:

- frontend Materialize opera em `snapshot-only` sobre o websocket do gateway, sem depender de projecao local por `entry.created`.
- o gateway continua como ancora autoritativa incremental e emite `dashboard.snapshot` progressivos para Materialize.
- os checks `verify-stream-materialize` e `verify-projection-materialize` passam a validar a semantica correta da trilha: snapshots autoritativos em vez de exigir apenas eventos unitarios.
- o bootstrap REST do workspace fica restrito ao seeding inicial da projecao autoritativa; a continuidade operacional segue pelo stream incremental.