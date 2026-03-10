# Matriz de Decisão Arquitetural

## Por que este capítulo existe

Um problema recorrente em relatórios de benchmark é o salto brusco entre evidência e prescrição. Primeiro apresenta-se uma massa de números; depois, quase sem mediação, declara-se um “vencedor” para uso prático. Essa passagem raramente é inocente. Ela costuma embutir prioridades implícitas que não foram declaradas: preferência por throughput, aversão a complexidade operacional, valorização de latência percebida, sensibilidade a custo de memória, exigência de auditabilidade ou tolerância a protagonismo do frontend. Como este relatório explicitamente recusou a ideia de vencedor universal, torna-se necessário oferecer uma camada final de decisão arquitetural capaz de ligar métricas, paradigmas e contextos de uso de forma mais transparente.

Este capítulo cumpre essa função. Ele não substitui a discussão técnica anterior e tampouco reduz a decisão a uma tabela de notas. Seu objetivo é mostrar como os resultados podem ser traduzidos em critérios de escolha sob diferentes prioridades organizacionais. Em outras palavras, o capítulo converte o corpus em ferramenta de decisão, sem trair a multidimensionalidade que o próprio benchmark revelou.

## Eixo decisório 1: quando a prioridade dominante é consulta rápida de painel

Em organizações cujo problema principal é servir rapidamente resumos executivos, painéis consolidados e consultas interativas frequentes sobre um estado já aquecido, o eixo dominante tende a ser a velocidade consultiva. Nesse cenário, a pergunta central não é tanto como reduzir a distância conceitual entre stream e snapshot, mas como garantir que o painel responda com baixa latência sob operação normal. O corpus aponta com força para duas candidaturas principais: ClickHouse e Pinot.

ClickHouse aparece como solução de maior equilíbrio geral nesse eixo. Sua latência HTTP foi muito forte, sua superfície SQL permaneceu extremamente competitiva e a cadência autoritativa de snapshots não entrou em colapso para sustentar essa velocidade. Isso o torna especialmente atraente para equipes que desejam alto desempenho de leitura sem aceitar degradação severa de reconvergência visual. Além disso, a topologia da trilha no repositório é relativamente inteligível: writer canônico, serving analítico, gateway e frontend conseguem cooperar sem exigir que o frontend assuma a maior parte da inteligência temporal.

Pinot, por outro lado, surge como solução particularmente poderosa quando a prioridade é maximizar a agressividade do serving SQL e HTTP puro. O backend demonstrou excelente comportamento em consultas sintéticas e em partes importantes da API. Contudo, a decisão por Pinot só é integralmente defensável quando a organização assume conscientemente seu preço arquitetural: mais protagonismo do frontend, maior importância da política de reancoragem e menor cadência autoritativa observada no corpus final. Se esse preço for aceitável, Pinot torna-se opção muito forte. Se não for, sua superioridade consultiva talvez não compense a distância para o estado global autoritativo do painel.

## Eixo decisório 2: quando a prioridade dominante é prontidão percebida do frontend

Há cenários em que o principal problema de negócio não é o menor p95 absoluto, mas o tempo necessário para que o operador volte a enxergar um painel útil logo após o arranque, a reconexão ou o início da sessão. Em tais contextos, métricas como `frontend_time_to_first_meaningful_state_ms` e `snapshot_rate_per_second` ganham peso extraordinário. O corpus mostra que, nesse eixo, Druid precisa ser levado muito a sério.

Druid oferece talvez o melhor exemplo de como experiência percebida e custo consultivo podem divergir. Sua API não lidera a comparação, e certas superfícies SQL permaneceram frágeis. Mesmo assim, a retomada visual e a cadência autoritativa do painel aparecem como pontos fortes relevantes. Isso sugere que Druid é tecnicamente atraente quando a organização precisa de sensação operacional de tempo real muito cedo e aceita pagar com topologia mais exigente e aquecimento mais delicado.

ClickHouse continua sendo forte também nesse eixo, embora menos brilhante que Druid no instante inicial percebido. A diferença é que ClickHouse entrega esse resultado em uma configuração mais equilibrada entre consulta, snapshots e estabilidade final. A decisão entre os dois depende, portanto, do quanto a equipe valoriza o arranque perceptual puro em comparação com previsibilidade operacional e completude de superfície.

## Eixo decisório 3: quando a prioridade dominante é governança do estado autoritativo

Em certas organizações, a maior preocupação não é apenas “parecer rápido”, mas assegurar que o painel reflita, com a menor distância possível, um estado autoritativo consistente e semanticamente controlado. Esse eixo é especialmente importante em domínios regulados, contábeis, financeiros ou operacionais críticos. Nesses casos, a arquitetura que governa a autoridade do snapshot torna-se tão importante quanto a velocidade consultiva.

