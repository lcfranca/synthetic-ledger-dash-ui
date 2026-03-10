# Introdução

## Contextualização do problema

A digitalização da operação empresarial elevou o papel de arquiteturas orientadas a eventos como espinha dorsal de sistemas transacionais, analíticos e observacionais. Em paralelo, a demanda por painéis gerenciais near-real-time tornou-se estrutural: gestores financeiros, comerciais e operacionais já não aceitam visões consolidadas apenas no fechamento de lote ou em janelas longas de polling. O problema, contudo, não se resolve pela simples exposição de eventos ao frontend. A decisão gerencial depende de um estado derivado consultável, semanticamente coerente e visualmente estável.

Essa exigência torna-se ainda mais severa em domínios contábil-financeiros. Um painel pode parecer rápido e, ainda assim, ser tecnicamente inadequado se violar invariantes de dupla entrada, oscilar entre snapshots inconsistentes ou degradar sob replay e reprocessamento. Logo, o desafio não é apenas acelerar consultas. O desafio é reduzir a distância entre o evento canônico de negócio e a disponibilidade de uma representação útil, autoritativa e contabilmente confiável no frontend.

## Problema analítico

O problema científico desta pesquisa consiste em comparar, de forma metodologicamente justa, backends com paradigmas internos distintos para alimentar painéis gerenciais em tempo real por push. Essa comparação precisa reconhecer tensões simultâneas entre throughput, latência percebida, custo operacional, corretude contábil, capacidade de replay, estabilidade sob filtros e proximidade arquitetural entre stream e estado derivado.

Em termos mais precisos, pergunta-se: como avaliar sistemas hot-analytic e incremental-streaming sob um mesmo contrato funcional, sem reduzir a comparação a um teste superficial de latência HTTP ou SQL? A pergunta é relevante porque diferentes tecnologias oferecem respostas arquiteturais distintas ao mesmo problema de serving, e tais respostas afetam desde a topologia da stack até a experiência visual final.

## Premissas de avaliação

A premissa central de avaliação é que sistemas de manutenção incremental de views tendem a reduzir a distância entre evento canônico e snapshot derivado consultável, favorecendo modos autoritativos de convergência visual. Entretanto, essa vantagem potencial vem acompanhada de custos cognitivos, restrições semânticas e desafios operacionais que não aparecem com a mesma intensidade em motores hot-analytic. Em contrapartida, motores analíticos quentes podem preservar excelente desempenho de serving quando o read model já está estabilizado, mas frequentemente exigem coordenação adicional entre API, gateway e frontend para manter coerência perceptual.

## Objetivos

O objetivo geral é estabelecer um benchmark state-of-the-art para avaliar backends capazes de servir painéis contábeis e comerciais near-real-time por push, preservando corretude financeira e convergência visual.

Como objetivos específicos, o trabalho busca:

1. Definir o contrato funcional do caso de uso com foco em ledger canônico, APIs e interface visual.
2. Descrever, implementar e endurecer as trilhas arquiteturais de ClickHouse, Druid, Pinot e Materialize no mesmo repositório experimental.
3. Propor uma taxonomia de métricas que combine latência, corretude, operacionalidade e experiência percebida.
4. Executar rodadas de benchmark reprodutíveis e auditáveis.
5. Interpretar os resultados comparando paradigmas de serving, e não apenas produtos individuais.

## Justificativa

Do ponto de vista industrial, a análise trata de um problema recorrente em plataformas de dados operacionais: como expor indicadores executivos e contábeis quase em tempo real sem transformar o frontend em um mosaico de inconsistências. Do ponto de vista conceitual, o documento articula áreas que costumam aparecer separadas: event sourcing, OLAP quente, streaming relacional, incremental view maintenance e latência percebida em interfaces.

Existe, portanto, uma lacuna entre benchmarks convencionais de banco de dados e a realidade de sistemas gerenciais push-oriented. Este trabalho busca preencher essa lacuna por meio de um protocolo experimental que preserve o sistema completo como unidade de análise.

## Estrutura do relatório

O Capítulo 2 apresenta a fundamentação teórica. O Capítulo 3 discute o estado da arte tecnológico. O Capítulo 4 descreve o modelo do problema e a arquitetura experimental do repositório. O Capítulo 5 formaliza a metodologia de benchmark. O Capítulo 6 registra resultados preliminares concretos já obtidos no ambiente experimental. Por fim, os apêndices consolidam o protocolo de coleta e a especificação canônica dos artefatos.