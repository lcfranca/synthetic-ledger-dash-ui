# Benchmarking de Backends para Alimentacao Push de Paineis Gerenciais em Tempo Real

## Subtitulo sugerido

Uma avaliacao cientifica, arquitetural e experimental de ClickHouse, Druid, Pinot e Materialize para convergencia visual de dashboards contabeis e comerciais orientados por eventos.

## Elementos pre-textuais

### Capa

- Titulo completo.
- Subtitulo.
- Autor.
- Programa de pos-graduacao.
- Linha de pesquisa.
- Instituicao.
- Local e ano.

### Folha de rosto

- Autor.
- Titulo.
- Natureza do trabalho.
- Objetivo academico.
- Area de concentracao.
- Orientador.
- Coorientador, se houver.

### Ficha catalografica

- Termos de indexacao.
- Areas tematicas.

### Folha de aprovacao

- Banca.
- Data.
- Assinaturas.

### Dedicatória, agradecimentos e epigrafe

- Opcional conforme o programa.

### Resumo

- Problema de pesquisa.
- Objetivo geral.
- Metodologia experimental.
- Corpus tecnologico: ClickHouse, Druid, Pinot, Materialize.
- Principais metricas.
- Resultados esperados ou obtidos.
- Contribuicoes cientificas.
- Palavras-chave.

### Abstract

- Versao em ingles do resumo com keywords.

### Listas obrigatorias

- Lista de figuras.
- Lista de tabelas.
- Lista de quadros.
- Lista de abreviaturas e siglas.
- Lista de simbolos, se aplicavel.

### Sumario

- Estrutura completa do texto.

## Capitulo 1. Introducao

### 1.1 Contextualizacao do problema

- Digitalizacao da operacao empresarial e crescimento de sistemas event-driven.
- Necessidade de dashboards gerenciais near-real-time com consistencia contabil.
- Limites de arquiteturas somente pull para casos de uso de alta frequencia visual.

### 1.2 Problema cientifico

- Como comparar, de forma justa, backends com paradigmas distintos para alimentar paineis e frontends em tempo real por push.
- Tensao entre throughput, latencia perceptual, corretude contabil, custo operacional e proximidade ao stream.

### 1.3 Hipotese central

- Backends de manutencao incremental de views tendem a reduzir a distancia entre evento canonico e estado derivado consultavel, mas podem impor custos cognitivos e arquiteturais diferentes dos motores analiticos quentes.

### 1.4 Objetivo geral

- Construir e defender um benchmark state-of-the-art para avaliar backends capazes de servir paineis contabeis e comerciais near-real-time por push, preservando corretude financeira e convergencia visual.

### 1.5 Objetivos especificos

- Definir o contrato funcional do caso de uso.
- Descrever e instrumentar cada backend com rigor arquitetural.
- Propor uma taxonomia de metricas de desempenho, corretude e operacionalidade.
- Executar benchmark comparativo reprodutivel.
- Interpretar resultados sob lentes de sistemas distribuidos, OLAP e streaming.

### 1.6 Questoes de pesquisa

- Qual backend minimiza melhor o tempo entre evento e visibilidade gerencial?
- Qual backend preserva melhor o fechamento contabil em condicoes de carga e replay?
- Qual estrategia de convergencia visual produz menor latencia percebida no frontend?
- Quais sao os custos operacionais e cognitivos de cada paradigma?

### 1.7 Justificativa

- Relevancia industrial para observabilidade gerencial em tempo real.
- Relevancia academica para a intersecao entre event sourcing, OLAP quente, push architectures e incremental view maintenance.

### 1.8 Contribuicoes esperadas

- Taxonomia formal do problema.
- Benchmark reproduzivel para o caso de uso.
- Grade metrica multi-dimensional.
- Analise comparativa entre paradigmas e nao apenas entre produtos.

## Capitulo 2. Fundamentacao Teorica

### 2.1 Event sourcing, ledger canonico e corretude contabil

- Imutabilidade.
- Dupla entrada.
- Time-travel.
- Idempotencia e replay.
- Implicacoes para modelos de leitura.

### 2.2 Sistemas push, pull e hibridos

- Polling periodico.
- Websocket e server push.
- Push-first com ressincronizacao autoritativa.
- Snapshots incrementais.

