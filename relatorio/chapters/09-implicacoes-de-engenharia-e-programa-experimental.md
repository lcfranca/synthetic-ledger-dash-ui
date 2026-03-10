# Implicações de Engenharia e Programa Experimental

## O benchmark como ferramenta de arquitetura, não apenas de medição

Uma consequência importante deste trabalho é mostrar que o benchmark deixa de ser útil quando é tratado apenas como mecanismo de medição retrospectiva. O valor real do corpus cresce quando ele passa a orientar decisões de arquitetura futuras. Para isso, o artigo precisa ultrapassar a descrição dos números e entrar no terreno das implicações de engenharia: que tipo de equipe cada stack pressupõe, que classes de risco cada integração produz, que formas de observabilidade são indispensáveis, quais contratos de dados precisam permanecer estáveis e em que pontos o repositório ainda precisa amadurecer antes de repetir a bateria com poder analítico maior.

Essa leitura interessa porque sistemas near-real-time orientados por eventos costumam fracassar não apenas por escolherem o backend “errado”, mas por não alinharem o backend escolhido à topologia do restante da stack. Um motor consultivo excelente pode degradar a experiência se a API, o gateway e o frontend forem incapazes de sustentar reconciliação robusta. Um mecanismo incremental elegante pode produzir atrito se o pipeline de bootstrap e observabilidade não estiver à altura da sua semântica temporal. Em ambos os casos, a decisão equivocada não está só no produto, mas na engenharia de integração.

## Contratos canônicos como patrimônio do experimento

O ativo mais valioso do repositório talvez não seja nenhum backend específico, mas o contrato canônico que o benchmark conseguiu estabilizar. O stream `ledger-entries-v1`, a disciplina de dupla entrada e a separação entre evento bruto e entry contábil derivada constituem a espinha dorsal da comparabilidade. Sem esse contrato, cada backend precisaria ser comparado sobre pipelines semânticos distintos, e o benchmark degeneraria em competição entre interpretações diferentes do domínio.

Para a engenharia futura, isso significa que qualquer evolução do repositório deve proteger agressivamente essa camada. É admissível mudar APIs, gateways, modelos auxiliares, caches, filtros, views materializadas e frontends especializados. Não é admissível fragilizar a camada canônica que torna as comparações defensáveis. Em termos práticos, isso implica versionamento rigoroso de schemas, testes de compatibilidade de eventos, validação contínua da contabilidade derivada e capacidade de replay auditável.

## Observabilidade como requisito de comparabilidade

Outra implicação forte do corpus é a necessidade de elevar observabilidade ao estatuto de requisito metodológico. Não basta que uma stack “funcione”; ela precisa funcionar de modo auditável. O problema das coberturas parciais de debug em algumas rodadas deixa isso muito claro. Quando faltam snapshots finais consistentes, o artigo perde poder explicativo. Não se perde apenas um detalhe operacional; perde-se capacidade de reconstruir, a posteriori, por que o sistema convergiu, divergiu, aqueceu lentamente ou falhou numa consulta específica.

O programa experimental futuro deveria, portanto, estabelecer um princípio simples: toda superfície usada na argumentação do artigo deve ter superfície correspondente de observabilidade. Se uma API entra na comparação, deve haver payload final capturável. Se uma estratégia de convergência depende de gateway, deve haver trilha de estado suficiente para reconstruir como esse gateway se comportou. Se um backend depende fortemente de bootstrap ou de ingestão, os estágios desse bootstrap precisam virar métricas de primeira classe.

## Replays, correções tardias e semântica temporal

O corpus atual é sólido para a primeira bateria conclusiva, mas ainda insuficiente para esgotar a dimensão temporal do problema. Uma agenda de engenharia realmente ambiciosa deve introduzir cenários controlados de replay, correção tardia, retrações, reprocessamento parcial e divergência entre dados de catálogo e histórico de ledger. Essas situações não são patológicas no domínio; são parte normal da vida de sistemas financeiros reais.

O que o benchmark fez até aqui foi provar que vale a pena tratar essas questões como objeto central. O que falta fazer é incorporá-las ao protocolo, com cenários específicos e métricas dedicadas. Para ClickHouse, isso permitiria observar quanto da robustez depende de estado já estabilizado. Para Druid, revelaria o custo de rehidratação e recompostura da ingestão em cenários mais próximos da operação real. Para Pinot, testaria a robustez da combinação entre projeção local e reancoragem periódica. Para Materialize, ofereceria o palco ideal para observar em que medida a vantagem conceitual incremental se converte em vantagem empírica quando o domínio efetivamente exige atualização semântica difícil.

