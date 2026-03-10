# Discussão Comparativa Ampliada

## Por que a tabela-resumo não basta

Em benchmark de banco de dados, é comum que a discussão final se resuma a uma tabela curta de tempos e a uma conclusão do tipo “o sistema X foi mais rápido”. Esse formato pode ser útil para workloads homogêneos, com uma única superfície de consulta e poucas exigências semânticas. Não é o caso deste relatório. O objeto de análise não é um conjunto de queries artificialmente isoladas; é a cadeia que conecta evento de negócio, ledger, backend, API, gateway realtime e frontend gerencial. Quando o objeto é uma cadeia e não uma única função, o sentido de “melhor” muda radicalmente.

O corpus final deixa isso evidente. Se a análise se limitasse ao SQL, Pinot seria o vencedor claro. Se a leitura se limitasse ao endpoint `summary`, ClickHouse teria vantagem mais forte. Se o foco recaisse sobre o tempo até o primeiro estado útil do frontend, Druid e Pinot pareceriam os mais atraentes. Se a ênfase estivesse na proximidade entre ideal incremental e modelo conceitual do problema, Materialize ganharia centralidade analítica. Cada recorte produz uma resposta distinta. O papel deste capítulo é organizar esses recortes em uma discussão coerente, em vez de escolher arbitrariamente apenas um deles.

## Dimensão 1: latência de consulta não é latência de sistema

A primeira tese da discussão ampliada é que latência de consulta e latência de sistema não são equivalentes. A literatura de bancos frequentemente privilegia métricas ligadas ao tempo de execução de query, throughput e escalabilidade. Tais medidas continuam importantes aqui, mas o corpus mostra que elas não esgotam o problema prático dos dashboards gerenciais. Em um painel orientado a eventos, o usuário não interage com um benchmark SQL; ele interage com um estado visual em processo de convergência.

Isso explica por que Druid pode parecer relativamente caro em `workspace` e ainda assim entregar prontidão visual muito competitiva. Explica também por que Materialize, mesmo perdendo em várias consultas, continua relevante quando o problema é encurtar a distância entre mudança no stream e utilidade operacional do snapshot. A lição não é que consulta deixou de importar. A lição é que consulta importa como parte de um sistema maior, não como soberana absoluta da decisão arquitetural.

## Dimensão 2: estado quente versus estado incremental

A segunda tese diz respeito à diferença entre servir um estado já quente e manter incrementalmente um estado derivado. Os resultados deste relatório sugerem que servir estado quente continua sendo uma estratégia extremamente poderosa. ClickHouse e Pinot mostram isso com clareza. Quando o modelo de leitura está materializado e a API sabe explorá-lo bem, a velocidade consultiva pode ser excepcional.

Entretanto, o corpus também sugere que essa vantagem não encerra a discussão. O que o paradigma hot-analytic ganha em consulta ele pode perder em distância conceitual para o problema do dashboard autoritativo. Nesses sistemas, parte do trabalho de manter coerência entre fluxo, snapshot e frontend desloca-se para a borda da aplicação. O que Materialize torna visível é exatamente o outro lado do espelho: internalizar mais da lógica incremental pode aproximar o backend do problema semântico, ainda que isso venha acompanhado de custos operacionais e de consulta que, no estado atual da trilha, permanecem elevados.

Em outras palavras, o benchmark mostra uma tensão estrutural entre duas ambições. A primeira é responder rapidamente sobre um estado quente. A segunda é reduzir ao máximo o custo cognitivo e temporal entre o stream e o estado autoritativo. Nem o corpus nem a teoria autorizam reduzir uma ambição à outra.

## Dimensão 3: prontidão percebida, autoridade e confiança visual

A terceira tese refere-se ao conceito de autoridade do painel. Nem toda atualização rápida produz confiança operacional. Um frontend pode se mover rapidamente e ainda assim permanecer dependente de projeções locais, sincronizações incompletas ou snapshots esparsos. É por isso que o relatório insiste em observar `snapshot_rate_per_second`, tempos de primeiro snapshot, tempos de estado significativo e métricas relacionadas ao fluxo de eventos visíveis.

Sob essa ótica, Pinot oferece um caso paradigmático. Sua superfície consultiva é excelente, mas a taxa autoritativa de snapshots observada no corpus é muito inferior à das demais stacks. Isso não elimina seu valor. Apenas impede que a velocidade de leitura seja interpretada como sinônimo de atualização autoritativa do painel. Druid, por contraste, mostra que um backend não precisa liderar todas as consultas para ainda assim sustentar um regime de visualização muito convincente quando a questão central é a retomada rápida do estado útil.

Essa distinção tem peso especial em ambientes contábeis e financeiros. O custo de exibir rapidamente um estado não autoritativo pode ser maior do que a vantagem de exibi-lo cedo. A relevância do benchmark está justamente em não esconder essa ambiguidade.

## Dimensão 4: custo operacional e custo cognitivo são métricas reais

Uma contribuição importante deste corpus é tratar custo operacional e custo cognitivo como parte do comportamento do backend, e não como ruído extra-experimental. Druid demanda disciplina de readiness, ingestão e coordenação de serviços. Pinot demanda maior governança da fronteira entre projeção local e reancoragem autoritativa. ClickHouse depende de uma boa separação entre derivação canônica e serving quente, além de desenho apropriado do read model. Materialize, por sua vez, cobra mais atenção à modelagem incremental, ao ciclo de bootstrap e à estabilidade da trilha inteira.

