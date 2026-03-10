# Apêndice C - Dossiês Operacionais por Backend

## Finalidade dos dossiês

Este apêndice reúne uma leitura operacional pormenorizada de cada trilha do benchmark. Seu objetivo não é repetir as tabelas do corpo principal, mas registrar, em linguagem de engenharia, os elementos que tipicamente ficam implícitos quando um relatório é condensado demais: pressupostos de integração, pontos de fragilidade, consequências das escolhas de modelagem e indícios de maturidade ou imaturidade operacional encontrados ao longo da coleta. Em um documento mais curto, tais observações tenderiam a desaparecer. Aqui, elas são preservadas porque ajudam a transformar o corpus em memória técnica reutilizável.

## Dossiê ClickHouse

### Papel da stack dentro do repositório

ClickHouse ocupa, no repositório, a posição de motor colunar de leitura quente alimentado por uma trilha canônica já semanticamente resolvida a montante. O produtor gera eventos de negócio; o storage writer realiza a derivação contábil; o backend recebe entries prontas para serving; a API especializada reorganiza o acesso em contratos adequados ao dashboard; o gateway harmoniza a atualização com a experiência visual. Esse arranjo permite que ClickHouse seja medido em um regime próximo daquilo em que costuma ser mais forte: baixa latência de leitura sobre estruturas tabulares quentes, com forte apoio da aplicação periférica para gerir reconciliação e continuidade de interface.

### O que a stack parece fazer muito bem

Os artefatos sugerem que ClickHouse foi particularmente competente em resumos e leituras recorrentes de painel. O bom desempenho do endpoint `summary` e a posição competitiva em `workspace` e consultas SQL reforçam a hipótese de que o read model foi bem alinhado ao padrão de agregações do domínio. Esse alinhamento é importante porque afasta a interpretação simplista de que “o banco é rápido por natureza”. O banco foi rápido porque havia combinação entre sua estrutura interna e a forma como a camada de aplicação o explorou.

Outra virtude relevante é a convivência relativamente saudável entre consulta rápida e cadência autoritativa de snapshots. Em muitos cenários, motores hot-analytic correm o risco de ficar excelentes em consulta e medianos em reconvergência visual. A trilha ClickHouse mostrou que isso não é inevitável quando o gateway está bem desenhado e quando o frontend não depende de um único mecanismo para parecer vivo.

### O que a stack exige da engenharia

A exigência principal da trilha ClickHouse está em outro lugar: ela pressupõe uma boa separação de responsabilidades. Se o writer canônico degradar, se a API errar o desenho do read model, se o gateway perder disciplina de ressincronização ou se o frontend for permissivo demais com estados transitórios, a boa performance do banco deixa de ser suficiente. Em outras palavras, ClickHouse recompensa engenharia periférica disciplinada. Não é uma solução que magicamente internaliza a semântica do sistema inteiro.

Também é importante notar que a tentativa substituída com falhas SQL massivas é parte do dossiê. Ela mostra que a stack pode degradar violentamente quando alguma camada do preparo experimental falha. Portanto, a imagem correta de ClickHouse no corpus não é a de backend infalível, e sim a de backend muito competitivo quando a trilha ao redor já foi devidamente estabilizada.

### Interpretação prática

Para equipes que já dispõem de pipeline canônico confiável, possuem boa disciplina de modelagem tabular e valorizam forte desempenho de leitura com custo operacional relativamente previsível, ClickHouse emerge como escolha extremamente séria. A principal cautela é não confundir velocidade consultiva com suficiência arquitetural. O backend não elimina o trabalho de reconciliação; ele funciona muito bem quando esse trabalho já foi corretamente redistribuído pelas demais camadas do sistema.

## Dossiê Druid

### Papel da stack dentro do repositório

Druid aparece, no repositório, como a trilha em que a topologia distribuída pesa mais explicitamente sobre o comportamento observado. Broker, router, middlemanager, coordinator, overlord, metadata store e serviços auxiliares constituem uma cadeia de prontidão mais longa e mais sensível do que a das demais stacks. Isso torna Druid particularmente ilustrativo para um ponto metodológico essencial: em certos backends, a unidade real do benchmark é a topologia distribuída inteira.

### O que a stack parece fazer muito bem

Apesar do custo de aquecimento e dos episódios iniciais de indisponibilidade parcial, Druid mostrou desempenho notável na dimensão de experiência percebida. O frontend atinge estado útil cedo e mantém cadência de snapshots compatível com ClickHouse e Materialize. Essa propriedade é relevante porque prova que o backend pode continuar interessante mesmo quando não lidera as superfícies consultivas puras. Em cenários em que o dashboard precisa “voltar a respirar” rapidamente após o arranque, essa característica pode ser mais importante do que a diferença entre dezenas ou centenas de milissegundos em uma query específica.

### Fragilidades operacionais registradas

O corpus também deixa claras as fragilidades. Os 503 iniciais de API, a transição de warming up, a dependência entre ingestão e serving e a falha da consulta `filtered_entries` demonstram que a trilha ainda exige cuidados importantes para garantir comparabilidade total entre todas as superfícies. Em ambientes reais, esse tipo de sensibilidade não desaparece por ser chamado de “questão operacional”. Ele consome tempo de engenharia, amplia o custo de rerun e reduz a previsibilidade do resultado.

