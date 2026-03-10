# Apêndice E - Programa de Reruns, Cenários e Extensões do Benchmark

## Objetivo deste apêndice

O corpus atual é suficientemente forte para sustentar comparação técnica séria, mas ainda não esgota o programa experimental que ele próprio inaugura. Este apêndice organiza, de forma mais operacional, o que deveria ser repetido, ampliado ou tensionado em iterações futuras. Seu valor não está apenas em sugerir “mais testes”, e sim em estruturar uma agenda específica de reruns e novos cenários que preserve compatibilidade com o protocolo já construído.

## Família de reruns 1: dupla conformação das rodadas canônicas

O primeiro bloco de reruns deve repetir a bateria canônica final com o protocolo atual, o mesmo orçamento de fases e o mesmo contrato funcional. O propósito aqui não é descobrir um workload novo, mas medir estabilidade de repetição. Essa dupla conformação é especialmente importante porque o corpus preserva sinais claros de fragilidade anterior: uma rodada substituída de ClickHouse com falhas massivas, rodadas de validação de Materialize com erros SQL e rodada canônica de Druid ainda com falhas em parte das superfícies.

Nessa família, o objetivo principal não é reinventar a metodologia. É confirmar se as trajetórias estáveis finais realmente se sustentam quando executadas novamente. Se ClickHouse repetir a rodada limpa e rápida, o artigo ganha muito em força conclusiva. Se Druid resolver `filtered_entries` e reduzir as falhas iniciais, melhora-se a comparabilidade SQL. Se Materialize mantiver corretude e reduzir volatilidade, sua posição prática sobe. Se Pinot mantiver sua superioridade consultiva e ampliar cadência autoritativa, a interpretação de sua trilha fica ainda mais rica.

## Família de reruns 2: variação controlada de cardinalidade e payload

O corpus atual já mostra que diferentes endpoints carregam custos muito distintos conforme o tamanho e a composição do payload. O próximo passo natural é variar cardinalidade, profundidade de filtros e volume do workspace de modo controlado. Em vez de um único painel padrão, o benchmark pode evoluir para pelo menos três níveis de pressão sobre o estado derivado: leve, intermediário e denso.

No nível leve, o objetivo é observar o comportamento em dashboards com pouca carga de agregação e catálogo. No nível intermediário, preserva-se cenário próximo ao atual. No nível denso, ampliam-se filtros compostos, volume do workspace, amplitude de catálogos e peso dos payloads. Esse desenho mostraria se a vantagem relativa de cada stack é estável ou se ela depende fortemente do tamanho do estado exibido.

## Família de reruns 3: replay e reprocessamento

Uma lacuna importante do corpus atual é a ausência de uma bateria especificamente centrada em replay. Isso é relevante porque o problema arquitetural do relatório não se limita ao steady state; ele inclui a capacidade de reconstruir estado confiável quando a trilha precisa ser reprocessada. Um cenário de replay deveria medir, pelo menos, tempo até health verde, tempo até primeiro snapshot útil, tempo até reconciliação de agregados e estabilidade visual do frontend durante a reidratação.

Esse cenário seria particularmente útil para diferenciar mais claramente paradigmas hot-analytic e incremental-streaming. Em teoria, sistemas incrementais podem capturar parte dessa vantagem conceitual com mais nitidez quando o problema deixa de ser consulta pura em estado aquecido e passa a ser reconstrução controlada de estado derivado.

## Família de reruns 4: correções tardias e retratações

Outra extensão indispensável é introduzir eventos que gerem retratações semânticas reais: cancelamentos, devoluções, estornos, ajustes de classificação e compensações contábeis retroativas. O corpus presente preserva corretude mínima, mas ainda não força o sistema a lidar de maneira intensa com a negativação incremental de contribuições anteriores. Esse é precisamente o tipo de situação em que a teoria de incremental view maintenance fica mais interessante e em que a robustez do dashboard pode ser testada além do monotônico simples.

Em termos de artigo, um cenário assim permitiria responder perguntas que hoje ainda permanecem abertas. O custo de snapshots autoritativos cresce muito quando o domínio exige retratação? As stacks hot-analytic perdem mais terreno porque precisam recompor mais estado na periferia? Materialize ganha vantagem prática quando a complexidade temporal deixa de ser periférica e passa a ser central? Essas perguntas justificam por si sós uma segunda grande fase do benchmark.

## Família de reruns 5: robustez de observabilidade e completude de debug

O programa experimental futuro deveria tratar a completude dos snapshots finais de debug como critério explícito de qualidade da rodada. Uma bateria em que a stack responde rápido, mas não deixa rastro final suficientemente auditável, é cientificamente mais fraca. Por isso, reruns focados em observabilidade devem existir como classe própria. Eles podem verificar, por exemplo, se todos os endpoints de debug permanecem consistentes ao fim da rodada, se os payloads finais preservam campos críticos e se a camada de health timeline consegue reconstruir fielmente transições de readiness.

Esse tipo de cenário é menos glamoroso do que p95, mas extremamente importante. Em projetos reais, o backend que a equipe consegue explicar costuma ser mais valioso do que o backend que apenas produz bons números em uma execução afortunada.

## Família de cenários 6: degradação parcial e falhas localizadas

