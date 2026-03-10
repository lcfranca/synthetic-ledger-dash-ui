# Estado da Arte Tecnológico

## Introdução

O estado da arte relevante para esta pesquisa não pode ser organizado apenas por ordem cronológica de lançamento de produtos ou por comparações superficiais de benchmark industrial. A questão central é identificar como diferentes famílias de sistemas materializam, em sua arquitetura interna, distintas respostas para o mesmo problema: transformar fluxos de eventos em estado derivado consultável com baixa latência, alta confiabilidade e custo operacional aceitável. Nesse sentido, ClickHouse, Druid, Pinot e Materialize não devem ser lidos como variações marginais de uma mesma classe, mas como respostas arquiteturais distintas a tensões entre ingestão, armazenamento, indexação, agregação, invalidação e serving.

Este capítulo apresenta cada backend em profundidade suficiente para sustentar uma comparação científica. O critério de análise não será marketing de produto, mas: arquitetura interna, modelo de armazenamento, caminho de ingestão, estratégia de indexação, semântica de atualização, implicações para dashboards push-oriented, pontos fortes, fragilidades e adequação ao problema do repositório.

## ClickHouse

### Classe arquitetural

ClickHouse é um sistema de armazenamento colunar orientado à análise de baixa latência em larga escala. Sua força decorre da combinação entre armazenamento em colunas, compressão agressiva, particionamento por partes, leitura vetorizada e uma família de motores `MergeTree` desenhados para otimizar scans seletivos, filtros e agregações. Em termos de paradigma, ClickHouse opera como um motor `hot-analytic`: ele se torna especialmente eficaz quando o read model relevante já se encontra materializado em tabelas adequadas e quando a consulta pode explorar a localidade estatística e os mecanismos de pruning do armazenamento colunar.

### Internals relevantes

No cerne do ClickHouse estão as `parts`, unidades físicas de armazenamento criadas por inserções e posteriormente consolidadas por merges assíncronos. Esse desenho oferece uma relação favorável entre throughput de ingestão e custo de leitura, mas também implica um comportamento temporal específico: o estado consultável pode depender do ciclo de merges, da materialização de visões auxiliares e da organização da ordenação primária. A indexação é deliberadamente esparsa. Em vez de um B-tree tradicional por linha, ClickHouse aposta em marcas, grânulos e ordenação por chave primária para eliminar grandes faixas de dados com custo baixo.

Essa estrutura é extremamente eficiente para workloads em que filtros e agregações podem ser mapeados sobre colunas bem compressíveis e chaves de ordenação adequadas. No contexto de dashboards gerenciais, isso favorece queries de resumo, slicing por dimensão e leitura de subconjuntos recentes, especialmente quando o fan-out para o ClickHouse já produziu um read model adequado. Em contrapartida, ClickHouse não é, por natureza, um mecanismo de manutenção incremental de views arbitrárias acoplado ao stream em tempo contínuo. Sua força reside mais no serving analítico de um estado quente do que na propagação incremental fina entre evento e view complexa.

### Ingestão e serving no caso de uso

No repositório, ClickHouse recebe o fluxo canônico a partir do `storage_writer`, que executa fan-out do ledger contábil para o backend. Isso preserva uma separação clara entre derivação contábil e serving analítico. A vantagem é metodológica e operacional: a lógica financeira central permanece no writer, enquanto ClickHouse se concentra em responder bem sobre uma tabela consultável. Para um benchmark honesto, isso é importante, porque evita atribuir ao banco responsabilidades de semântica de domínio que pertencem ao pipeline canônico.

Em dashboards push-oriented, ClickHouse tende a funcionar melhor com estratégia híbrida: eventos podem sustentar continuidade visual imediata, mas snapshots autoritativos periódicos do gateway oferecem a ancoragem necessária para filtros, agregados e reconciliação. Isso o coloca numa posição forte para consultas de baixa latência, mas menos naturalmente alinhada a snapshots incrementais autoritativos de alta frequência sob filtros compostos altamente dinâmicos.

### Limites e riscos

Os limites de ClickHouse, para este caso específico, decorrem menos de desempenho bruto e mais de semântica operacional. O sistema pode responder rapidamente a queries bem ajustadas, mas não internaliza, por si só, uma teoria de retrações e de manutenção incremental de read models comparável à de sistemas como Materialize. Em workloads com alta taxa de correções, replay frequente ou necessidade de snapshots incrementais filtrados muito próximos do stream, a solução tende a exigir mais coordenação na API e no gateway.

### Bibliografia-base de ClickHouse

