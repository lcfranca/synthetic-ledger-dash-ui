# Estado da Arte Tecnologico

## 3.1 Introducao

O estado da arte relevante para esta pesquisa nao pode ser organizado apenas por ordem cronologica de lancamento de produtos ou por comparacoes superficiais de benchmark industrial. A questao central e identificar como diferentes familias de sistemas materializam, em sua arquitetura interna, distintas respostas para o mesmo problema: transformar fluxos de eventos em estado derivado consultavel com baixa latencia, alta confiabilidade e custo operacional aceitavel. Nesse sentido, ClickHouse, Druid, Pinot e Materialize nao devem ser lidos como variacoes marginais de uma mesma classe, mas como respostas arquiteturais distintas a tensoes entre ingestao, armazenamento, indexacao, agregacao, invalidacao e serving.

Este capitulo apresenta cada backend em profundidade suficiente para sustentar uma comparacao cientifica. O criterio de analise nao sera marketing de produto, mas: arquitetura interna, modelo de armazenamento, caminho de ingestao, estrategia de indexacao, semantica de atualizacao, implicacoes para dashboards push-oriented, pontos fortes, fragilidades e adequacao ao problema do repositorio.

## 3.2 ClickHouse

### 3.2.1 Classe arquitetural

ClickHouse e um sistema de armazenamento colunar orientado a analise de baixa latencia em larga escala. Sua forca decorre da combinacao entre armazenamento em colunas, compressao agressiva, particionamento por partes, leitura vetorizada e uma familia de motores `MergeTree` desenhados para otimizar scans seletivos, filtros e agregacoes. Em termos de paradigma, ClickHouse opera como um motor `hot-analytic`: ele se torna especialmente eficaz quando o read model relevante ja se encontra materializado em tabelas adequadas e quando a consulta pode explorar a localidade estatistica e os mecanismos de pruning do armazenamento colunar.

### 3.2.2 Internals relevantes

No cerne do ClickHouse estao as `parts`, unidades fisicas de armazenamento criadas por insercoes e posteriormente consolidadas por merges assincronos. Esse desenho oferece uma relacao favoravel entre throughput de ingestao e custo de leitura, mas tambem implica um comportamento temporal especifico: o estado consultavel pode depender do ciclo de merges, da materializacao de visoes auxiliares e da organizacao da ordenacao primaria. A indexacao e deliberadamente esparsa. Em vez de um B-tree tradicional por linha, ClickHouse aposta em marcas, granulos e ordenacao por chave primaria para eliminar grandes faixas de dados com custo baixo.

Essa estrutura e extremamente eficiente para workloads em que filtros e agregacoes podem ser mapeados sobre colunas bem compressiveis e chaves de ordenacao adequadas. No contexto de dashboards gerenciais, isso favorece queries de resumo, slicing por dimensao e leitura de subconjuntos recentes, especialmente quando o fan-out para o ClickHouse ja produziu um read model adequado. Em contrapartida, ClickHouse nao e, por natureza, um mecanismo de manutencao incremental de views arbitrarias acoplado ao stream em tempo continuo. Sua forca reside mais no serving analitico de um estado quente do que na propagacao incremental fina entre evento e view complexa.

### 3.2.3 Ingestao e serving no caso de uso

No repositorio, ClickHouse recebe o fluxo canonico a partir do `storage_writer`, que executa fan-out do ledger contabil para o backend. Isso preserva uma separacao clara entre derivacao contabil e serving analitico. A vantagem e metodologica e operacional: a logica financeira central permanece no writer, enquanto ClickHouse se concentra em responder bem sobre uma tabela consultavel. Para um benchmark honesto, isso e importante, porque evita atribuir ao banco responsabilidades de semantica de dominio que pertencem ao pipeline canonico.

