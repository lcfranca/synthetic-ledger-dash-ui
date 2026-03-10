# Análise Técnica por Backend

## Propósito deste capítulo

O capítulo anterior consolidou a leitura comparativa direta das métricas mais visíveis do corpus. Essa visão é necessária, mas ainda insuficiente para explicar por que cada stack se comportou como se comportou. Um benchmark de sistema completo não produz apenas uma ordenação de vencedores e perdedores; ele produz também um mapa causal provisório entre arquitetura interna, topologia operacional, superfície de consulta, mecanismo de convergência visual e custo de sustentação. É precisamente esse mapa que este capítulo procura construir.

Em vez de tratar ClickHouse, Druid, Pinot e Materialize como caixas pretas que recebem eventos e devolvem tempos de resposta, a análise a seguir reconstrói, backend a backend, quais propriedades técnicas parecem ter moldado o comportamento observado. A pergunta orientadora deixa de ser “quem foi mais rápido?” e passa a ser “qual combinação entre internals, integração no repositório e regime do experimento explica os resultados medidos?”. Essa mudança é essencial para evitar conclusões superficiais. Um backend pode ser rápido porque opera sobre um estado já bem aquecido; outro pode parecer mais lento porque absorve internamente responsabilidades que, noutra stack, foram deslocadas para a aplicação, para o gateway ou para o frontend.

Há ainda uma segunda razão para esta leitura aprofundada. O corpus deste relatório não registra apenas quatro rodadas finais. Ele preserva também tentativas substituídas, rodadas de validação e evidências diagnósticas que mostram warm-up irregular, falhas transitórias, indisponibilidade parcial de endpoints de debug e assimetrias de custo operacional. Essas trilhas não devem ser tratadas como resíduos descartáveis. Elas são parte da realidade do sistema e ajudam a interpretar por que certos resultados finais são mais estáveis, mais frágeis ou mais caros de reproduzir.

## ClickHouse sob o protocolo do experimento

### Estrutura funcional da trilha ClickHouse

Na configuração deste repositório, ClickHouse aparece como a materialização mais clássica do paradigma hot-analytic. O ledger canônico já chega semanticamente depurado pelo storage writer, que realiza a derivação contábil, preserva a disciplina de dupla entrada e expõe ao backend um fluxo normalizado de entries. Isso significa que a trilha ClickHouse não precisa resolver o problema conceitual mais duro do domínio, que é a tradução de eventos de negócio heterogêneos em um modelo financeiro consistente. Em vez disso, ela recebe um stream já pronto para ser indexado e servido.

Esse detalhe metodológico é decisivo. Ele permite que o benchmark observe ClickHouse em um regime particularmente favorável à sua natureza: ingestão relativamente simples, serving consultivo intenso e necessidade de responder bem a resumos, workspaces e consultas filtradas sobre um conjunto de dados em crescimento. A força de ClickHouse, nesse contexto, não vem de uma semântica incremental sofisticada, mas da combinação entre armazenamento colunar, compressão, pruning e custo baixo para agregações recorrentes quando a ordenação e a modelagem tabular estão ajustadas ao workload.

### Superfície HTTP observada

A rodada canônica final de ClickHouse apresentou o melhor p95 de `summary` na API entre as stacks comparadas. Esse resultado é coerente com a função que o backend desempenha no experimento. O endpoint `summary` representa precisamente o tipo de consulta que motores colunares bem organizados tendem a servir com alta eficiência: agregações consolidadas, cardinalidade moderada e conjunto de colunas relativamente estável. O mesmo raciocínio ajuda a explicar o bom desempenho em `entries`, ainda que a diferença para Pinot seja menor nessa superfície.

Já o resultado de `workspace` é levemente distinto. ClickHouse não foi o melhor, embora tenha permanecido em faixa bastante competitiva. Isso sugere que o workspace, por sua própria natureza, custa mais do que o resumo executivo simples. Nessa API, o sistema precisa combinar mais dados, transportar payload significativamente maior e preservar coerência entre subconjuntos heterogêneos do dashboard. O fato de ClickHouse continuar bem posicionado mesmo assim reforça a interpretação de que a trilha estava bem calibrada para leitura quente de estado já materializado.

### SQL nativo e leitura quente

A leitura SQL de ClickHouse permaneceu em segundo lugar, atrás apenas de Pinot, em todas as consultas canônicas bem-sucedidas. Essa proximidade é importante porque revela que a superioridade consultiva de Pinot não implica uma derrota estrutural de ClickHouse; ela mostra apenas que, neste corpus específico, Pinot extraiu ainda mais eficiência em certas consultas sintéticas de baixa cardinalidade. Para fins de engenharia, isso significa que a decisão entre os dois motores não pode ser baseada apenas em uma diferença pontual de milissegundos. É preciso considerar qual dos dois exige menos coordenação periférica, menos ajuste fino, menos custo operacional local e menos complexidade para preservar a experiência percebida do painel.

