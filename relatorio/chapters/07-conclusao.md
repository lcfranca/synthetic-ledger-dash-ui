# Conclusão

## Resposta à pergunta do relatório

O experimento realizado permite responder, com base empírica real e rastreável, que a escolha de backend para dashboards gerenciais orientados por eventos não admite resposta universal. O backend mais adequado depende da dimensão que se deseja otimizar e do custo aceitável nas demais dimensões.

Se o critério dominante for latência de API sob consultas de painel, ClickHouse apresentou o melhor comportamento observado neste corpus. Se o foco principal recair sobre latência SQL nativa, Pinot obteve os menores p95 medidos. Se a prioridade for combinar prontidão visual muito baixa com cadência consistente de snapshots autoritativos, Druid emergiu como o melhor compromisso observado entre convergência e custo de leitura. Materialize, por sua vez, demonstrou a capacidade de dissociar a utilidade inicial do frontend do custo total de consulta, mas o fez com a maior latência interna e com a maior volatilidade operacional dentre as stacks comparadas.

## Contribuição analítica principal

O resultado mais relevante do trabalho não é a proclamação de um vencedor absoluto, mas a demonstração de que a avaliação de backends para serving near-real-time precisa ser multidimensional. A combinação de API, SQL, websocket, health e corretude contábil mostrou que conclusões baseadas em uma única família de métricas podem ser profundamente enganosas.

Esse ponto aparece com clareza em pelo menos dois casos. Pinot foi excelente no plano consultivo, mas exibiu cadence de snapshots muito inferior à das demais stacks. Materialize, em sentido oposto, sustentou convergência visual competitiva mesmo sob latências SQL e HTTP muito mais elevadas. Tais contrastes seriam invisíveis em um benchmark restrito a p95 de consulta.

## Implicações arquiteturais

As evidências coletadas favorecem uma leitura arquitetural específica. Motores analíticos voltados a serving direto tendem a maximizar performance de leitura imediata. Sistemas com projeções incrementais podem reduzir o intervalo entre evento e utilidade percebida, mas não necessariamente minimizam o custo das consultas subjacentes. Sistemas intermediários, como Druid no corpus observado, podem oferecer equilíbrio pragmático entre as duas frentes, desde que a orquestração operacional respeite suas exigências de readiness e ingestão.

Essa conclusão é especialmente relevante para sistemas contábeis e gerenciais, nos quais a confiabilidade semântica do estado exibido importa tanto quanto a velocidade. A manutenção de `balance_sheet_difference` igual a 0.0 em todas as stacks observadas mostra que o benchmark preservou a dimensão substantiva do problema, e não apenas sua superfície de performance.

## Limites e agenda imediata

As conclusões deste relatório são fortes como descrição do corpus coletado, mas deliberadamente moderadas como generalização. O estudo ainda carece de repetições adicionais por backend, variação controlada de carga, consolidação estatística sobre múltiplas rodadas e exploração mais sistemática das métricas de recursos computacionais. Também permanece aberta a investigação de ajustes de configuração que possam alterar substancialmente a posição relativa de cada stack.

O passo natural seguinte não é reescrever a taxonomia dos resultados, mas expandir a amostra mantendo o mesmo protocolo auditável. Isso inclui repetir a bateria conclusiva, tratar variância inter-rodada, incorporar análise transversal de CPU e memória e investigar por que determinados backends dissociam tão fortemente latência consultiva e convergência visual.

## Fecho final

O relatório conclui, portanto, que o problema de serving para dashboards gerenciais em tempo real deve ser formulado como problema de sistema completo. Evento, trilha contábil, backend, API, gateway e frontend compõem uma cadeia única de valor observável. A stack tecnicamente preferível será aquela que melhor alinhar, para um contexto específico, desempenho consultivo, estabilidade operacional, cadência de atualização e preservação da corretude contábil.

No corpus empírico aqui obtido, ClickHouse foi a melhor opção geral para latência de leitura, Pinot foi a melhor opção para SQL puro, Druid apresentou o compromisso mais equilibrado entre rapidez percebida e cadência autoritativa, e Materialize permaneceu como a stack mais interessante para explorar semântica incremental, embora ainda não como a mais eficiente para o workload medido. Essa é a conclusão substantiva que os dados reais autorizam neste estado do projeto.