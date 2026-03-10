# Modelo do Problema e Arquitetura Experimental

## Domínio funcional

O caso de uso deste relatório é um ambiente de eventos contábil-financeiros sintéticos capaz de alimentar painéis executivos, contábeis e comerciais em tempo quase real. O domínio experimental inclui eventos de venda, frete, devolução, pagamento a fornecedor, transferências de tesouraria e pagamento de juros de capital de giro. Cada evento de domínio é traduzido em lançamentos contabilmente coerentes, respeitando a disciplina de dupla entrada.

O objetivo funcional não é apenas preservar um feed de eventos recentes, mas produzir três classes de leitura: um resumo executivo, um workspace detalhado e coleções filtráveis de entries e catálogos. Dessa forma, a stack experimental aproxima o benchmark de um contexto realista, em que o frontend depende simultaneamente de granularidade transacional, agregados consolidados e semântica contábil robusta.

## Contrato canônico dos dados

O contrato canônico do sistema é centrado no tópico Kafka `ledger-entries-v1`. O `storage_writer` executa a derivação contábil uma única vez e publica nesse stream os lançamentos normalizados. Essa escolha evita que cada backend precise reinterpretar o evento de negócio bruto de maneira autônoma, reduzindo o viés metodológico introduzido por pipelines de ingestão semanticamente distintos.

O contrato funcional compartilhado pelos frontends e APIs inclui, entre outros elementos:

1. `entry.created` como unidade de atualização transacional.
2. `dashboard.snapshot` como envelope autoritativo de reconciliação visual.
3. Endpoints de resumo, workspace, entries, filtros e master data.
4. Invariantes contábeis verificáveis a partir do mesmo ledger.

Essa combinação garante que a comparação entre backends ocorra sobre uma base funcional constante, mesmo quando a estratégia de serving varia.

## Arquitetura do repositório

O repositório foi estruturado como monorepo operacional, contendo producer, OpenTelemetry Collector, Kafka, storage writer, APIs por backend, gateway de realtime, frontends especializados e scripts de benchmark. O fluxo macro pode ser descrito da seguinte forma:

1. O `producer` gera eventos sintéticos de negócio.
2. O `otel-collector` roteia a ingestão para o pipeline principal.
3. O `storage_writer` consolida a semântica contábil e publica o ledger canônico.
4. Cada backend consome o ledger por sua própria estratégia de ingestão.
5. APIs especializadas expõem o contrato de leitura ao frontend.
6. O `realtime_gateway` coordena stream e snapshots autoritativos para convergência visual.

Essa arquitetura é cientificamente relevante porque a unidade real de análise deixa de ser o banco isolado e passa a ser a composição entre banco, camada de consulta, gateway e frontend.

## Estratégias de convergência visual por backend

Cada backend foi integrado ao mesmo problema funcional, mas com uma estratégia de convergência visual coerente com sua natureza interna:

1. ClickHouse: `authoritative resync`, com snapshots autoritativos combinados a eventos.
2. Druid: `filtered authoritative snapshot`, privilegiando snapshots consistentes sob filtros.
3. Pinot: `push-first`, com projeção local no frontend e reancoragem autoritativa.
4. Materialize: `authoritative incremental snapshot`, aproximando o frontend de views incrementais mantidas sobre o stream.

Essa diversidade permite comparar não apenas a performance do backend, mas a adequação de cada paradigma a formas distintas de alimentar o frontend sem degradar consistência visual.

## Observabilidade e pontos de controle

O ambiente inclui endpoints de health e debug para master data, storage writer, realtime gateway e trilhas específicas de cada backend. Essa camada de observabilidade é parte do desenho experimental, pois permite capturar transições de estado, bootstrap, degradação e readiness sem depender apenas de logs ad hoc. Em particular, a trilha Materialize expõe um endpoint de bootstrap incremental com métricas de hidratação, offsets Kafka e lag de views, o que a torna especialmente apropriada para avaliação de comportamento incremental real.

## Consequências metodológicas

O modelo experimental adotado neste relatório possui duas implicações metodológicas principais. Primeiro, ele preserva um contrato funcional comum e um ledger canônico compartilhado. Segundo, ele admite que o modo de convergência visual é parte integrante do backend avaliado. Como consequência, o benchmark deixa de ser um teste simplificado de throughput e se torna uma comparação de arquiteturas de serving para dashboards gerenciais orientados por eventos.