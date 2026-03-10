# Resultados Comparativos da Bateria Conclusiva

## Objetivo desta seção

Esta seção apresenta a bateria comparativa efetivamente executada para os quatro backends investigados. Todos os números aqui reportados foram extraídos de rodadas reais do cenário `report-conclusion`, consolidadas em `summary.csv` e `round_report.json`, sem interpolação manual e sem substituição por valores exemplificativos.

## Corpus empírico utilizado

As rodadas comparadas compartilharam commit, host e duracao total de coleta, variando apenas o backend ativo.

| Backend | Round ID | Commit | Duracao |
| --- | --- | --- | ---: |
| ClickHouse | `20260309T033332Z__clickhouse__report-conclusion__run-1` | `2211abae82145de28056003773f83d8785fe454e` | 270 s |
| Druid | `20260309T032706Z__druid__report-conclusion__run-1` | `2211abae82145de28056003773f83d8785fe454e` | 270 s |
| Pinot | `20260309T025603Z__pinot__report-conclusion__run-1` | `2211abae82145de28056003773f83d8785fe454e` | 270 s |
| Materialize | `20260309T030326Z__materialize__report-conclusion__run-1` | `2211abae82145de28056003773f83d8785fe454e` | 270 s |

Cada rodada produziu artefatos de API, SQL, websocket, health timeline, recursos computacionais e snapshots finais de debug. A tabela de comparação a seguir sintetiza apenas as métricas derivadas transversais mais diretamente comparáveis entre as quatro stacks.

## Métricas consolidadas comparativas

| Backend | API `summary` p95 (ms) | API `workspace` p95 (ms) | SQL `entries_count` p95 (ms) | SQL `summary_by_role` p95 (ms) | First meaningful (ms) | Snapshot/s | Entries/s | Balance diff | Health transitions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ClickHouse | 58.26 | 255.12 | 4.65 | 7.67 | 104 | 2.3369 | 78.3223 | 0.0 | 0 |
| Druid | 594.39 | 1748.37 | 55.85 | 60.19 | 45 | 2.3070 | 79.3577 | 0.0 | 1 |
| Pinot | 89.07 | 198.71 | 3.04 | 3.32 | 42 | 0.0202 | 78.9367 | 0.0 | 1 |
| Materialize | 2143.40 | 1979.76 | 875.08 | 855.90 | 157 | 2.3353 | 53.4821 | 0.0 | 14 |

## Análise por dimensão observada

### Latência de API

No plano de serving HTTP, ClickHouse apresentou o melhor resultado para o endpoint `summary`, com p95 de 58.26 ms, seguido por Pinot com 89.07 ms. Para o endpoint `workspace`, Pinot obteve o menor p95 observado, 198.71 ms, com ClickHouse em seguida, 255.12 ms. Druid e Materialize exibiram custo substancialmente maior nesse contrato, com p95 de 1748.37 ms e 1979.76 ms, respectivamente.

Essa distribuição sugere que, neste ambiente e neste workload, as stacks orientadas a serving analítico direto preservam vantagem clara na superfície HTTP. A distância entre os dois melhores resultados e os dois piores é grande o suficiente para ser empiricamente relevante mesmo sem tratamento inferencial adicional.

### Latência SQL nativa

No plano SQL, Pinot apresentou os menores p95 para as duas consultas sinteticas comparadas, 3.04 ms em `entries_count` e 3.32 ms em `summary_by_role`. ClickHouse manteve desempenho muito proximo, com 4.65 ms e 7.67 ms, respectivamente. Druid ocupou uma posicao intermediaria, na casa de dezenas de milissegundos. Materialize permaneceu claramente acima das demais stacks, com p95 de 875.08 ms e 855.90 ms.

Do ponto de vista estritamente consultivo, o resultado observado não favorece um paradigma incremental puro como primeira escolha para esse perfil de leitura. A vantagem de Pinot e ClickHouse, contudo, precisa ser interpretada em conjunto com as métricas de convergência visual e estabilidade, e não como argumento isolado de superioridade global.