## Engenharia de frontend e o erro de subestimar a borda

Uma das lições mais importantes do corpus é que o frontend não pode ser tratado como apêndice cosmético do benchmark. Em várias stacks, parte crítica da experiência percebida depende de como a borda consome websocket, projeta eventos, decide quando trocar o estado exibido e quando aceitar um snapshot autoritativo como suficiente. Ignorar essa camada seria mutilar o fenômeno medido.

Do ponto de vista de produto, isso implica que o benchmark futuro deveria versionar também políticas de frontend: critérios de estado significativo, modos de ressincronização, políticas de deduplicação, tolerância a vazio transitório, fallback para polling e tratamento de desconexão. Sem isso, corre-se o risco de atribuir ao banco diferenças que, na prática, pertencem à política de UI e de gateway.

## Uma agenda objetiva para reruns de dupla conformação

O pedido de dupla conformação faz sentido e o corpus já indica onde essa energia deve ser gasta primeiro. A prioridade técnica imediata é repetir a bateria final com foco especial em Druid e ClickHouse. Druid precisa validar novamente a consulta `filtered_entries` e confirmar se os 503 iniciais e as falhas parciais de API pertencem de fato ao aquecimento esperado ou a uma fragilidade ainda não totalmente resolvida. ClickHouse, por sua vez, precisa repetir a trajetória que levou da tentativa substituída com falhas SQL massivas à rodada canônica final limpa, para demonstrar que a melhoria foi estabilização reprodutível e não apenas uma boa execução isolada.

Materialize também merece reruns, mas por razão distinta. No seu caso, o objetivo não é apenas verificar uma falha pontual, e sim medir se a trilha incremental consegue ganhar maturidade prática sem perder a contribuição conceitual. Para Pinot, o foco principal dos reruns não deveria ser latência consultiva, já suficientemente forte no corpus, mas sim a cadência autoritativa de snapshots e a qualidade da auditabilidade final.

## Expansão do protocolo: além de uma única rodada canônica

Para que o relatório cresça em profundidade científica, o protocolo precisa amadurecer de uma “bateria final bem-sucedida” para um desenho com repetições deliberadas, cenários diferenciados e análise de variância. Isso não significa transformar o trabalho num tratado estatístico desconectado da engenharia. Significa apenas reconhecer que a força atual do corpus está na rastreabilidade, e que o próximo salto metodológico natural é combinar essa rastreabilidade com repetição suficiente para separar sinal de variabilidade local.

Um desenho plausível incluiria pelo menos três famílias de cenário. A primeira manteria o caso atual de serving near-real-time contínuo. A segunda introduziria replay controlado e correções tardias. A terceira variaria a composição de filtros, cardinalidades e tamanho de payload do workspace. Com isso, o artigo deixaria de registrar apenas “como as stacks se comportaram num caso” e passaria a mostrar “como os paradigmas se movem quando a pressão do domínio muda”.

## O papel do relatório ampliado dentro do repositório

À medida que o relatório cresce, ele deixa de ser apenas documentação de resultados e passa a funcionar como camada de memória técnica do projeto. Isso é particularmente importante em repositórios experimentais longos, nos quais decisões metodológicas se perdem facilmente com o tempo. Um artigo técnico extenso, desde que ancorado em artefatos reais, cumpre também a função de consolidar racionalidade histórica: por que o protocolo foi desenhado assim, o que se tentou antes, quais trilhas falharam, por que certas correções foram introduzidas, e quais hipóteses ainda permanecem abertas.

Nesse sentido, aumentar a extensão do documento não é luxo estilístico. É uma forma de preservar contexto técnico que, de outro modo, ficaria disperso entre scripts, commits, observações de execução e memória tácita do desenvolvedor.

## Fecho do programa experimental

O programa que emerge deste capítulo é claro. Primeiro, preservar a comparabilidade semântica do contrato canônico. Segundo, elevar observabilidade a requisito de primeira ordem. Terceiro, repetir o corpus final onde houve falha, substituição ou fragilidade de auditabilidade. Quarto, introduzir cenários temporais e operacionais mais duros que aproximem o benchmark da realidade de sistemas financeiros vivos. Quinto, tratar frontend, gateway e backend como partes indissociáveis de uma arquitetura de serving.

Se o repositório seguir esse programa, o relatório deixará de ser apenas uma fotografia competente de uma bateria final e se tornará uma referência técnica ampla sobre como comparar paradigmas de serving para dashboards gerenciais orientados por eventos. Esse é o horizonte que justifica a expansão do texto e a reestruturação do documento nesta versão.