Em dashboards push-oriented, ClickHouse tende a funcionar melhor com estrategia hibrida: eventos podem sustentar continuidade visual imediata, mas snapshots autoritativos periodicos do gateway oferecem a ancoragem necessaria para filtros, agregados e reconciliacao. Isso o coloca numa posicao forte para consultas de baixa latencia, mas menos naturalmente alinhada a snapshots incrementais autoritativos de alta frequencia sob filtros compostos altamente dinamicos.

### 3.2.4 Limites e riscos

Os limites de ClickHouse, para este caso especifico, decorrem menos de desempenho bruto e mais de semantica operacional. O sistema pode responder rapidamente a queries bem ajustadas, mas nao internaliza, por si so, uma teoria de retracoes e de manutencao incremental de read models comparavel a sistemas como Materialize. Em workloads com alta taxa de correcoes, replay frequente ou necessidade de snapshots incrementais filtrados muito proximos do stream, a solucao tende a exigir mais coordenacao na API e no gateway.

### 3.2.5 Bibliografia-base de ClickHouse

- Stonebraker, M. et al. C-Store: A Column-oriented DBMS.
- Abadi, D. J.; Madden, S.; Ferreira, M. C. Integrating compression and execution in column-oriented database systems.
- ClickHouse, Inc. Documentacao tecnica oficial do ClickHouse.
- Publicacoes tecnicas e blogs de engenharia do projeto ClickHouse sobre MergeTree, skipping indexes, projections e materialized views.

## 3.3 Apache Druid

### 3.3.1 Classe arquitetural

Apache Druid e um sistema analitico distribuido fortemente orientado a ingestao de eventos e serving OLAP de baixa latencia, especialmente em cenarios de series temporais, exploracao interativa e agregacoes multidimensionais. Diferentemente de um banco monolitico, sua arquitetura explicita uma topologia de servicos com papeis distintos: `Overlord` para coordenacao de tarefas de ingestao, `Coordinator` para gestao de segmentos, `Broker` para planejamento e fan-out de consultas, `Router` para front-door HTTP e `Historicals` ou `MiddleManagers` para armazenamento e processamento de dados.

### 3.3.2 Internals relevantes

Druid organiza dados em segmentos imutaveis, particionados temporalmente e distribuiveis entre nos. A ingestao streaming via Kafka supervisor alimenta tarefas que consomem o stream, constroem segmentos e os publicam para serving. Esse desenho tem vantagens claras: baixa latencia para agregacoes sobre dados temporalmente organizados, boa escalabilidade horizontal e forte adequacao a cenarios exploratorios com filtros e group-bys. No entanto, ele introduz uma complexidade operacional significativa. O desempenho percebido nao depende apenas do motor de consulta, mas da coordenacao entre servicos, do estado do supervisor, da saude do metadata store e da disponibilidade de brokers.

Em outras palavras, Druid oferece um estado da arte importante para workloads analiticos de eventos, mas o custo de atingir esse estado da arte nao e trivial. Isso precisa aparecer no benchmark como metrica de custo operacional, cold start, transicoes de health e estabilidade do pipeline de ingestao. Um benchmark que medisse apenas latencia de consulta e ignorasse a topologia multi-servico de Druid estaria subestimando um aspecto central da tecnologia.

### 3.3.3 Druid no contexto de dashboards push-oriented

Para o caso deste projeto, Druid ocupa uma posicao interessante. Ele consome o stream canonico do ledger via supervisor Kafka e serve o painel por meio de uma API dedicada. Em termos de convergencia visual, o sistema se beneficia de snapshots autoritativos filtrados e de telemetria de pipeline, mas nao opera como um mecanismo de incremental view maintenance fino. O gateway precisa coordenar o fluxo de eventos e os snapshots do backend para preservar coerencia perceptual, especialmente quando filtros complexos entram em cena.

Isso significa que Druid e particularmente forte como backend de leitura analitica quente, mas menos natural como ancora incremental direta entre stream e frontend. Em cenarios de alta cardinalidade ou de grande volume temporal, seu modelo de segmentos e planning pode continuar competitivo; em cenarios de replay, bootstrap local e operacao com recursos restritos, a topologia multi-servico pode impor custos maiores que os observados em outras stacks.