### Convergência visual e prontidão percebida

As métricas de frontend mostram uma dissociação importante entre custo de consulta e prontidão percebida. Pinot e Druid registraram os menores `frontend_time_to_first_meaningful_state_ms`, 42 ms e 45 ms, respectivamente. ClickHouse permaneceu em 104 ms e Materialize em 157 ms. Entretanto, essa leitura isolada seria enganosa se desconsiderasse `snapshot_rate_per_second`.

Nesse ponto, Druid, ClickHouse e Materialize mantiveram taxas semelhantes de snapshots, aproximadamente 2,3 por segundo. Pinot, por sua vez, exibiu taxa de apenas 0,0202 snapshots por segundo, apesar de excelente desempenho em API e SQL. Em termos metodológicos, esse contraste importa mais do que uma classificação simplista do menor tempo inicial: ele indica que a primeira percepção de prontidão pode ocorrer antes que a atualização autoritativa do painel atinja cadência comparável à das demais stacks.

### Corretude contábil e estabilidade operacional

Em todas as rodadas observadas, `balance_sheet_difference` permaneceu em 0.0. Esse é um resultado central do experimento, pois elimina a hipótese de que ganhos aparentes de latência tenham sido comprados por perda de integridade contábil. Em outras palavras, a comparação se deu sob manutenção da corretude mínima do ledger agregado.

No plano de estabilidade, ClickHouse apresentou `health_transition_total` igual a 0, Druid e Pinot apresentaram 1 transição cada, e Materialize registrou 14 transições. A interpretação mais prudente é que a trilha Materialize permaneceu funcional, mas com maior sensibilidade operacional sob a carga observada no host local. Esse achado é coerente com sua pior posição nas métricas de latência de leitura e não deve ser separado da análise arquitetural.

## Síntese interpretativa

Os dados coletados sustentam quatro afirmações empíricas.

Primeiro, não há dominância universal entre as stacks. ClickHouse liderou a latência de API para `summary`; Pinot liderou SQL e `workspace`; Druid combinou prontidão visual muito baixa com cadência de snapshots comparável à de ClickHouse; Materialize preservou integridade contábil e convergência visual razoável, mas ao custo de maior latência e maior instabilidade.

Segundo, a camada de experiência percebida não pode ser reduzida à latência SQL nativa. Druid ilustra isso de modo eloquente: embora seu `workspace` p95 tenha permanecido alto, 1748.37 ms, o frontend alcançou estado útil em 45 ms e manteve 2.307 snapshots por segundo. Materialize aponta na mesma direção, ainda que com custos mais severos. Isso reforça a tese de que, para dashboards near-real-time, o sistema de projeção e distribuição importa tanto quanto o mecanismo de consulta subjacente.

Terceiro, a taxa de snapshots do Pinot relativiza a excelência das suas leituras HTTP e SQL. A stack foi extremamente rápida na superfície consultiva, mas o acoplamento entre evento e painel autoritativo mostrou cadência muito inferior nesta configuração observada. Portanto, qualquer conclusão favorável a Pinot deve ser explicitamente condicionada ao requisito dominante da aplicação.

Quarto, a corretude contábil foi preservada em todos os cenários observados. Esse fato melhora a qualidade epistêmica da comparação, pois impede que uma stack seja beneficiada por relaxamento semântico não declarado.

## Limites desta evidência

Esta seção consolida dados reais, mas não elimina as limitações do experimento. Cada backend foi representado por uma rodada conclusiva no mesmo host local, o que é suficiente para análise comparativa auditável, mas insuficiente para inferência estatística forte. Persistem ameaças conhecidas: jitter do WSL2, efeito de aquecimento residual, particularidades de configuração local de cada stack e ausência de repetições suficientes para estimar variância inter-rodada com robustez.

Em consequência, as conclusões a seguir devem ser lidas como afirmações empíricas circunscritas ao corpus coletado, e não como leis gerais sobre os produtos avaliados.