Sob essa ótica, Materialize reaparece com força analítica, mesmo sem liderar consultas. O backend não foi o mais rápido, mas continua sendo o caso do corpus que melhor encarna a ambição de aproximar a manutenção do estado derivado do próprio coração do sistema. Isso não é pequeno. Significa que, para organizações cuja estratégia de longo prazo exige tratar incrementalidade e temporalidade como virtudes centrais do backend, Materialize pode representar a trilha de maior valor evolutivo, ainda que não seja a melhor resposta imediata para o workload já testado.

ClickHouse e Druid também podem sustentar autoridade do painel, mas o fazem por composição. Em ambos, parte importante da solução continua distribuída entre API, gateway e frontend. Isso é totalmente aceitável em muitas arquiteturas. Apenas muda a natureza do controle. Em vez de concentrar a autoridade incremental no backend, a organização passa a governá-la através de contratos entre múltiplas camadas.

## Eixo decisório 4: quando a prioridade dominante é simplicidade operacional local

Há equipes cujo principal gargalo não está no hardware nem no modelo conceitual, mas na capacidade prática de operar, depurar e repetir a stack. Nesses ambientes, custo operacional local passa a ser variável central. O benchmark mostra com clareza que esse custo não é homogêneo.

Druid é a stack mais explicitamente onerosa nesse quesito, porque sua topologia distribuída torna o aquecimento e a coordenação muito mais sensíveis. Pinot também demanda cuidados relevantes, embora em outro formato, sobretudo na relação entre backend e política de frontend. Materialize cobra preço de natureza distinta: não tanto pela multiplicidade de serviços, mas pela sofisticação do paradigma incremental e pela instabilidade ainda observável na trilha atual. ClickHouse surge, no corpus final estabilizado, como a solução que melhor combina alta performance com uma sensação relativamente mais controlável de operação, desde que o pipeline canônico anterior a ele esteja bem resolvido.

Em linguagem decisória, isso significa que ClickHouse tende a ser a alternativa de menor atrito para equipes que desejam resultado forte sem transformar o benchmark inteiro em projeto de operação distribuída. Pinot pode ser igualmente atraente em times maduros em frontend e serving interativo. Druid e Materialize, por sua vez, exigem disposição explícita para investir em maturação operacional e observabilidade.

## Eixo decisório 5: quando a prioridade dominante é aprendizagem estratégica da organização

Nem toda escolha de backend é decisão de curto prazo. Algumas organizações usam projetos experimentais para aprender sobre paradigmas, preparar capacidades internas e decidir em que direção tecnológica desejam evoluir. Nesse tipo de cenário, o backend “mais rápido hoje” nem sempre é o backend “mais valioso para aprender”.

Sob esse critério, Materialize ocupa posição privilegiada. Ele força a equipe a pensar em incremental view maintenance, fronteiras temporais, autoridade do snapshot e custo semântico da modelagem relacional. Mesmo que a trilha atual ainda esteja aquém de uma solução prática madura para o corpus medido, o backend amplia o repertório conceitual do projeto. Druid também tem valor estratégico semelhante, embora por outra razão: ele expõe, com muita clareza, o custo e o poder de uma topologia de serving analítico distribuído orientada a eventos.

ClickHouse e Pinot, por outro lado, oferecem aprendizado estratégico mais ligado a excelência de serving, modelagem quente e eficiência consultiva. A escolha entre aprender mais sobre incrementalidade ou mais sobre leitura quente não é técnica apenas; é também organizacional e de portfólio.

## Cenários de decisão sintetizados

Se uma organização precisa escolher um backend para um painel gerencial com forte exigência de leitura rápida, baixa tolerância a complexidade distribuída adicional e interesse em boa cadência de snapshots autoritativos, o corpus favorece ClickHouse como primeira escolha concreta. Se a organização deseja maximizar performance consultiva e já domina políticas sofisticadas de frontend e gateway, Pinot passa a ser opção muito atraente. Se o objetivo é privilegiar experiência percebida e recuperação visual rápida, aceitando maior disciplina de operação, Druid ganha força. Se o horizonte é construir uma linha de evolução incremental mais profunda, mesmo com maior custo atual, Materialize continua sendo a investigação mais promissora.

É crucial observar que essas recomendações não se excluem mutuamente. Um laboratório de arquitetura maduro pode perfeitamente adotar ClickHouse para produção imediata, manter Pinot como referência de performance consultiva, usar Druid como linha de comparação para topologias de ingestão e sustaining analítico, e preservar Materialize como trilha estratégica de pesquisa e evolução. O relatório só faz sentido pleno quando lido como catálogo de possibilidades tecnicamente informadas, não como cerimônia de coroação de um único produto.

## O que a matriz de decisão corrige em relação a benchmarks simplificados