### 3.3.4 Limites e riscos

Os principais riscos de Druid, para o caso estudado, residem na sensibilidade operacional do pipeline: supervisores em retry, dependencias entre broker e router, estado do metadata store e custo de aquecimento da stack. Em uma publicacao cientifica honesta, esses fatores nao devem ser tratados como ruido contingente. Eles sao parte do comportamento real da tecnologia em ambientes de engenharia. Assim, custo cognitivo e custo operacional local devem figurar como variaveis comparativas explicitas.

### 3.3.5 Bibliografia-base de Druid

- Yang, F. et al. Druid: A Real-Time Analytical Data Store.
- Documentacao oficial do Apache Druid.
- Publicacoes tecnicas do projeto sobre segment lifecycle, ingestion specs, roll-up, compaction e Kafka indexing service.

## 3.4 Apache Pinot

### 3.4.1 Classe arquitetural

Apache Pinot foi concebido para serving OLAP de baixa latencia em cenarios com alto volume de consultas interativas, forte exigencia de recorte dimensional e consumo continuo de streams. Sua arquitetura distribui responsabilidades entre `Controller`, `Broker` e `Server`, combinando ingestao realtime com estrategias de indexacao voltadas a consultas de baixa latencia. No ecossistema industrial, Pinot se destacou sobretudo em casos de analytics operacionais com alta taxa de leitura, grande fan-out de queries e necessidade de respostas quase imediatas para exploracao por produto.

### 3.4.2 Internals relevantes

O desenho interno de Pinot combina armazenamento colunar, dicionarios, indexes invertidos e, em alguns cenarios, estruturas como `Star-Tree` para acelerar agregacoes recorrentes. Sua proposta nao e apenas armazenar colunas, mas organizar o caminho entre consulta e dado por meio de estruturas que reduzam scanning desnecessario para workloads interativos. A ingestao realtime, baseada em consumo de streams como Kafka, torna Pinot particularmente atraente para modelos de leitura com atualizacao continua.

No entanto, o que torna Pinot tecnicamente relevante para este benchmark e sua afinidade com modos `push-first`. Quando combinado a um frontend capaz de projetar localmente parte dos eventos `entry.created`, Pinot pode servir como backend de baixa latencia para reancoragem periodica, enquanto a continuidade perceptual imediata e mantida no cliente. Trata-se de uma escolha arquitetural distinta da de Druid e da de Materialize: Pinot nao internaliza a manutencao incremental completa do estado derivado, mas tampouco depende apenas de snapshots pesados para responder com rapidez.

### 3.4.3 Estado da literatura e fontes tecnicas

Em comparacao com Druid e ClickHouse, a literatura revisada por pares explicitamente centrada em Pinot e menos consolidada como corpus academico canonico. Isso nao invalida a tecnologia; apenas exige mais cuidado bibliografico. Para uma escrita cientifica rigorosa, a base de Pinot deve combinar documentacao oficial, textos de engenharia de produtores da tecnologia e, onde disponivel, artigos tecnicos sobre realtime OLAP, indexes e serving distribuido. Em termos epistemicos, trata-se de uma area em que a literatura industrial de alta qualidade ainda ocupa parte do espaco que, em outros sistemas, foi mais formalizado por artigos classicos.

### 3.4.4 Pinot no contexto do benchmark

No repositorio, Pinot assume o papel de backend desacoplado com frontend especializado. Essa decisao e instrutiva: ela permite observar uma estrategia de convergencia visual em que o cliente participa mais ativamente do processo, enquanto o backend fornece a ancora quente para consultas autoritativas. Em cenarios de fila operacional, essa composicao pode gerar excelente latencia percebida. Em contrapartida, sua robustez depende da qualidade da projecao local, da disciplina de reconciliacao e da consistencia entre eventos recebidos e snapshots reconsultados.

### 3.4.5 Limites e riscos