### 2.3 OLAP quente, HTAP e streaming relational systems

- Definicoes.
- Diferencas conceituais.
- Trade-offs de modelagem.

### 2.4 Incremental view maintenance

- Algebra de diferencas.
- Manutencao incremental de agregacoes.
- Retracoes.
- Joins incrementais.
- Limites praticos em alta cardinalidade.

### 2.5 Latencia percebida no frontend

- Tempo para primeira leitura util.
- Tempo de convergencia visual.
- Continuidade perceptual.
- Consistencia eventual percebida.

### 2.6 Sistemas distribuidos e validade experimental

- Cold start.
- Warm state.
- Jitter.
- Variabilidade intra-rodada e inter-rodada.
- Ameaças à validade.

## Capitulo 3. Estado da Arte Tecnologico

### 3.1 ClickHouse

- Arquitetura interna.
- Motor MergeTree e derivados.
- Armazenamento colunar, partes e merges.
- Indexacao esparsa, compression codecs, vectorized execution.
- Kafka ingestion patterns e materialized views.
- Implicacoes para read models near-real-time.

### 3.2 Apache Druid

- Segmentos, indexing service, coordinator, overlord, broker, router e historicals.
- Ingestao streaming com supervisor Kafka.
- Roll-up, segment generation, deep storage e metadata store.
- Planejamento de queries e latencia operacional.
- Impactos do ciclo de vida de segmentos sobre dashboards push.

### 3.3 Apache Pinot

- Controller, broker, server e realtime tables.
- Star-tree, indexing, forward index, inverted index, dictionary encoding.
- Consumo Kafka realtime e low-latency serving.
- Implicacoes de push-first com projecao local no frontend.

### 3.4 Materialize

- Timely Dataflow e Differential Dataflow como fundamento conceitual.
- Sources, subsources, progress tracking, views e materialized views.
- Incremental recomputation, monotonicidade, retracoes e determinismo.
- Semantica pgwire e particularidades SQL para workloads incrementais.
- Papel como serving layer incremental proxima do stream.

### 3.5 Comparacao conceitual entre categorias

- Motores hot-analytic versus incremental-streaming.
- Capacidade de servir snapshots autoritativos por push.
- Custo de aproximacao entre stream e estado derivado consultavel.

## Capitulo 4. Modelo do Problema e Arquitetura do Caso de Uso

### 4.1 Dominio funcional

- Eventos contabil-financeiros sinteticos.
- Painel executivo.
- Painel contabil.
- Workspace comercial.

### 4.2 Contrato canonico dos dados

- Evento de origem.
- Ledger entries.
- Catálogos e master data.
- Semantica de `entry.created` e `dashboard.snapshot`.

### 4.3 Arquitetura experimental do repositorio

- Producer.
- OpenTelemetry Collector.
- Storage writer.
- Kafka.
- APIs por backend.
- Realtime gateway.
- Frontends.

### 4.4 Estrategias de convergencia visual por backend

- ClickHouse: authoritative resync.
- Druid: filtered authoritative snapshot.
- Pinot: push-first com projecao local.
- Materialize: authoritative incremental snapshot.

## Capitulo 5. Metodologia de Benchmark

### 5.1 Tipo de pesquisa

- Pesquisa experimental aplicada com carater comparativo e instrumentacao controlada.

### 5.2 Unidade de analise

- Rodada individual por backend.
- Ambiente local controlado.
- Janela maxima de 10 minutos por execucao.

### 5.3 Variaveis independentes

- Backend selecionado.
- Classe de workload.
- Presenca ou ausencia de filtros.
- Estado cold start ou warm state.

### 5.4 Variaveis dependentes

- Latencias API, SQL e websocket.
- Tempo de convergencia visual.
- Corretude contabil.
- Uso de CPU, memoria e disco.
- Robustez a replay e cold start.

### 5.5 Controle experimental

- Um backend por vez.
- Mesmo dataset logico.
- Mesma familia de consultas.
- Mesmo hardware e limites de recurso.
- Scripts dedicados por backend.

### 5.6 Cenarios experimentais

- Alta ingestao.
- Alta cardinalidade.
- Joins incrementais com master data.
- Retracoes e replay.
- Estabilidade operacional em janela fixa.

