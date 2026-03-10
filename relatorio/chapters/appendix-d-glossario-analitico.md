# Apêndice D - Glossário Analítico de Métricas, Componentes e Paradigmas

## Razão deste glossário expandido

Relatórios longos sobre sistemas orientados a eventos e backends near-real-time tendem a acumular terminologia técnica cuja interpretação varia conforme a tradição de origem. O mesmo termo pode significar coisas diferentes em engenharia de dados, bancos analíticos, sistemas interativos e arquitetura de produto. Este glossário expandido não pretende substituir literatura formal, mas estabilizar o vocabulário efetivamente utilizado neste relatório. Essa estabilização é importante porque o argumento do documento depende fortemente de distinções finas entre conceitos próximos, porém não equivalentes.

## Evento canônico

No contexto deste relatório, evento canônico não é qualquer fato bruto emitido pela aplicação. O termo designa o registro que ocupa o papel de verdade operacional compartilhável dentro do protocolo do benchmark. Mais precisamente, a pesquisa toma como referência o fluxo de entries contábeis normalizadas, e não o evento comercial original ainda heterogêneo. Essa escolha é crítica porque evita que cada backend seja comparado sobre uma interpretação própria do domínio. O evento canônico, portanto, não é apenas um artefato técnico; é a condição de comparabilidade semântica do experimento.

## Ledger

Ledger, no sentido empregado aqui, é a trilha ordenada, auditável e reprocessável de lançamentos contábeis que representa a história financeira relevante do sistema. Sua importância vai além da persistência. O ledger funciona como eixo temporal, jurídico e metodológico do benchmark. Sem ele, não haveria replay confiável, avaliação consistente de corretude nem possibilidade de distinguir ganho de performance de relaxamento semântico indevido.

## Dupla entrada

Dupla entrada é o princípio segundo o qual cada fato econômico relevante precisa ser refletido por lançamentos coerentes de débito e crédito, preservando equilíbrio entre classes patrimoniais e de resultado. No benchmark, esse princípio atua como restrição mínima de validade. Não se trata de detalhe contábil externo ao sistema. Trata-se de condição que delimita o que conta como estado derivado aceitável. Um backend que performasse melhor às custas de quebrar a disciplina de dupla entrada não poderia ser considerado tecnicamente superior dentro do problema definido pelo relatório.

## Read model

Read model designa a representação derivada especificamente moldada para servir consultas, painéis e interfaces. O relatório insiste nesse conceito porque as quatro stacks não operam sobre o mesmo tipo de proximidade entre stream e read model. Em algumas, o estado consultável é servido como camada quente sobre dados já materializados. Em outras, o read model participa de uma topologia incremental mais íntima do fluxo de eventos. A distinção importa porque altera o custo de atualização, de replay, de filtragem e de reconciliação visual.

## Hot-analytic

O termo hot-analytic é usado para designar motores cujo ponto forte é servir com baixa latência um estado analítico já disponível e suficientemente quente. A ênfase está menos na manutenção incremental fina do próprio modelo derivado e mais na excelência de consulta sobre tabelas, segmentos ou índices já prontos para serving. ClickHouse, Druid e Pinot pertencem a essa família, ainda que com internals muito diferentes. A utilidade do termo está em separar essa classe de sistemas de arquiteturas incremental-streaming mais profundas.

## Incremental-streaming

Incremental-streaming designa, neste relatório, arquiteturas em que o processo de manter o estado derivado próximo ao stream é parte central do próprio backend, e não apenas tarefa distribuída entre aplicação, gateway e cache. O caso emblemático do corpus é Materialize. O valor do termo está em indicar uma diferença ontológica no tipo de promessa arquitetural: não se trata apenas de responder rápido sobre um estado pronto, mas de reduzir estruturalmente o custo de manter esse estado em convergência contínua com o fluxo.

## Incremental view maintenance

Incremental view maintenance é o campo que estuda como atualizar visões derivadas sem recomputá-las integralmente após cada mudança na base de fatos. No contexto do relatório, o conceito serve para qualificar uma ambição técnica: aproximar o estado consultável de um regime em que diferenças, e não recomputações totais, sejam o principal mecanismo de atualização. A relevância para dashboards near-real-time é direta: quanto mais cara for a recomputação total, maior o interesse por manutenção incremental coerente.

## Retratação

Retratação é a remoção, invalidação ou compensação de contribuição anterior no estado derivado. Em sistemas financeiros, devoluções, cancelamentos, estornos e correções tardias frequentemente assumem essa forma lógica. O conceito é importante porque separa workloads monotônicos de workloads que exigem tratamento explícito de diferença negativa. Boa parte da sofisticação atribuída a sistemas incrementais só se justifica plenamente quando retratações entram no cenário experimental.

## Snapshot autoritativo

Snapshot autoritativo é a representação do estado que o sistema assume como referência final confiável para exibição, reconciliação e decisão. Ele se opõe a atualizações locais provisórias, projeções parciais ou sinais de progresso ainda não plenamente reconciliados. Em dashboards operacionais, a noção de autoridade é crucial. Um sistema pode ser rápido em mostrar algo; a pergunta decisiva é quando esse algo pode ser tratado como suficiente para orientar ação real.