Os limites principais de Pinot, para este caso, emergem quando a complexidade do painel exige mais do que feed de eventos e resumos rapidos. Workspaces ricos em joins, catalogos e agregados contabeis cumulativos tendem a exigir maior coordenacao entre frontend, API e backend. Portanto, o benchmark deve testar explicitamente estabilidade de `push-first`, divergencia entre detalhamento e agregados e custo de ressincronizacao autoritativa.

### 3.4.6 Bibliografia-base de Pinot

- Documentacao oficial do Apache Pinot.
- Textos tecnicos da comunidade Pinot e de empresas mantenedoras como LinkedIn e StarTree.
- Literatura sobre indexes colunar-invertidos, `Star-Tree` e realtime OLAP em serving distribuido.

## 3.5 Materialize

### 3.5.1 Classe arquitetural

Materialize ocupa uma posicao singular no corpus comparado. Ele nao e, em sentido estrito, apenas um banco analitico colunar para serving quente, nem simplesmente um processador de stream desacoplado de interface SQL. Seu valor arquitetural reside justamente em articular semantica relacional declarativa com manutencao incremental de views sobre fontes streaming. Assim, Materialize se aproxima da categoria `incremental-streaming`, em que a definicao do modelo de leitura participa do proprio mecanismo de convergencia entre stream e estado derivado.

### 3.5.2 Fundamentos internos

O pano de fundo conceitual de Materialize esta profundamente ligado a Timely Dataflow e Differential Dataflow. Em vez de recomputar resultados completos a cada mudanca, o sistema propaga diferencas e frontier progress, permitindo atualizacao incremental de estruturas derivadas. Na pratica, isso significa que `SOURCE`, `VIEW` e `MATERIALIZED VIEW` nao sao apenas objetos de catalogo; eles sao partes de uma topologia incremental com semantica temporal e de progresso.

Essa caracteristica e crucial para o caso deste benchmark. Em dashboards push-oriented, o que se deseja idealmente nao e apenas consultar um estado quente rapidamente, mas aproximar o frontend de uma view derivada que se reconcilia continuamente com o stream canonico. Materialize oferece, ao menos em principio, um encaixe natural para esse problema. Por isso sua trilha no repositorio foi desenhada com bootstrap proprio, API dedicada, health incremental e gateway autoritativo por snapshot incremental.

### 3.5.3 Particularidades semanticas e custos cognitivos

O potencial de Materialize, contudo, nao vem sem contrapartida. Sistemas incrementais impõem restricoes semanticas reais. Funcoes nao deterministicas, limites SQL associados ao modelo incremental, necessidade de atencao a monotonicidade e comportamento sob retracoes nao sao detalhes cosmeticos. Eles afetam diretamente o desenho das views e a traducao de modelos analiticos para o paradigma incremental. Em outras palavras, Materialize pode reduzir a distancia entre stream e snapshot, mas cobra do engenheiro maior disciplina na modelagem relacional incremental.

Isso justifica a inclusao de `cognitive_cost` como metrica comparativa. Enquanto ClickHouse, Druid e Pinot frequentemente concentram a complexidade em serving, segmentacao ou indexacao, Materialize desloca parte do desafio para a expressao correta da topologia incremental. Em ambientes de benchmark serio, esse custo nao deve ser escondido: ele e parte do valor explicativo do paradigma.

### 3.5.4 Materialize no caso de uso do repositorio

No presente projeto, Materialize recebe diretamente `ledger-entries-v1`, bootstrapa conexao Kafka, source, view tipada e materialized views por dominio. A API `api_materialize` consulta essas views incrementais, enquanto o `realtime_gateway` fornece snapshots autoritativos progressivos ao frontend. Isso representa, de fato, uma configuracao mais proxima do ideal conceitual do backend do que trata-lo como mero SQL adapter. Nessa topologia, o frontend deixa de depender exclusivamente de projecao local por evento e passa a se ancorar em um snapshot incremental que vive mais proximo do fluxo.