### Convergência visual e relação com o gateway

O dado mais instrutivo da trilha ClickHouse talvez não seja sua latência pura, mas o fato de combinar boa superfície consultiva com uma cadência autoritativa de snapshots muito superior à observada em Pinot. Esse ponto importa porque demonstra que o sucesso de ClickHouse, no experimento, não se limitou ao banco isolado. Houve também uma boa acomodação entre banco, API, gateway e frontend. Em outras palavras, a stack não ficou refém de uma escolha entre duas virtudes incompatíveis. Ela conseguiu preservar boa leitura HTTP e SQL sem sacrificar o ritmo de reconvergência autoritativa do painel.

Isso sugere que a estratégia híbrida associada a ClickHouse, baseada em feed de eventos para continuidade imediata e snapshots periódicos para reconciliação, está suficientemente madura para o workload testado. Não significa que ela resolveria qualquer cenário. Significa apenas que, neste domínio e neste protocolo, a coordenação extra exigida por um motor hot-analytic não produziu penalidade decisiva na experiência percebida.

### Diagnóstico da tentativa substituída

O ponto que impede uma leitura triunfalista da stack é a existência de uma rodada anterior substituída com um volume massivo de falhas SQL. Essa tentativa mostra que a trilha ClickHouse não deve ser lida como naturalmente robusta em qualquer configuração. O experimento preservou evidência de que certas combinações de estado, bootstrap, carga ou preparação do ambiente foram capazes de degradar severamente a coleta SQL. É exatamente por isso que a rodada final precisa ser interpretada não apenas como “o resultado do backend”, mas como “o resultado do backend quando a trilha operacional correta já havia sido estabilizada”.

Em termos científicos, isso não invalida o bom resultado final. Mas impõe cautela: o benchmark não autoriza concluir que ClickHouse é simplesmente rápido; ele autoriza concluir que ClickHouse foi rápido na rodada canônica estabilizada, ao passo que uma tentativa anterior mostrou sensibilidade importante à preparação experimental. Esse contraste torna a stack mais interessante, e não menos. Ele mostra que performance observada e robustez de repetição não são a mesma coisa.

## Druid sob o protocolo do experimento

### A complexidade da topologia Druid no corpus

Nenhuma outra stack do corpus deixa tão claro quanto Druid que benchmarking de backend é benchmarking de sistema multi-serviço. O que se mede ali não é apenas um mecanismo de consulta. Mede-se também a coordenação entre broker, router, supervisor de ingestão, segmentos, metadata store e readiness do ecossistema inteiro. Esse traço distingue Druid não apenas de Materialize, mas também de ClickHouse e Pinot, cujas integrações no repositório, embora complexas, não expõem com a mesma nitidez uma coreografia operacional tão distribuída.

Essa característica ajuda a explicar uma aparente contradição do corpus: Druid teve p95 altos em `summary` e `workspace`, mas ao mesmo tempo apresentou uma das melhores métricas de `frontend_time_to_first_meaningful_state_ms` e manteve taxa de snapshots muito próxima da de ClickHouse. Em leitura simplista, isso pareceria incoerente. Em leitura arquitetural, faz sentido. A prontidão percebida do frontend não depende apenas do tempo de cada consulta pesada; depende também de quando o sistema passa a fornecer material suficiente para que o painel entre em estado semanticamente útil e continue se reconciliando com o fluxo.

### Warm-up e transição de readiness

Os próprios artefatos deixam claro que a trilha Druid passou por warming up real. Os primeiros 503 em endpoints de API e as transições registradas no health timeline não são ruído desprezível. Eles demonstram que a stack não entra imediatamente em regime estável no mesmo modo que uma topologia mais compacta. Essa latência de aquecimento tem implicação dupla. De um lado, eleva o custo operacional local do backend. De outro, relativiza qualquer comparação em que se observem apenas os instantes posteriores ao aquecimento.

No entanto, há uma leitura complementar importante. O fato de Druid ter se estabilizado e, uma vez estabilizado, ter sustentado cadência de snapshots e prontidão percebida competitivas, indica que o custo adicional de arranque não o impede de ser interessante para dashboards push-oriented. Ele apenas desloca parte do problema para a engenharia operacional. Isso é coerente com a literatura prática da tecnologia: Druid frequentemente recompensa a organização correta da ingestão e do serving, mas cobra mais disciplina de operação para chegar a esse ponto.

### A anomalia de `filtered_entries`