### Interpretação prática

Druid parece adequado para equipes que aceitam topologia mais exigente em troca de uma combinação interessante entre análise quente, ingestão orientada a eventos e boa experiência inicial do painel. O backend não aparece como solução minimalista nem como resposta universal, mas como alternativa tecnicamente respeitável quando se deseja boa atualização percebida e quando se tolera uma infraestrutura mais complexa para chegar a esse resultado.

## Dossiê Pinot

### Papel da stack dentro do repositório

Pinot ocupa o lugar da stack mais consultivamente agressiva do corpus. Sua integração no repositório favorece um modo de operação em que o backend serve consultas muito rápidas e o frontend participa ativamente da continuidade visual. Nessa arquitetura, o banco não precisa ser o único mecanismo de sensação de tempo real; ele atua como âncora rápida de leitura autoritativa, enquanto o cliente administra parte da fluidez local.

### O que a stack parece fazer muito bem

O corpus é inequívoco quanto ao seu maior mérito: Pinot venceu as principais consultas SQL e foi excelente em parte importante da superfície HTTP. Isso o torna particularmente atraente para workloads de serving interativo, filtros frequentes e respostas rápidas em painéis operacionais com forte orientação a exploração. O backend também parece confortável em consultas sintéticas recorrentes de baixa cardinalidade, o que reforça sua vocação de OLAP operacional responsivo.

### O ponto de tensão da trilha

O problema central não está na consulta, mas na distância entre consulta e reconciliação autoritativa. A taxa de snapshots por segundo observada no corpus final é muito inferior à das demais stacks. Isso cria uma assimetria que o relatório não pode ignorar. O backend parece ótimo para responder; a questão em aberto é o quanto essa excelência se transforma em painel plenamente autoritativo com a mesma frequência. Some-se a isso a cobertura limitada dos snapshots finais de debug, e aparece um tipo de custo menos óbvio: custo de auditabilidade.

### Interpretação prática

Pinot é forte quando a organização aceita colocar mais inteligência na borda e deseja maximizar performance de serving direto. Para equipes que tratam o frontend como ator semântico de primeira linha e possuem boa disciplina de reconciliação, isso pode ser uma vantagem. Para equipes que desejam maior centralização da autoridade do painel na própria trilha backend-gateway, a distância entre leitura rápida e atualização autoritativa precisa ser observada com muito cuidado.

## Dossiê Materialize

### Papel da stack dentro do repositório

Materialize é o backend que mais se aproxima do ideal teórico de manutenção incremental do próprio estado derivado. Sua presença no repositório cumpre função quase metodológica: impedir que o benchmark se reduza a comparação entre três variantes de serving quente e, ao mesmo tempo, testar se uma arquitetura incremental mais “pura” consegue transferir essa elegância conceitual para o plano operacional.

### O que a stack parece fazer de forma singular

A singularidade de Materialize não está em liderar p95, mas em oferecer um caminho plausível para desacoplar utilidade inicial do painel e custo integral da consulta. O corpus sugere que o frontend consegue tornar-se útil relativamente cedo mesmo quando as consultas nativas permanecem caras. Isso é uma pista importante de valor arquitetural, porque aponta para uma forma diferente de organizar a experiência near-real-time: menos dependente de serving quente puro e mais dependente de um estado incrementalmente sustentado próximo ao stream.

### O que limita a maturidade prática da trilha

Ao mesmo tempo, a rodada canônica final registra alta volatilidade de health e cobertura muito baixa nos snapshots finais de debug. Isso mostra que a trilha incremental ainda não estava operando com a mesma estabilidade prática das melhores execuções de ClickHouse ou Pinot. Há aqui uma distinção crucial entre potência conceitual e prontidão de engenharia. Materialize parece dizer algo importante sobre a forma correta de modelar o problema, mas ainda não entrega, neste corpus, a mesma robustez operacional da solução consultiva mais madura.

### Interpretação prática

Materialize é a stack que mais interessa quando o objetivo é empurrar o repositório para um debate tecnicamente mais sofisticado sobre incremental view maintenance, temporalidade e autoridade do snapshot. É menos convincente, por ora, como escolha imediata para o workload já medido. Em termos de pesquisa aplicada, isso é extremamente valioso: a tecnologia obriga o experimento a avançar, mesmo quando não “vence” a bateria final.

## Síntese dos dossiês

Lidos em conjunto, os quatro dossiês revelam que o repositório abriga não apenas alternativas de infraestrutura, mas quatro filosofias de aproximação entre evento, estado e visualização. ClickHouse privilegia a excelência do serving quente bem integrado. Druid enfatiza a potência de uma topologia analítica de eventos ao preço de maior exigência operacional. Pinot maximiza a consulta direta com forte protagonismo da borda. Materialize internaliza mais profundamente a lógica incremental, ao custo de maturidade prática ainda incompleta. Para fins de engenharia, essa síntese vale mais do que qualquer ranking isolado.