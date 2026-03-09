# Introducao

## Contextualizacao do problema

A digitalizacao da operacao empresarial elevou o papel de arquiteturas orientadas a eventos como espinha dorsal de sistemas transacionais, analiticos e observacionais. Em paralelo, a demanda por paineis gerenciais near-real-time tornou-se estrutural: gestores financeiros, comerciais e operacionais nao aceitam mais visoes consolidadas apenas no fechamento de lote ou em janelas longas de polling. O problema, contudo, nao se resolve pela simples exposicao de eventos ao frontend. A decisao gerencial depende de um estado derivado consultavel, semanticamente coerente e visualmente estavel.

Essa exigencia se torna mais severa em dominios contabil-financeiros. Um painel pode parecer rapido e, ainda assim, ser tecnicamente inadequado se violar invariantes de dupla entrada, oscilar entre snapshots inconsistentes ou degradar sob replay e reprocessamento. Logo, o desafio nao e apenas acelerar consultas. O desafio e reduzir a distancia entre o evento canonico de negocio e a disponibilidade de uma representacao util, autoritativa e contabilmente confiavel no frontend.

## Problema analitico

O problema cientifico desta pesquisa consiste em comparar, de forma metodologicamente justa, backends com paradigmas internos distintos para alimentar paineis gerenciais em tempo real por push. Essa comparacao precisa reconhecer tensoes simultaneas entre throughput, latencia percebida, custo operacional, corretude contabil, capacidade de replay, estabilidade sob filtros e proximidade arquitetural entre stream e estado derivado.

Em termos mais precisos, pergunta-se: como avaliar sistemas hot-analytic e incremental-streaming sob um mesmo contrato funcional, sem reduzir a comparacao a um teste superficial de latencia HTTP ou SQL? A pergunta e relevante porque diferentes tecnologias oferecem respostas arquiteturais distintas ao mesmo problema de serving, e tais respostas afetam desde a topologia da stack ate a experiencia visual final.

## Premissas de avaliacao

A premissa central de avaliacao e que sistemas de manutencao incremental de views tendem a reduzir a distancia entre evento canonico e snapshot derivado consultavel, favorecendo modos autoritativos de convergencia visual. Entretanto, essa vantagem potencial vem acompanhada de custos cognitivos, restricoes semanticas e desafios operacionais que nao aparecem com a mesma intensidade em motores hot-analytic. Em contrapartida, motores analiticos quentes podem preservar excelente desempenho de serving quando o read model ja esta estabilizado, mas frequentemente exigem coordenacao adicional entre API, gateway e frontend para manter coerencia perceptual.

## Objetivos

O objetivo geral e estabelecer um benchmark state-of-the-art para avaliar backends capazes de servir paineis contabeis e comerciais near-real-time por push, preservando corretude financeira e convergencia visual.

Como objetivos especificos, o trabalho busca:

1. Definir o contrato funcional do caso de uso com foco em ledger canonico, APIs e interface visual.
2. Descrever, implementar e endurecer as trilhas arquiteturais de ClickHouse, Druid, Pinot e Materialize no mesmo repositorio experimental.
3. Propor uma taxonomia de metricas que combine latencia, corretude, operacionalidade e experiencia percebida.
4. Executar rodadas de benchmark reprodutiveis e auditaveis.
5. Interpretar os resultados comparando paradigmas de serving, e nao apenas produtos individuais.

## Justificativa

Do ponto de vista industrial, a analise trata de um problema recorrente em plataformas de dados operacionais: como expor indicadores executivos e contabeis quase em tempo real sem transformar o frontend em um mosaico de inconsistencias. Do ponto de vista conceitual, o documento articula areas que costumam aparecer separadas: event sourcing, OLAP quente, streaming relacional, incremental view maintenance e latencia percebida em interfaces.

Existe, portanto, uma lacuna entre benchmarks convencionais de banco de dados e a realidade de sistemas gerenciais push-oriented. Este trabalho busca preencher essa lacuna por meio de um protocolo experimental que preserve o sistema completo como unidade de analise.

## Estrutura do relatorio

O Capitulo 2 apresenta a fundamentacao teorica. O Capitulo 3 discute o estado da arte tecnologico. O Capitulo 4 descreve o modelo do problema e a arquitetura experimental do repositorio. O Capitulo 5 formaliza a metodologia de benchmark. O Capitulo 6 registra resultados preliminares concretos ja obtidos no ambiente experimental. Por fim, os apendices consolidam o protocolo de coleta e a especificacao canonica dos artefatos.