Uma direção adicional consiste em introduzir degradações localizadas: atraso deliberado em parte da ingestão, indisponibilidade temporária do broker, lentidão controlada de API, perda momentânea de conexão do gateway ou crescimento abrupto de backlog. O interesse aqui não é produzir caos arbitrário, mas observar como cada paradigma se comporta quando a trilha deixa de operar em regime perfeitamente estável. Sistemas gerenciais reais convivem com essas situações com frequência suficiente para que um benchmark de sistema completo não as trate como irrelevantes.

Esse bloco de experimentos também aproxima o trabalho de engenharia resiliente. Ele ajuda a responder se um backend degrada de modo legível, se o painel continua útil sob sofrimento parcial e se a diferença entre “rápido” e “robusto” cresce quando o sistema é pressionado fora da linha ideal.

## Família de cenários 7: evolução do papel do frontend

Como o corpus já mostrou que o frontend é parte constitutiva do fenômeno observado, uma agenda madura de benchmark deve incluir cenários em que políticas de frontend sejam alteradas explicitamente. Isso inclui variar critérios de estado significativo, frequência de reconciliação, agressividade de projeção local, estratégia de fallback e política de tratamento de snapshot vazio ou atrasado. O objetivo é medir quanto da vantagem de cada stack está no backend e quanto está no modo como o frontend negocia com ele a temporalidade do estado exibido.

Pinot é o caso mais óbvio para esse tipo de experimento, mas não o único. ClickHouse e Druid também podem revelar sensibilidades relevantes, e Materialize pode mostrar quanto valor incremental de fato migra do cliente para o backend quando a configuração está mais madura.

## Como relatar esses cenários sem perder auditabilidade

À medida que o programa experimental crescer, o artigo precisará continuar fiel ao princípio que justifica sua força atual: cada afirmação importante deve poder ser rastreada a artefatos persistidos. Isso significa que novos cenários não devem ser adicionados se a instrumentação correspondente não estiver preparada. O relatório não precisa relatar tudo ao mesmo tempo; precisa relatar bem o que foi realmente medido.

Uma forma defensável de evoluir a escrita é manter sempre três camadas de evidência. A primeira é a camada canônica, com corpus principal e comparação transversal. A segunda é a camada auxiliar, com rodadas diagnósticas e de validação. A terceira é a camada exploratória, com cenários novos ainda sem massa estatística suficiente para conclusões fortes, mas já úteis para abrir o debate técnico. Essa estratificação evita tanto a simplificação excessiva quanto o acúmulo caótico de dados sem hierarquia.

## Checklist operacional para reruns canônicos

Como o benchmark depende fortemente de repetibilidade, vale registrar um checklist operacional mais explícito para os reruns de conformação. Primeiro, garantir limpeza completa do ambiente, ausência de resíduos de containers e seleção inequívoca da stack ativa. Segundo, registrar commit, arquivo de ambiente e budgets efetivos antes do início da coleta. Terceiro, validar não apenas health binário, mas readiness suficiente de frontend, API, gateway e endpoints de debug. Quarto, confirmar a produção ativa de eventos e a materialização mínima do ledger antes de entrar na janela principal. Quinto, ao final, capturar integralmente todos os snapshots finais previstos antes do desligamento da stack.

Esse checklist é simples, mas sua explicitação é importante porque o próprio corpus já mostrou o quanto resultados muito diferentes podem surgir de pequenas diferenças na preparação. Documentá-lo no relatório reduz a dependência de memória tácita e aumenta a chance de reruns verdadeiramente comparáveis.

## Estratégia de publicação incremental do corpus futuro

À medida que novas rodadas forem executadas, o relatório pode crescer sem perder clareza se adotar uma estratégia de publicação incremental. O capítulo principal de resultados deve continuar reservando prioridade às rodadas canônicas mais estáveis. As rodadas auxiliares, de validação e de stress, por sua vez, podem ser absorvidas em apêndices e capítulos diagnósticos específicos, com interpretação mais prudente. Isso evita dois extremos indesejáveis: de um lado, um manuscrito curto demais que apaga contexto; de outro, um manuscrito caótico em que toda execução recebe o mesmo peso analítico.

Em termos práticos, essa estratégia significa que o relatório futuro deve continuar crescendo por camadas. Primeiro, consolida-se a bateria central. Depois, adicionam-se famílias de cenário e reruns com sua própria seção interpretativa. Por fim, quando houver massa suficiente, essas novas famílias podem ser promovidas da condição de evidência auxiliar para condição de evidência principal. Essa governança editorial é importante porque o próprio sucesso do benchmark tende a aumentar rapidamente o volume de artefatos disponíveis.

## Fecho do apêndice

O programa de reruns e cenários aqui descrito não é mero apêndice opcional. Ele é a continuação lógica do corpus já produzido. O benchmark atingiu um ponto em que a pergunta deixou de ser se vale a pena comparar paradigmas de serving para dashboards orientados a eventos. Vale. A pergunta agora é como expandir essa comparação sem perder rigor, rastreabilidade e utilidade de engenharia. A resposta proposta por este apêndice é simples: repetir onde houve fragilidade, aprofundar onde a teoria pede pressão adicional e sempre preservar a ligação entre arquitetura, métrica e artefato observável.