Esses custos não aparecem numa única consulta, mas aparecem no projeto real. Para uma equipe de engenharia, eles se traduzem em tempo de implementação, dificuldade de diagnóstico, sensibilidade a replays, qualidade de observabilidade e risco de regressão ao ajustar o workload. Logo, o artigo não deve tratar esses aspectos como notas de rodapé. Eles são parte da substância da comparação.

## Dimensão 5: corretude contábil como fronteira mínima, não como diferencial suficiente

O fato de todas as stacks canônicas terem mantido `balance_sheet_difference` igual a zero é excelente para a qualidade epistemológica do relatório. Isso garante que a comparação principal não foi contaminada por uma solução que simplesmente “ganhou” por ter relaxado integridade semântica. Mas há um detalhe importante: corretude mínima não encerra o problema contábil. Preservar equilíbrio patrimonial é condição necessária; não é, por si só, prova suficiente de que a trilha completa de reconciliação, filtragem, atualização incremental e exibição final seja igualmente robusta em todas as dimensões.

Em outras palavras, a corretude observada delimita o campo do debate, mas não o resolve. Ela autoriza que se compare latência, convergência e operação sem suspeita imediata de fraude semântica. Ao mesmo tempo, impõe que a pesquisa futura continue observando outras formas de coerência: idempotência, comportamento sob correção tardia, consistência entre detalhamento e agregados, custo de replay e estabilidade sob filtros compostos mais agressivos.

## Dimensão 6: o peso do corpus auxiliar e das tentativas substituídas

Uma escolha importante desta versão ampliada é não reduzir o artigo apenas às rodadas finais canônicas. As tentativas substituídas e as rodadas auxiliares existem por uma razão: elas revelam fragilidades de preparação, aquecimento e maturação do experimento. A tentativa anterior de ClickHouse, com enorme concentração de falhas SQL, e as rodadas de validação de Materialize, com insucessos iniciais em consultas nativas, mostram que a comparação entre paradigmas não ocorre num vácuo. Ela depende de estabilização progressiva das trilhas e de eliminação incremental de erros de integração.

Esse dado tem duas implicações. A primeira é epistemológica: o artigo fica mais honesto quando registra a trilha de amadurecimento do corpus em vez de fingir que só existiram as quatro melhores rodadas. A segunda é prática: essas rodadas auxiliares são um mapa de onde vale a pena concentrar reruns de dupla conformação. O trabalho futuro não precisa repetir tudo cegamente; ele pode priorizar precisamente os pontos em que o corpus já mostrou fragilidade.

## Dimensão 7: relação entre recursos e desempenho

A leitura de recursos computacionais também relativiza conclusões rápidas. Druid e Pinot aparecem com consumo agregado de memória pico substancialmente superior ao de ClickHouse e Materialize, ao passo que ClickHouse lidera em CPU média agregada no corpus final. Isso impede leituras simplificadas do tipo “o melhor foi também o mais barato”. A relação entre recursos e benefício depende do que se deseja otimizar. Se o objetivo for minimizar custo de memória local, certas stacks tornam-se menos atraentes. Se o objetivo for maximizar velocidade consultiva absoluta, um gasto maior de CPU pode ser perfeitamente aceitável.

O ponto principal é que o artigo deve explicitar a multidimensionalidade da escolha. Em projetos reais, não existe uma função objetivo única. Existem restrições orçamentárias, limites de infraestrutura, exigências de auditabilidade, tolerância a complexidade operacional e expectativas muito diferentes sobre o papel do frontend. É justamente por isso que um benchmark amplo como este precisa fornecer mais de uma forma de leitura.

## Uma matriz interpretativa para decisão arquitetural

À luz do corpus, é possível propor uma matriz interpretativa qualitativa. Para casos em que a prioridade máxima seja leitura direta rápida sobre estado quente com bom equilíbrio geral de integração, ClickHouse aparece como a escolha mais consistente do corpus final estabilizado. Para casos em que a camada consultiva pura, especialmente SQL, seja dominante e a equipe aceite maior protagonismo do frontend na continuidade visual, Pinot surge como candidato forte. Para contextos em que a organização aceite topologia multi-serviço mais exigente em troca de excelente prontidão percebida e boa cadência autoritativa, Druid se torna tecnicamente defensável. Para contextos em que o objetivo principal seja explorar proximidade semântica com incremental view maintenance e evoluir um caminho mais rigoroso entre stream e snapshot autoritativo, Materialize permanece como a linha de investigação mais fecunda, embora ainda não a mais madura no corpus final.

Essa matriz não substitui o benchmark; ela é o produto interpretativo do benchmark. Seu valor está em impedir decisões dogmáticas. Em vez de proclamar uma resposta universal, ela força a equipe a escolher explicitamente qual problema deseja resolver primeiro.

## Encerramento da discussão comparativa

O ganho principal desta discussão ampliada é tornar claro que o relatório não está comparando apenas produtos, mas formas de organizar a distância entre evento e interface. Cada backend representa uma solução diferente para essa distância. Alguns a encurtam por velocidade de serving, outros por organização incremental do estado, outros por composição entre backend e frontend, outros por compromisso entre aquecimento, consulta e cadência autoritativa. Esse é o sentido mais forte da contribuição analítica do trabalho.

Quando o problema é formulado dessa forma, a diminuição do relatório seria um empobrecimento real: ela apagaria precisamente as nuances que tornam o benchmark útil. A versão ampliada precisa, portanto, preservar tabelas, preservar narrativa e acrescentar discussão. Esse é o princípio que orienta os capítulos finais e os apêndices técnicos que seguem.