- Stonebraker, M. et al. C-Store: A Column-oriented DBMS.
- Abadi, D. J.; Madden, S.; Ferreira, M. C. Integrating compression and execution in column-oriented database systems.
- ClickHouse, Inc. Documentação técnica oficial do ClickHouse.
- Publicações técnicas e blogs de engenharia do projeto ClickHouse sobre MergeTree, skipping indexes, projections e materialized views.

## Apache Druid

### Classe arquitetural

Apache Druid é um sistema analítico distribuído fortemente orientado à ingestão de eventos e serving OLAP de baixa latência, especialmente em cenários de séries temporais, exploração interativa e agregações multidimensionais. Diferentemente de um banco monolítico, sua arquitetura explicita uma topologia de serviços com papéis distintos: `Overlord` para coordenação de tarefas de ingestão, `Coordinator` para gestão de segmentos, `Broker` para planejamento e fan-out de consultas, `Router` para front-door HTTP e `Historicals` ou `MiddleManagers` para armazenamento e processamento de dados.

### Internals relevantes

Druid organiza dados em segmentos imutáveis, particionados temporalmente e distribuíveis entre nós. A ingestão streaming via Kafka supervisor alimenta tarefas que consomem o stream, constroem segmentos e os publicam para serving. Esse desenho tem vantagens claras: baixa latência para agregações sobre dados temporalmente organizados, boa escalabilidade horizontal e forte adequação a cenários exploratórios com filtros e group-bys. No entanto, ele introduz uma complexidade operacional significativa. O desempenho percebido não depende apenas do motor de consulta, mas da coordenação entre serviços, do estado do supervisor, da saúde do metadata store e da disponibilidade de brokers.

Em outras palavras, Druid oferece um estado da arte importante para workloads analíticos de eventos, mas o custo de atingir esse estado da arte não é trivial. Isso precisa aparecer no benchmark como métrica de custo operacional, cold start, transições de health e estabilidade do pipeline de ingestão. Um benchmark que medisse apenas latência de consulta e ignorasse a topologia multi-serviço de Druid estaria subestimando um aspecto central da tecnologia.

### Druid no contexto de dashboards push-oriented

Para o caso deste projeto, Druid ocupa uma posição interessante. Ele consome o stream canônico do ledger via supervisor Kafka e serve o painel por meio de uma API dedicada. Em termos de convergência visual, o sistema se beneficia de snapshots autoritativos filtrados e de telemetria de pipeline, mas não opera como um mecanismo de incremental view maintenance fino. O gateway precisa coordenar o fluxo de eventos e os snapshots do backend para preservar coerência perceptual, especialmente quando filtros complexos entram em cena.

Isso significa que Druid é particularmente forte como backend de leitura analítica quente, mas menos natural como âncora incremental direta entre stream e frontend. Em cenários de alta cardinalidade ou de grande volume temporal, seu modelo de segmentos e planning pode continuar competitivo; em cenários de replay, bootstrap local e operação com recursos restritos, a topologia multi-serviço pode impor custos maiores que os observados em outras stacks.

### Limites e riscos

Os principais riscos de Druid, para o caso estudado, residem na sensibilidade operacional do pipeline: supervisores em retry, dependências entre broker e router, estado do metadata store e custo de aquecimento da stack. Em uma publicação científica honesta, esses fatores não devem ser tratados como ruído contingente. Eles são parte do comportamento real da tecnologia em ambientes de engenharia. Assim, custo cognitivo e custo operacional local devem figurar como variáveis comparativas explícitas.

### Bibliografia-base de Druid

- Yang, F. et al. Druid: A Real-Time Analytical Data Store.
- Documentação oficial do Apache Druid.
- Publicações técnicas do projeto sobre segment lifecycle, ingestion specs, roll-up, compaction e Kafka indexing service.

## Apache Pinot

### Classe arquitetural

Apache Pinot foi concebido para serving OLAP de baixa latência em cenários com alto volume de consultas interativas, forte exigência de recorte dimensional e consumo contínuo de streams. Sua arquitetura distribui responsabilidades entre `Controller`, `Broker` e `Server`, combinando ingestão realtime com estratégias de indexação voltadas a consultas de baixa latência. No ecossistema industrial, Pinot se destacou sobretudo em casos de analytics operacionais com alta taxa de leitura, grande fan-out de queries e necessidade de respostas quase imediatas para exploração por produto.

### Internals relevantes

O desenho interno de Pinot combina armazenamento colunar, dicionários, indexes invertidos e, em alguns cenários, estruturas como `Star-Tree` para acelerar agregações recorrentes. Sua proposta não é apenas armazenar colunas, mas organizar o caminho entre consulta e dado por meio de estruturas que reduzam scanning desnecessário para workloads interativos. A ingestão realtime, baseada em consumo de streams como Kafka, torna Pinot particularmente atraente para modelos de leitura com atualização contínua.

