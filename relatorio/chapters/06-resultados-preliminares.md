# Resultados Comparativos da Bateria Conclusiva

## 6.1 Objetivo desta secao

Esta secao apresenta a bateria comparativa efetivamente executada para os quatro backends investigados. Todos os numeros aqui reportados foram extraidos de rodadas reais do cenario `report-conclusion`, consolidadas em `summary.csv` e `round_report.json`, sem interpolacao manual e sem substituicao por valores exemplificativos.

## 6.2 Corpus empirico utilizado

As rodadas comparadas compartilharam commit, host e duracao total de coleta, variando apenas o backend ativo.

| Backend | Round ID | Commit | Duracao |
| --- | --- | --- | ---: |
| ClickHouse | `20260309T033332Z__clickhouse__report-conclusion__run-1` | `2211abae82145de28056003773f83d8785fe454e` | 270 s |
| Druid | `20260309T032706Z__druid__report-conclusion__run-1` | `2211abae82145de28056003773f83d8785fe454e` | 270 s |
| Pinot | `20260309T025603Z__pinot__report-conclusion__run-1` | `2211abae82145de28056003773f83d8785fe454e` | 270 s |
| Materialize | `20260309T030326Z__materialize__report-conclusion__run-1` | `2211abae82145de28056003773f83d8785fe454e` | 270 s |

Cada rodada produziu artefatos de API, SQL, websocket, health timeline, recursos computacionais e snapshots finais de debug. A tabela de comparacao a seguir sintetiza apenas as metricas derivadas transversais mais diretamente comparaveis entre as quatro stacks.

## 6.3 Metricas consolidadas comparativas

| Backend | API `summary` p95 (ms) | API `workspace` p95 (ms) | SQL `entries_count` p95 (ms) | SQL `summary_by_role` p95 (ms) | First meaningful (ms) | Snapshot/s | Entries/s | Balance diff | Health transitions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ClickHouse | 58.26 | 255.12 | 4.65 | 7.67 | 104 | 2.3369 | 78.3223 | 0.0 | 0 |
| Druid | 594.39 | 1748.37 | 55.85 | 60.19 | 45 | 2.3070 | 79.3577 | 0.0 | 1 |
| Pinot | 89.07 | 198.71 | 3.04 | 3.32 | 42 | 0.0202 | 78.9367 | 0.0 | 1 |
| Materialize | 2143.40 | 1979.76 | 875.08 | 855.90 | 157 | 2.3353 | 53.4821 | 0.0 | 14 |

## 6.4 Analise por dimensao observada

### 6.4.1 Latencia de API

No plano de serving HTTP, ClickHouse apresentou o melhor resultado para o endpoint `summary`, com p95 de 58.26 ms, seguido por Pinot com 89.07 ms. Para o endpoint `workspace`, Pinot obteve o menor p95 observado, 198.71 ms, com ClickHouse em seguida, 255.12 ms. Druid e Materialize exibiram custo substancialmente maior nesse contrato, com p95 de 1748.37 ms e 1979.76 ms, respectivamente.

Essa distribuicao sugere que, neste ambiente e neste workload, as stacks orientadas a serving analitico direto preservam vantagem clara na superficie HTTP. A distancia entre os dois melhores resultados e os dois piores e grande o suficiente para ser empiricamente relevante mesmo sem tratamento inferencial adicional.

### 6.4.2 Latencia SQL nativa

No plano SQL, Pinot apresentou os menores p95 para as duas consultas sinteticas comparadas, 3.04 ms em `entries_count` e 3.32 ms em `summary_by_role`. ClickHouse manteve desempenho muito proximo, com 4.65 ms e 7.67 ms, respectivamente. Druid ocupou uma posicao intermediaria, na casa de dezenas de milissegundos. Materialize permaneceu claramente acima das demais stacks, com p95 de 875.08 ms e 855.90 ms.

Do ponto de vista estritamente consultivo, o resultado observado nao favorece um paradigma incremental puro como primeira escolha para esse perfil de leitura. A vantagem de Pinot e ClickHouse, contudo, precisa ser interpretada em conjunto com as metricas de convergencia visual e estabilidade, e nao como argumento isolado de superioridade global.