Tal desenho e relevante para a literatura porque permite comparar, de forma concreta, um paradigma `hot-analytic` com um paradigma `incremental-streaming` sob o mesmo caso de uso funcional. Em vez de perguntar apenas qual banco responde consultas mais rapido, o benchmark pode perguntar qual arquitetura reduz melhor o tempo entre evento canonico e estado derivado utilizavel por uma interface gerencial.

### 3.5.5 Limites e riscos

O principal risco ao avaliar Materialize e superestimar sua vantagem teorica sem medir seus custos reais. Alta cardinalidade, joins incrementais complexos, retracoes e replay podem revelar tensoes importantes entre elegancia conceitual e custo operacional. Da mesma forma, um benchmark injusto pode subestimar a tecnologia se insistir em modela-la com queries e contratos pensados para motores analiticos classicos. A implicacao metodologica e direta: Materialize deve ser avaliado em cenarios desenhados para incremental view maintenance, sem deixar de ser comparado transversalmente em latencia, corretude, recursos e robustez.

### 3.5.6 Bibliografia-base de Materialize

- Murray, D. G. et al. Naiad: A Timely Dataflow System.
- McSherry, F. et al. Differential Dataflow.
- Documentacao oficial do Materialize.
- Publicacoes tecnicas do projeto sobre progress tracking, sources, views materializadas, consistency fronts e streaming SQL.

## 3.6 Sintese comparativa entre categorias

Ao final da analise, as quatro tecnologias distribuem-se em duas familias comparativas principais. ClickHouse, Druid e Pinot sao motores `hot-analytic`, ainda que com internals distintos. Eles tendem a operar melhor quando o read model consultavel ja foi suficientemente construido e quando o desafio dominante e responder bem sobre esse estado materializado. Materialize, por sua vez, aproxima-se de uma familia `incremental-streaming`, na qual o custo e a qualidade da manutencao incremental do read model tornam-se parte integrante do sistema avaliado.

Essa distincao nao implica que uma categoria substitua a outra. Ela implica apenas que o benchmark cientificamente correto deve reconhecer que as tecnologias respondem a perguntas parcialmente diferentes. O valor analitico do trabalho, portanto, esta justamente em mostrar onde esses paradigmas convergem, onde divergem e sob quais metricas um parece mais adequado do que o outro para dashboards gerenciais alimentados por push.

## 3.7 Conclusao do capitulo

O estado da arte tecnologico examinado neste capitulo revela que a comparacao entre ClickHouse, Druid, Pinot e Materialize exige uma leitura em profundidade de internals, topologias operacionais e teorias implicitas de convergencia entre evento e estado consultavel. Cada sistema encarna uma resposta diferente para o problema do serving analitico ou incremental. Por essa razao, o benchmark consolidado neste relatorio nao pode se contentar com uma tabela simples de latencias. Ele precisa medir, com rigor, as propriedades que decorrem das escolhas internas de cada tecnologia: custo de bootstrap, regime de ingestao, comportamento sob filtros e replay, corretude contabil, estabilidade do tempo real e impacto sobre a experiencia visual do frontend.

## Bibliografia-base do Capitulo 3

- Abadi, D. J. et al. Column-stores versus row-stores: how different are they really?
- Chen, Y. et al. literatura tecnica sobre serving distribuido e indexing para Pinot, complementada pela documentacao oficial do projeto.
- ClickHouse, Inc. Documentacao oficial e notas de engenharia sobre MergeTree, projections e materialized views.
- Druid committers and PMC. Documentacao oficial do Apache Druid e material tecnico sobre Kafka indexing service e segment lifecycle.
- Materialize, Inc. Documentacao oficial e textos tecnicos sobre streaming SQL, Timely Dataflow e Differential Dataflow.
- Stonebraker, M. et al. C-Store: A Column-oriented DBMS.
- Yang, F. et al. Druid: A Real-Time Analytical Data Store.