O maior ponto de atenção na rodada canônica final de Druid é o fracasso sistemático da consulta `filtered_entries` no corpus SQL. Esse dado não pode ser tratado como detalhe menor, porque ele rompe a comparabilidade plena entre as superfícies SQL canônicas. Ao mesmo tempo, seria um erro transformá-lo em condenação total da tecnologia. O mais defensável é tratá-lo como uma interseção entre semântica da consulta, estado da ingestão, tradução SQL e sensibilidade da trilha específica construída no repositório.

Para o artigo, a consequência é metodológica. Em vez de esconder a falha e manter apenas a tabela resumida, é preciso explicitar que a bateria conclusiva de Druid ficou parcialmente incompleta na superfície SQL filtrada, apesar de ter permanecido funcional e até competitiva no plano de convergência visual. Isso reforça a ideia central do trabalho: não existe uma única dimensão dominante capaz de absorver as demais.

### Economia de experiência percebida

Druid mostrou que, em certos cenários, o usuário pode receber uma experiência inicial muito boa antes que as superfícies consultivas mais pesadas atinjam sua melhor forma. Em aplicações gerenciais, isso não é trivial. A utilidade prática do painel muitas vezes depende de o operador voltar a ver um estado coerente rapidamente, ainda que parte das consultas profundas ou parte dos filtros sofisticados exija mais tempo para convergir. Em outras palavras, a stack sugere uma forma de economia arquitetural na qual a experiência inicial pode ser muito boa mesmo quando a latência total de consulta não é líder.

### Leitura crítica da trilha Druid

O backend sai do corpus com um perfil ambíguo, porém intelectualmente valioso. Ele não vence na leitura crua de p95 HTTP nem oferece a superfície SQL mais limpa. Ainda assim, aparece como uma solução plausível para cenários em que o problema dominante seja manter ritmo autoritativo de snapshots e boa percepção inicial do frontend, desde que a equipe aceite a maior exigência operacional e lide explicitamente com a fragilidade de certos caminhos de consulta.

## Pinot sob o protocolo do experimento

### Superioridade consultiva e seus limites

Pinot foi o melhor backend do corpus em consultas SQL e o melhor em parte da superfície HTTP. Isso já seria suficiente para destacá-lo. Mas o dado mais interessante é que essa superioridade apareceu de forma consistente em várias consultas de natureza distinta, o que sugere um casamento particularmente eficiente entre o workload sintético do relatório e o estilo de serving operacional para o qual Pinot foi desenhado.

Ao mesmo tempo, o próprio corpus impede que essa superioridade seja convertida em vitória universal. O backend exibiu taxa autoritativa de snapshots dramaticamente inferior à das demais stacks. Portanto, a leitura correta não é “Pinot é o melhor”; a leitura correta é “Pinot foi o melhor motor de leitura direta no protocolo observado, mas essa vantagem não se converteu automaticamente em cadência autoritativa equivalente na camada de atualização visual”.

### O papel do frontend especializado

Essa dissociação é coerente com a integração adotada no repositório. A trilha Pinot foi desenhada de modo particularmente favorável a um frontend mais ativo na projeção local de eventos. Isso significa que parte da agilidade percebida não depende apenas do backend responder rápido, mas também da disciplina com que o cliente mantém estado transitório útil antes da reconciliação completa. Em termos de arquitetura de produto, isso é excelente quando a prioridade máxima é fluidez operacional imediata. Em termos de governança técnica, porém, desloca responsabilidade para a borda.

Uma consequência direta dessa escolha é que a stack precisa ser julgada não apenas por sua leitura quente, mas pela distância entre a performance consultiva e a atualização autoritativa efetivamente medida. Se essa distância se torna grande demais, há risco de que o sistema pareça responsivo, mas permaneça dependente de uma negociação mais complexa entre evento local, reancoragem periódica e completude do dashboard.

### Ausência de cobertura diagnóstica no fim da rodada

Outro ponto crítico da trilha Pinot é a cobertura final reduzida nos snapshots de debug, que no corpus aparece mais limitada do que a observada em ClickHouse e Druid. Isso não destrói o resultado consultivo, mas empobrece a auditabilidade pós-rodada. Para um artigo técnico aprofundado, esse detalhe importa bastante, porque parte da força do benchmark está precisamente em preservar rastros que expliquem o que aconteceu quando algo vai bem e quando algo vai mal. Um backend muito rápido, porém menos auditável ao final da rodada, produz uma forma diferente de custo de engenharia.

### Leitura arquitetural final de Pinot

O que Pinot sugere, então, é uma solução particularmente forte quando a organização está disposta a aceitar um frontend mais participante e deseja maximizar a velocidade de serving sobre um estado analítico quente. A questão crítica passa a ser governar corretamente a diferença entre rapidez consultiva e ritmo de ressincronização autoritativa. Se a aplicação tolera ou explora bem essa arquitetura, Pinot torna-se extremamente atraente. Se a aplicação exige atualização autoritativa muito frequente do painel integral, a vantagem consultiva pode não bastar.