### 6.4.3 Convergencia visual e prontidao percebida

As metricas de frontend mostram uma dissociacao importante entre custo de consulta e prontidao percebida. Pinot e Druid registraram os menores `frontend_time_to_first_meaningful_state_ms`, 42 ms e 45 ms, respectivamente. ClickHouse permaneceu em 104 ms e Materialize em 157 ms. Entretanto, essa leitura isolada seria enganosa se desconsiderasse `snapshot_rate_per_second`.

Nesse ponto, Druid, ClickHouse e Materialize mantiveram taxas semelhantes de snapshots, aproximadamente 2.3 por segundo. Pinot, por sua vez, exibiu taxa de apenas 0.0202 snapshots por segundo, apesar de excelente desempenho em API e SQL. Em termos metodologicos, esse contraste importa mais do que uma classificacao simplista do menor tempo inicial: ele indica que a primeira percepcao de prontidao pode ocorrer antes que a atualizacao autoritativa do painel atinja cadencia comparavel a das demais stacks.

### 6.4.4 Corretude contabil e estabilidade operacional

Em todas as rodadas observadas, `balance_sheet_difference` permaneceu em 0.0. Esse e um resultado central do experimento, pois elimina a hipotese de que ganhos aparentes de latencia tenham sido comprados por perda de integridade contabil. Em outras palavras, a comparacao se deu sob manutencao da corretude minima do ledger agregado.

No plano de estabilidade, ClickHouse apresentou `health_transition_total` igual a 0, Druid e Pinot apresentaram 1 transicao cada, e Materialize registrou 14 transicoes. A interpretacao mais prudente e que a trilha Materialize permaneceu funcional, mas com maior sensibilidade operacional sob a carga observada no host local. Esse achado e coerente com sua pior posicao nas metricas de latencia de leitura e nao deve ser separado da analise arquitetural.

## 6.5 Sintese interpretativa

Os dados coletados sustentam quatro afirmacoes empiricas.

Primeiro, nao ha dominancia universal entre as stacks. ClickHouse liderou a latencia de API para `summary`; Pinot liderou SQL e `workspace`; Druid combinou prontidao visual muito baixa com cadence de snapshots comparavel a ClickHouse; Materialize preservou integridade contabil e convergencia visual razoavel, mas ao custo de maior latencia e maior instabilidade.

Segundo, a camada de experiencia percebida nao pode ser reduzida a latencia SQL nativa. Druid ilustra isso de modo eloquente: embora seu `workspace` p95 tenha permanecido alto, 1748.37 ms, o frontend alcancou estado util em 45 ms e manteve 2.307 snapshots por segundo. Materialize aponta na mesma direcao, ainda que com custos mais severos. Isso reforca a tese de que, para dashboards near-real-time, o sistema de projecao e distribuicao importa tanto quanto o mecanismo de consulta subjacente.

Terceiro, a taxa de snapshots do Pinot relativiza a excelencia das suas leituras HTTP e SQL. A stack foi extremamente rapida na superficie consultiva, mas o acoplamento entre evento e painel autoritativo mostrou cadencia muito inferior nesta configuracao observada. Portanto, qualquer conclusao favoravel a Pinot deve ser explicitamente condicionada ao requisito dominante da aplicacao.

Quarto, a corretude contabil foi preservada em todos os cenarios observados. Esse fato melhora a qualidade epistemica da comparacao, pois impede que uma stack seja beneficiada por relaxamento semantico nao declarado.

## 6.6 Limites desta evidencia

Esta secao consolida dados reais, mas nao elimina as limitacoes do experimento. Cada backend foi representado por uma rodada conclusiva no mesmo host local, o que e suficiente para analise comparativa auditavel, mas insuficiente para inferencia estatistica forte. Persistem ameacas conhecidas: jitter do WSL2, efeito de aquecimento residual, particularidades de configuracao local de cada stack e ausencia de repeticoes suficientes para estimar variancia inter-rodada com robustez.

Em consequencia, as conclusoes a seguir devem ser lidas como afirmacoes empiricas circunscritas ao corpus coletado, e nao como leis gerais sobre os produtos avaliados.