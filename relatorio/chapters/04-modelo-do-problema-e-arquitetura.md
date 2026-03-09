# Modelo do Problema e Arquitetura Experimental

## 4.1 Dominio funcional

O caso de uso deste relatorio e um ambiente de eventos contabil-financeiros sinteticos capaz de alimentar paineis executivos, contabeis e comerciais em tempo quase real. O dominio experimental inclui eventos de venda, frete, devolucao, pagamento a fornecedor, transferencias de tesouraria e pagamento de juros de capital de giro. Cada evento de dominio e traduzido em lancamentos contabilmente coerentes, respeitando a disciplina de dupla entrada.

O objetivo funcional nao e apenas preservar um feed de eventos recentes, mas produzir tres classes de leitura: um resumo executivo, um workspace detalhado e colecoes filtraveis de entries e catalogos. Dessa forma, a stack experimental aproxima o benchmark de um contexto realista, em que o frontend depende simultaneamente de granularidade transacional, agregados consolidados e semantica contabil robusta.

## 4.2 Contrato canonico dos dados

O contrato canonico do sistema e centrado no topico Kafka `ledger-entries-v1`. O `storage_writer` executa a derivacao contabil uma unica vez e publica nesse stream os lancamentos normalizados. Essa escolha evita que cada backend precise reinterpretar o evento de negocio bruto de maneira autônoma, reduzindo o vies metodologico introduzido por pipelines de ingestao semanticamente distintos.

O contrato funcional compartilhado pelos frontends e APIs inclui, entre outros elementos:

1. `entry.created` como unidade de atualizacao transacional.
2. `dashboard.snapshot` como envelope autoritativo de reconciliacao visual.
3. Endpoints de resumo, workspace, entries, filtros e master data.
4. Invariantes contabeis verificaveis a partir do mesmo ledger.

Essa combinacao garante que a comparacao entre backends ocorra sobre uma base funcional constante, mesmo quando a estrategia de serving varia.

## 4.3 Arquitetura do repositorio

O repositorio foi estruturado como monorepo operacional, contendo producer, OpenTelemetry Collector, Kafka, storage writer, APIs por backend, gateway de realtime, frontends especializados e scripts de benchmark. O fluxo macro pode ser descrito da seguinte forma:

1. O `producer` gera eventos sinteticos de negocio.
2. O `otel-collector` roteia a ingestao para o pipeline principal.
3. O `storage_writer` consolida a semantica contabil e publica o ledger canonico.
4. Cada backend consome o ledger por sua propria estrategia de ingestao.
5. APIs especializadas expõem o contrato de leitura ao frontend.
6. O `realtime_gateway` coordena stream e snapshots autoritativos para convergencia visual.

Essa arquitetura e cientificamente relevante porque a unidade real de analise deixa de ser o banco isolado e passa a ser a composicao entre banco, camada de consulta, gateway e frontend.

## 4.4 Estrategias de convergencia visual por backend

Cada backend foi integrado ao mesmo problema funcional, mas com uma estrategia de convergencia visual coerente com sua natureza interna:

1. ClickHouse: `authoritative resync`, com snapshots autoritativos combinados a eventos.
2. Druid: `filtered authoritative snapshot`, privilegiando snapshots consistentes sob filtros.
3. Pinot: `push-first`, com projecao local no frontend e reancoragem autoritativa.
4. Materialize: `authoritative incremental snapshot`, aproximando o frontend de views incrementais mantidas sobre o stream.

Essa diversidade permite comparar nao apenas a performance do backend, mas a adequacao de cada paradigma a formas distintas de alimentar o frontend sem degradar consistencia visual.

## 4.5 Observabilidade e pontos de controle

O ambiente inclui endpoints de health e debug para master data, storage writer, realtime gateway e trilhas especificas de cada backend. Essa camada de observabilidade e parte do desenho experimental, pois permite capturar transicoes de estado, bootstrap, degradacao e readiness sem depender apenas de logs ad hoc. Em particular, a trilha Materialize expõe um endpoint de bootstrap incremental com metricas de hidratacao, offsets Kafka e lag de views, o que a torna especialmente apropriada para avaliacao de comportamento incremental real.

## 4.6 Consequencias metodologicas

O modelo experimental adotado neste relatorio possui duas implicacoes metodologicas principais. Primeiro, ele preserva um contrato funcional comum e um ledger canonico compartilhado. Segundo, ele admite que o modo de convergencia visual e parte integrante do backend avaliado. Como consequencia, o benchmark deixa de ser um teste simplificado de throughput e se torna uma comparacao de arquiteturas de serving para dashboards gerenciais orientados por eventos.