No entanto, o que torna Pinot tecnicamente relevante para este benchmark é sua afinidade com modos `push-first`. Quando combinado a um frontend capaz de projetar localmente parte dos eventos `entry.created`, Pinot pode servir como backend de baixa latência para reancoragem periódica, enquanto a continuidade perceptual imediata é mantida no cliente. Trata-se de uma escolha arquitetural distinta da de Druid e da de Materialize: Pinot não internaliza a manutenção incremental completa do estado derivado, mas tampouco depende apenas de snapshots pesados para responder com rapidez.

### Estado da literatura e fontes técnicas

Em comparação com Druid e ClickHouse, a literatura revisada por pares explicitamente centrada em Pinot é menos consolidada como corpus acadêmico canônico. Isso não invalida a tecnologia; apenas exige mais cuidado bibliográfico. Para uma escrita científica rigorosa, a base de Pinot deve combinar documentação oficial, textos de engenharia de produtores da tecnologia e, onde disponível, artigos técnicos sobre realtime OLAP, indexes e serving distribuído. Em termos epistêmicos, trata-se de uma área em que a literatura industrial de alta qualidade ainda ocupa parte do espaço que, em outros sistemas, foi mais formalizado por artigos clássicos.

### Pinot no contexto do benchmark

No repositório, Pinot assume o papel de backend desacoplado com frontend especializado. Essa decisão é instrutiva: ela permite observar uma estratégia de convergência visual em que o cliente participa mais ativamente do processo, enquanto o backend fornece a âncora quente para consultas autoritativas. Em cenários de fila operacional, essa composição pode gerar excelente latência percebida. Em contrapartida, sua robustez depende da qualidade da projeção local, da disciplina de reconciliação e da consistência entre eventos recebidos e snapshots reconsultados.

### Limites e riscos

Os limites principais de Pinot, para este caso, emergem quando a complexidade do painel exige mais do que feed de eventos e resumos rápidos. Workspaces ricos em joins, catálogos e agregados contábeis cumulativos tendem a exigir maior coordenação entre frontend, API e backend. Portanto, o benchmark deve testar explicitamente estabilidade de `push-first`, divergência entre detalhamento e agregados e custo de ressincronização autoritativa.

### Bibliografia-base de Pinot

- Documentação oficial do Apache Pinot.
- Textos técnicos da comunidade Pinot e de empresas mantenedoras como LinkedIn e StarTree.
- Literatura sobre indexes colunar-invertidos, `Star-Tree` e realtime OLAP em serving distribuído.

## Materialize

### Classe arquitetural

Materialize ocupa uma posição singular no corpus comparado. Ele não é, em sentido estrito, apenas um banco analítico colunar para serving quente, nem simplesmente um processador de stream desacoplado de interface SQL. Seu valor arquitetural reside justamente em articular semântica relacional declarativa com manutenção incremental de views sobre fontes streaming. Assim, Materialize se aproxima da categoria `incremental-streaming`, em que a definição do modelo de leitura participa do próprio mecanismo de convergência entre stream e estado derivado.

### Fundamentos internos

O pano de fundo conceitual de Materialize está profundamente ligado a Timely Dataflow e Differential Dataflow. Em vez de recomputar resultados completos a cada mudança, o sistema propaga diferenças e frontier progress, permitindo atualização incremental de estruturas derivadas. Na prática, isso significa que `SOURCE`, `VIEW` e `MATERIALIZED VIEW` não são apenas objetos de catálogo; eles são partes de uma topologia incremental com semântica temporal e de progresso.

Essa característica é crucial para o caso deste benchmark. Em dashboards push-oriented, o que se deseja idealmente não é apenas consultar um estado quente rapidamente, mas aproximar o frontend de uma view derivada que se reconcilia continuamente com o stream canônico. Materialize oferece, ao menos em princípio, um encaixe natural para esse problema. Por isso sua trilha no repositório foi desenhada com bootstrap próprio, API dedicada, health incremental e gateway autoritativo por snapshot incremental.

### Particularidades semânticas e custos cognitivos

O potencial de Materialize, contudo, não vem sem contrapartida. Sistemas incrementais impõem restrições semânticas reais. Funções não determinísticas, limites SQL associados ao modelo incremental, necessidade de atenção à monotonicidade e comportamento sob retrações não são detalhes cosméticos. Eles afetam diretamente o desenho das views e a tradução de modelos analíticos para o paradigma incremental. Em outras palavras, Materialize pode reduzir a distância entre stream e snapshot, mas cobra do engenheiro maior disciplina na modelagem relacional incremental.