### 5.7 Instrumentacao

- Scripts shell/Node/Python por backend.
- Coleta via API, SQL, websocket, debug endpoints e `docker stats`.
- Persistencia estruturada por rodada.

### 5.8 Critérios de aceitacao

- BP fechado.
- Ausencia de perda de eventos.
- Disponibilidade da API.
- Contrato consistente entre frontend e backend.

## Capitulo 6. Definicao Formal das Metricas

### 6.1 Metricas de latencia

- p50, p95, p99 de `/summary`.
- p50, p95, p99 de `/workspace`.
- Tempo para primeiro snapshot util.
- Tempo entre evento e refletancia no frontend.

### 6.2 Metricas de corretude contabil

- `balance_sheet.difference`.
- Equilibrio entre ativos e passivos mais patrimonio.
- Consistencia entre entradas detalhadas e agregados.

### 6.3 Metricas de estabilidade do realtime

- Taxa de snapshots por segundo.
- Taxa de eventos `entry.created` observados.
- Lag incremental.
- Freshness.

### 6.4 Metricas de completude de contrato

- Disponibilidade de catalogos.
- Populacao de visoes executivas.
- Integridade de filtros.

### 6.5 Metricas operacionais

- CPU media e pico.
- Memoria media e pico.
- Disco consumido por rodada.
- Tempo de bootstrap para estado verde.

### 6.6 Metricas de reprodutibilidade e robustez

- Variancia por repeticao.
- Sensibilidade a cold start.
- Sensibilidade a replay.

## Capitulo 7. Procedimentos de Coleta

### 7.1 Preparacao do ambiente

- Limpeza completa da stack.
- Seleção de um unico backend ativo.
- Warm-up controlado.

### 7.2 Execucao dos scripts de coleta

- Script de subida.
- Script de warm-up.
- Script de coleta SQL/API.
- Script de coleta websocket.
- Script de recursos de container.
- Script de consolidacao.

### 7.3 Janela de tempo por rodada

- Maximo de 10 minutos.
- Segmentacao: bootstrap, warm-up, coleta e teardown.

### 7.4 Armazenamento dos resultados

- JSON bruto.
- CSV consolidado.
- Metadados de commit, stack e timestamp.

## Capitulo 8. Resultados

### 8.1 Disponibilidade operacional por backend

### 8.2 Desempenho de APIs e SQL

### 8.3 Convergencia visual no frontend

### 8.4 Corretude contabil e estabilidade de agregados

### 8.5 Custos operacionais e cognitivos

### 8.6 Sintese comparativa entre paradigmas

## Capitulo 9. Discussao

### 9.1 Interpretacao dos resultados a luz da teoria

### 9.2 Quando motores analiticos quentes sao superiores

### 9.3 Quando manutencao incremental de views e superior

### 9.4 Limites do benchmark proposto

### 9.5 Generalizacao para outros dominios

## Capitulo 10. Ameacas a Validade

### 10.1 Validade interna

### 10.2 Validade externa

### 10.3 Validade de construto

### 10.4 Validade de conclusao

## Capitulo 11. Conclusao

### 11.1 Retomada da pergunta de pesquisa

### 11.2 Contribuicoes efetivas

### 11.3 Implicacoes para engenharia de sistemas de dashboards push

### 11.4 Trabalhos futuros

- Benchmark distribuido em infraestrutura dedicada.
- Inclusao de mais motores HTAP/streaming.
- Validacao com cargas reais e usuarios humanos.

## Referencias

- Livros e artigos sobre OLAP, event sourcing, streaming systems, incremental view maintenance, Timely Dataflow, Differential Dataflow, ClickHouse, Druid, Pinot, Materialize, HCI de tempo real e observabilidade distribuida.

## Apendices

### Apendice A. Especificacao do dataset sintetico

### Apendice B. Scripts de coleta por backend

### Apendice C. Consultas SQL versionadas

### Apendice D. Configuracao completa do ambiente experimental

### Apendice E. Tabelas completas de resultados

## Anexos opcionais

- Diagramas de arquitetura.
- JSON schemas.
- Logs exemplares de warm-up, replay e degradacao.