Esta matriz corrige dois vícios comuns. O primeiro é o vício do monocritério, em que a decisão é tomada como se todas as organizações tivessem a mesma função objetivo. O segundo é o vício da abstração excessiva, em que a arquitetura real da stack é apagada e os produtos passam a ser comparados como se existissem fora das APIs, gateways, frontends e contratos que lhes dão sentido no experimento.

Ao explicitar critérios, o capítulo torna mais difícil o uso indevido do benchmark. Ninguém poderá citar o relatório honestamente dizendo apenas “o backend X venceu”, sem também dizer em qual eixo ele venceu, qual custo pagou e quais condições de integração tornaram esse resultado possível.

## Cenários exemplares de decisão

Para tornar a matriz ainda mais concreta, vale imaginar alguns cenários exemplares. O primeiro é o de uma empresa que já possui pipeline contábil canônico estável, equipe pequena de backend e forte necessidade de dashboards executivos responsivos com baixa tolerância a crescimento de complexidade operacional. Nesse caso, a combinação de alto desempenho consultivo, cadência autoritativa robusta e integração relativamente mais controlável torna ClickHouse a aposta mais prudente no corpus atual. A decisão não decorre apenas da velocidade, mas do fato de que o backend oferece ótima resposta sem exigir, no estado presente do repositório, o grau de reengenharia que outras trilhas ainda pedem.

O segundo cenário é o de uma organização digital cuja cultura de produto aceita um frontend muito ativo, com boa engenharia de estado local, forte disciplina de reancoragem e prioridade máxima em experiência de navegação e exploração interativa. Nessa configuração, Pinot ganha valor adicional. Sua superioridade consultiva pode ser explorada mais plenamente quando a equipe não vê a inteligência do cliente como problema, mas como parte deliberada da solução arquitetural.

O terceiro cenário é o de uma operação que precisa de retomada perceptual extremamente rápida após reconexões, reinícios ou oscilações de readiness, e que já tem maturidade razoável para operar topologias mais distribuídas. Aqui, Druid pode ser estrategicamente vantajoso. O backend passa a ser justificado menos por vencer tabelas de consulta e mais por oferecer um tipo de compromisso entre fluxo, snapshots e percepção de utilidade que outras stacks não entregam da mesma forma.

O quarto cenário é o de uma organização que deseja usar o projeto não apenas para servir dashboards atuais, mas para formar competência interna em manutenção incremental, temporalidade e semântica de estado derivado mais próxima do stream. Para esse contexto, Materialize permanece extremamente valioso, mesmo sem liderança prática nas métricas finais do corpus. O ganho não é imediato em p95; é estratégico na capacidade de experimentar um paradigma que pode tornar-se cada vez mais relevante à medida que o domínio exigir replay, correção tardia e views incrementais mais ricas.

## Trade-offs que não devem ser omitidos no uso do relatório

Uma matriz de decisão só é honesta quando explicita também o que ela não resolve. Este relatório, por mais ampliado que esteja, ainda se apoia em um único host local, em budgets de fase controlados e em um conjunto finito de cenários. Isso significa que as recomendações aqui derivadas devem ser interpretadas como decisões informadas pelo corpus, não como leis gerais sobre os produtos avaliados. Há ainda espaço real para mudança de posição relativa quando o workload, a infraestrutura ou a política de frontend se alterarem.

Também não seria correto usar a matriz como desculpa para apagar o papel do restante da stack. Nenhum backend deste relatório existe sozinho. Todos dependem de writer, API, gateway, frontend, health checks e observabilidade. Se uma equipe tentar “importar” a conclusão do relatório sem importar a disciplina arquitetural correspondente, o documento será usado de forma incorreta. A matriz de decisão é uma ferramenta para escolher soluções dentro de um sistema, não um atalho para pular o desenho do sistema.

Há, por fim, um último trade-off que precisa ser verbalizado. Quanto mais se busca uma resposta universal, menos útil o benchmark se torna. O valor real do relatório está justamente em obrigar a organização a dizer o que deseja otimizar. Essa obrigação pode ser desconfortável, mas é tecnicamente saudável. Ela evita que a decisão sobre backend seja tomada no terreno vago do gosto pessoal ou da reputação de mercado e a desloca para o terreno explícito dos critérios, dos riscos e das prioridades.

## Fecho da matriz decisória

A utilidade final da matriz não está em encerrar o debate, mas em discipliná-lo. Ela obriga cada decisão a declarar seu critério dominante, seu apetite por complexidade, sua relação com a autoridade do estado e sua prioridade entre consulta rápida, prontidão percebida e aprendizagem estratégica. Esse é exatamente o tipo de ganho que um documento técnico extenso deve oferecer. Sem isso, a ampliação do relatório seria só volume; com isso, ela se torna estrutura de decisão.