## Materialize sob o protocolo do experimento

### O backend mais teoricamente promissor do corpus

Materialize ocupa no relatório a posição mais delicada e mais interessante. Em tese, é o backend cujo paradigma mais naturalmente se aproxima da ambição conceitual do problema: reduzir a distância entre stream canônico e estado derivado consultável por meio de manutenção incremental. Em outras palavras, ele promete resolver, no coração do próprio sistema, parte do problema que as demais stacks resolvem por composição entre writer, API, gateway e frontend.

Essa promessa, porém, só tem valor científico se for testada contra custos reais. E o corpus mostra custos reais expressivos. Materialize foi a stack mais cara em várias consultas HTTP e SQL, além de registrar a maior volatilidade operacional no health timeline. Portanto, sua relevância no trabalho não decorre de ser a “vencedora prática”, mas de funcionar como caso-limite epistemicamente rico: a tecnologia mais alinhada ao ideal incremental não foi, neste protocolo, a mais eficiente como superfície de leitura.

### Dissociação entre utilidade inicial e custo consultivo

O dado mais esclarecedor de Materialize talvez seja exatamente a dissociação entre utilidade inicial e custo consultivo. O frontend alcança estado significativo antes que as consultas pareçam baratas. Isso aponta para uma propriedade arquitetural importante: a experiência do usuário não está rigidamente acoplada ao tempo de cada consulta isolada. A stack consegue, ao menos parcialmente, transformar atualização incremental e snapshot autoritativo progressivo em utilidade operacional antes que a superfície consultiva integral se torne comparável à de motores hot-analytic.

Em termos de teoria de sistemas interativos, isso é um resultado relevante. Mostra que latência de query e latência percebida pertencem a camadas relacionadas, mas não idênticas. Em termos de engenharia, contudo, o resultado só vale se o custo operacional e a instabilidade não anularem a viabilidade da solução em produção.

### Volatilidade e cobertura de debug

As transições de health e a baixa cobertura de snapshots finais de debug em Materialize não podem ser tratadas como pequenos acidentes. Elas sugerem que a trilha incremental, do modo como foi instrumentada no repositório, ainda não estava plenamente madura no momento da coleta. Isso não prova que a tecnologia seja intrinsecamente instável. Prova apenas que a configuração concreta usada no corpus ainda impunha fricção suficiente para aparecer nas métricas de operação.

Esse é um ponto especialmente importante para o artigo, porque ajuda a escapar de uma leitura binária. Não seria correto dizer que Materialize “falhou”, pois preservou corretude contábil e entregou indícios fortes de valor arquitetural. Também não seria correto dizer que “venceu conceitualmente”, ignorando a realidade das consultas e da operação. O resultado mais honesto é que Materialize funcionou como a stack de maior interesse analítico e de menor maturidade prática relativa no corpus medido.

### O valor científico da trilha Materialize

Mesmo sem liderar as métricas de leitura, Materialize talvez seja a tecnologia que mais obriga o relatório a elevar o nível do debate. Ele impede que a avaliação de backends seja reduzida a um ranking de p95. Ao fazer isso, força a pesquisa a reconhecer que o problema do trabalho não é simplesmente acelerar consultas, mas articular semântica incremental, experiência percebida, corretude financeira e custo operacional. Esse deslocamento conceitual é uma das contribuições mais importantes do corpus.

## Síntese técnica do capítulo

Analisadas isoladamente, as stacks podem parecer apenas alternativas de implementação para a mesma função. Analisadas à luz do experimento, revelam-se arranjos com lógicas internas bem diferentes. ClickHouse destacou-se como a solução mais consistente entre leitura rápida e boa cadência autoritativa após estabilização. Druid apareceu como o backend em que o custo operacional do arranque pesa mais, mas onde a experiência percebida e a cadência de snapshots podem permanecer muito boas quando o sistema entra em regime. Pinot confirmou superioridade consultiva robusta, ao custo de depender mais de arquitetura `push-first` e menos de reancoragem frequente do estado global. Materialize, por fim, mostrou o maior alinhamento conceitual com o ideal incremental do problema, mas também o maior custo para tornar esse ideal operacionalmente estável.

O valor do benchmark, portanto, não está em decretar um vencedor único. Está em mostrar que cada backend oferece uma solução distinta para um mesmo sistema de referência e que essas soluções cobram preços diferentes em consulta, convergência, operação e auditabilidade. Esse é o tipo de resultado que um artigo técnico amplo precisa registrar, porque ele continua relevante mesmo quando as posições relativas mudarem em futuras rodadas de rerun.