## Continuidade visual

Continuidade visual é a propriedade pela qual o frontend evita descontinuidades bruscas, listas vazias espúrias, oscilações severas de agregados ou alternância frequente entre estados semânticos incompatíveis durante a convergência. O termo é usado para lembrar que experiência percebida não depende apenas de velocidade, mas de estabilidade do caminho entre evento e interface. Um painel tecnicamente eventual, porém visualmente errático, pode ser menos útil do que um painel um pouco mais lento, porém semanticamente estável.

## `frontend_time_to_first_meaningful_state_ms`

Essa métrica representa o intervalo até que o frontend alcance um estado considerado minimamente informativo e operacionalmente útil. Ela não se confunde com o primeiro pacote websocket nem com a primeira resposta HTTP. Seu valor teórico está em medir um limiar semântico de utilidade, não apenas um marco infraestrutural de atividade. Por isso ela é uma das métricas centrais do relatório.

## `snapshot_rate_per_second`

Essa métrica mede a cadência com que snapshots autoritativos são percebidos na interface ou no gateway, conforme o pipeline de coleta. Sua importância reside em capturar a frequência da reancoragem do painel em um estado efetivamente consolidado. Dois sistemas podem ter tempos iniciais parecidos e, ainda assim, divergir fortemente na taxa com que atualizam o estado autoritativo depois desse primeiro instante.

## `entry_rate_per_second`

A métrica expressa a taxa percebida de propagação de eventos do tipo `entry.created` na trilha de observação usada pelo benchmark. Ela ajuda a distinguir casos em que o sistema é bom em refletir o fluxo elementar de eventos daqueles em que a materialização autoritativa do painel continua lenta. Em conjunto com `snapshot_rate_per_second`, permite separar vivacidade do feed e autoridade do estado derivado.

## Health timeline

Health timeline designa a série temporal de observações de saúde dos componentes monitorados. No relatório, essa trilha é importante porque registra aquecimento, transições de estado e episódios de indisponibilidade parcial. Sua presença impede que a discussão trate readiness como abstração implícita. Em vez disso, readiness entra no corpus como dado observável, comparável e interpretável.

## Round canônica

Rodada canônica é a execução escolhida como representante principal de cada backend no cenário `report-conclusion`. Nesta versão do relatório, a canonicidade não significa perfeição absoluta; significa a execução final mais adequada para a comparação principal, preservando ao mesmo tempo as rodadas auxiliares e substituídas como evidência diagnóstica. O conceito é importante porque explicita o critério de seleção em vez de ocultá-lo.

## Rodada substituída

Rodada substituída é a execução preservada no corpus, mas não usada como representante principal de um backend por ter sido superada por execução posterior mais estável ou mais completa. O caso mais expressivo no corpus é a tentativa anterior de ClickHouse com falhas massivas na superfície SQL. Manter a rodada substituída no artigo é metodologicamente valioso porque torna visível o processo de estabilização do experimento.

## Rodada de validação

Rodadas de validação são execuções auxiliares destinadas a verificar readiness, SQL ou viabilidade de trilhas específicas antes da bateria conclusiva. Elas não possuem o mesmo peso comparativo das rodadas canônicas, mas preservam conhecimento crítico sobre o amadurecimento do protocolo. Em um artigo aprofundado, essas rodadas ajudam a explicar por que certos resultados finais foram possíveis e quais problemas precisaram ser superados para alcançá-los.

## Custo operacional

Custo operacional é o conjunto de fricções relacionadas a bootstrap, readiness, coordenação de serviços, observabilidade, repetibilidade, diagnóstico e consumo de infraestrutura. O relatório insiste nesse conceito porque muito do que diferencia as stacks não aparece apenas no tempo de query, mas no esforço necessário para fazer a trilha inteira entrar em regime reproduzível. Tratar esse custo como ruído seria empobrecer a comparação.

## Custo cognitivo

Custo cognitivo designa a complexidade intelectual e de modelagem exigida da equipe para usar um backend de forma correta e sustentável. No corpus, ele aparece de formas diferentes: modelagem incremental e restrições semânticas mais exigentes em Materialize; coordenação entre projeção local e estado autoritativo em Pinot; disciplina de topologia e readiness em Druid; desenho de read model e integração periférica em ClickHouse. Embora não seja reduzido a um único número, é uma variável real de arquitetura.

## Sistema completo

Ao falar em sistema completo, o relatório recusa a ideia de que o backend seja unidade isolada suficiente de análise. Sistema completo é o arranjo que liga produtor, stream, writer canônico, backend, API, gateway e frontend. O termo é central porque resume a principal contribuição metodológica do trabalho: a unidade de benchmark não é apenas o banco, mas a cadeia que transforma evento em estado utilizável por decisão gerencial.

## Encerramento do glossário

Este glossário expandido existe para que a leitura do relatório não dependa de suposições tácitas sobre termos fundamentais. Ao estabilizar o vocabulário, ele também reforça a ideia central do trabalho: comparar backends para dashboards near-real-time exige mais do que medir consultas; exige definir com precisão que tipo de verdade operacional, que tipo de autoridade visual, que tipo de custo e que tipo de sistema estão efetivamente em jogo.