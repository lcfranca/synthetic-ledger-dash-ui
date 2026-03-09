# Conclusao

## 7.1 Resposta a pergunta do relatorio

O experimento realizado permite responder, com base empirica real e rastreavel, que a escolha de backend para dashboards gerenciais orientados por eventos nao admite resposta universal. O backend mais adequado depende da dimensao que se deseja otimizar e do custo aceitavel nas demais dimensoes.

Se o criterio dominante for latencia de API sob consultas de painel, ClickHouse apresentou o melhor comportamento observado neste corpus. Se o foco principal recair sobre latencia SQL nativa, Pinot obteve os menores p95 medidos. Se a prioridade for combinar prontidao visual muito baixa com cadencia consistente de snapshots autoritativos, Druid emergiu como o melhor compromisso observado entre convergencia e custo de leitura. Materialize, por sua vez, demonstrou a capacidade de dissociar a utilidade inicial do frontend do custo total de consulta, mas o fez com a maior latencia interna e com a maior volatilidade operacional dentre as stacks comparadas.

## 7.2 Contribuicao analitica principal

O resultado mais relevante do trabalho nao e a proclamacao de um vencedor absoluto, mas a demonstracao de que a avaliacao de backends para serving near-real-time precisa ser multidimensional. A combinacao de API, SQL, websocket, health e corretude contabil mostrou que conclusoes baseadas em uma unica familia de metricas podem ser profundamente enganosas.

Esse ponto aparece com clareza em pelo menos dois casos. Pinot foi excelente no plano consultivo, mas exibiu cadence de snapshots muito inferior a das demais stacks. Materialize, em sentido oposto, sustentou convergencia visual competitiva mesmo sob latencias SQL e HTTP muito mais elevadas. Tais contrastes seriam invisiveis em um benchmark restrito a p95 de consulta.

## 7.3 Implicacoes arquiteturais

As evidencias coletadas favorecem uma leitura arquitetural especifica. Motores analiticos voltados a serving direto tendem a maximizar performance de leitura imediata. Sistemas com projecoes incrementais podem reduzir o intervalo entre evento e utilidade percebida, mas nao necessariamente minimizam o custo das consultas subjacentes. Sistemas intermediarios, como Druid no corpus observado, podem oferecer equilibrio pragmatico entre as duas frentes, desde que a orquestracao operacional respeite suas exigencias de readiness e ingestao.

Essa conclusao e especialmente relevante para sistemas contabeis e gerenciais, nos quais a confiabilidade semantica do estado exibido importa tanto quanto a velocidade. A manutencao de `balance_sheet_difference` igual a 0.0 em todas as stacks observadas mostra que o benchmark preservou a dimensao substantiva do problema, e nao apenas sua superficie de performance.

## 7.4 Limites e agenda imediata

As conclusoes deste relatorio sao fortes como descricao do corpus coletado, mas deliberadamente moderadas como generalizacao. O estudo ainda carece de repeticoes adicionais por backend, variacao controlada de carga, consolidacao estatistica sobre multiplas rodadas e exploracao mais sistematica das metricas de recursos computacionais. Tambem permanece aberta a investigacao de ajustes de configuracao que possam alterar substancialmente a posicao relativa de cada stack.

O passo natural seguinte nao e reescrever a taxonomia dos resultados, mas expandir a amostra mantendo o mesmo protocolo auditavel. Isso inclui repetir a bateria conclusiva, tratar variancia inter-rodada, incorporar analise transversal de CPU e memoria e investigar por que determinados backends dissociam tao fortemente latencia consultiva e convergencia visual.

## 7.5 Fecho final

O relatorio conclui, portanto, que o problema de serving para dashboards gerenciais em tempo real deve ser formulado como problema de sistema completo. Evento, trilha contabil, backend, API, gateway e frontend compoem uma cadeia unica de valor observavel. A stack tecnicamente preferivel sera aquela que melhor alinhar, para um contexto especifico, desempenho consultivo, estabilidade operacional, cadencia de atualizacao e preservacao da corretude contabil.

No corpus empirico aqui obtido, ClickHouse foi a melhor opcao geral para latencia de leitura, Pinot foi a melhor opcao para SQL puro, Druid apresentou o compromisso mais equilibrado entre rapidez percebida e cadencia autoritativa, e Materialize permaneceu como a stack mais interessante para explorar semantica incremental, embora ainda nao como a mais eficiente para o workload medido. Essa e a conclusao substantiva que os dados reais autorizam neste estado do projeto.