Isso justifica a inclusão de `cognitive_cost` como métrica comparativa. Enquanto ClickHouse, Druid e Pinot frequentemente concentram a complexidade em serving, segmentação ou indexação, Materialize desloca parte do desafio para a expressão correta da topologia incremental. Em ambientes de benchmark sério, esse custo não deve ser escondido: ele é parte do valor explicativo do paradigma.

### Materialize no caso de uso do repositório

No presente projeto, Materialize recebe diretamente `ledger-entries-v1`, bootstrapa conexão Kafka, source, view tipada e materialized views por domínio. A API `api_materialize` consulta essas views incrementais, enquanto o `realtime_gateway` fornece snapshots autoritativos progressivos ao frontend. Isso representa, de fato, uma configuração mais próxima do ideal conceitual do backend do que tratá-lo como mero SQL adapter. Nessa topologia, o frontend deixa de depender exclusivamente de projeção local por evento e passa a se ancorar em um snapshot incremental que vive mais próximo do fluxo.

Tal desenho é relevante para a literatura porque permite comparar, de forma concreta, um paradigma `hot-analytic` com um paradigma `incremental-streaming` sob o mesmo caso de uso funcional. Em vez de perguntar apenas qual banco responde consultas mais rápido, o benchmark pode perguntar qual arquitetura reduz melhor o tempo entre evento canônico e estado derivado utilizável por uma interface gerencial.

### Limites e riscos

O principal risco ao avaliar Materialize é superestimar sua vantagem teórica sem medir seus custos reais. Alta cardinalidade, joins incrementais complexos, retrações e replay podem revelar tensões importantes entre elegância conceitual e custo operacional. Da mesma forma, um benchmark injusto pode subestimar a tecnologia se insistir em modelá-la com queries e contratos pensados para motores analíticos clássicos. A implicação metodológica é direta: Materialize deve ser avaliado em cenários desenhados para incremental view maintenance, sem deixar de ser comparado transversalmente em latência, corretude, recursos e robustez.

### Bibliografia-base de Materialize

- Murray, D. G. et al. Naiad: A Timely Dataflow System.
- McSherry, F. et al. Differential Dataflow.
- Documentação oficial do Materialize.
- Publicações técnicas do projeto sobre progress tracking, sources, views materializadas, consistency fronts e streaming SQL.

## Síntese comparativa entre categorias

Ao final da análise, as quatro tecnologias distribuem-se em duas famílias comparativas principais. ClickHouse, Druid e Pinot são motores `hot-analytic`, ainda que com internals distintos. Eles tendem a operar melhor quando o read model consultável já foi suficientemente construído e quando o desafio dominante é responder bem sobre esse estado materializado. Materialize, por sua vez, aproxima-se de uma família `incremental-streaming`, na qual o custo e a qualidade da manutenção incremental do read model tornam-se parte integrante do sistema avaliado.

Essa distinção não implica que uma categoria substitua a outra. Ela implica apenas que o benchmark cientificamente correto deve reconhecer que as tecnologias respondem a perguntas parcialmente diferentes. O valor analítico do trabalho, portanto, está justamente em mostrar onde esses paradigmas convergem, onde divergem e sob quais métricas um parece mais adequado do que o outro para dashboards gerenciais alimentados por push.

## Conclusão do capítulo

O estado da arte tecnológico examinado neste capítulo revela que a comparação entre ClickHouse, Druid, Pinot e Materialize exige uma leitura em profundidade de internals, topologias operacionais e teorias implícitas de convergência entre evento e estado consultável. Cada sistema encarna uma resposta diferente para o problema do serving analítico ou incremental. Por essa razão, o benchmark consolidado neste relatório não pode se contentar com uma tabela simples de latências. Ele precisa medir, com rigor, as propriedades que decorrem das escolhas internas de cada tecnologia: custo de bootstrap, regime de ingestão, comportamento sob filtros e replay, corretude contábil, estabilidade do tempo real e impacto sobre a experiência visual do frontend.

## Bibliografia-base do Capítulo 3

- Abadi, D. J. et al. Column-stores versus row-stores: how different are they really?
- Chen, Y. et al. literatura técnica sobre serving distribuído e indexing para Pinot, complementada pela documentação oficial do projeto.
- ClickHouse, Inc. Documentação oficial e notas de engenharia sobre MergeTree, projections e materialized views.
- Druid committers and PMC. Documentação oficial do Apache Druid e material técnico sobre Kafka indexing service e segment lifecycle.
- Materialize, Inc. Documentação oficial e textos técnicos sobre streaming SQL, Timely Dataflow e Differential Dataflow.
- Stonebraker, M. et al. C-Store: A Column-oriented DBMS.
- Yang, F. et al. Druid: A Real-Time Analytical Data Store.