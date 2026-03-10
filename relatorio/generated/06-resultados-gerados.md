# Resultados Comparativos Derivados dos Artefatos

Este capítulo é gerado automaticamente a partir dos artefatos em `artifacts/benchmark`. As tabelas abaixo não são mantidas manualmente: elas são reconstruídas no build do relatório, preservando rastreabilidade entre corpus empírico, tabelas e interpretação textual.

## Corpus, seleção canônica e rastreabilidade

A seleção canônica utiliza, para cada backend, a rodada mais recente do cenário `report-conclusion`. Rodadas auxiliares e tentativas substituídas permanecem documentadas para análise diagnóstica e para suporte a reruns de conformação.

\begin{landscape}
\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{1.9cm}L{1.8cm}L{2.4cm}L{5.2cm}L{2.4cm}rrrr}
\caption{Inventário completo das rodadas disponíveis no corpus de benchmark.}\label{tab:corpus-inventory}\\
\toprule
Classe & Backend & Cenário & Round ID & Início & Duração (s) & Erros & Transições & Dif. balanço \\\midrule
\endfirsthead
\toprule
Classe & Backend & Cenário & Round ID & Início & Duração (s) & Erros & Transições & Dif. balanço \\\midrule
\endhead
validação & materialize & validation-smoke & \nolinkurl{20260309T020307Z__materialize__validation-smoke__run-2} & \nolinkurl{2026-03-09T02:03:07Z} & 90 & 48 & 5 & 0,00 \\
validação & materialize & validation-sql & \nolinkurl{20260309T020746Z__materialize__validation-sql__run-3} & \nolinkurl{2026-03-09T02:07:46Z} & 90 & 49 & 7 & 0,00 \\
validação & materialize & validation-ready & \nolinkurl{20260309T021556Z__materialize__validation-ready__run-4} & \nolinkurl{2026-03-09T02:15:56Z} & 90 & 0 & 4 & 0,00 \\
substituída & clickhouse & report-conclusion & \nolinkurl{20260309T024926Z__clickhouse__report-conclusion__run-1} & \nolinkurl{2026-03-09T02:49:26Z} & 270 & 99217 & 0 & 0,00 \\
canônica & pinot & report-conclusion & \nolinkurl{20260309T025603Z__pinot__report-conclusion__run-1} & \nolinkurl{2026-03-09T02:56:03Z} & 270 & 0 & 1 & 0,00 \\
canônica & materialize & report-conclusion & \nolinkurl{20260309T030326Z__materialize__report-conclusion__run-1} & \nolinkurl{2026-03-09T03:03:26Z} & 270 & 0 & 14 & 0,00 \\
canônica & druid & report-conclusion & \nolinkurl{20260309T032706Z__druid__report-conclusion__run-1} & \nolinkurl{2026-03-09T03:27:06Z} & 270 & 2385 & 1 & 0,00 \\
canônica & clickhouse & report-conclusion & \nolinkurl{20260309T033332Z__clickhouse__report-conclusion__run-1} & \nolinkurl{2026-03-09T03:33:32Z} & 270 & 0 & 0 & 0,00 \\
\bottomrule
\end{longtable}
\normalsize
\end{landscape}



\begin{landscape}
\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{1.8cm}L{7.0cm}rrrrr}
\caption{Orçamento de fases das rodadas canônicas utilizadas na comparação principal.}\label{tab:phase-budgets}\\
\toprule
Backend & Round ID & Bootstrap (s) & Readiness (s) & Warm-up (s) & Segmento (s) & Duração (s) \\\midrule
\endfirsthead
\toprule
Backend & Round ID & Bootstrap (s) & Readiness (s) & Warm-up (s) & Segmento (s) & Duração (s) \\\midrule
\endhead
clickhouse & \nolinkurl{20260309T033332Z__clickhouse__report-conclusion__run-1} & 180 & 240 & 10 & 90 & 270 \\
druid & \nolinkurl{20260309T032706Z__druid__report-conclusion__run-1} & 180 & 240 & 10 & 90 & 270 \\
materialize & \nolinkurl{20260309T030326Z__materialize__report-conclusion__run-1} & 180 & 240 & 10 & 90 & 270 \\
pinot & \nolinkurl{20260309T025603Z__pinot__report-conclusion__run-1} & 180 & 240 & 10 & 90 & 270 \\
\bottomrule
\end{longtable}
\normalsize
\end{landscape}



## Latência HTTP e SQL

\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{1.8cm}L{2.3cm}rrrrrrrrr}
\caption{Latência HTTP por endpoint nas rodadas canônicas.}\label{tab:api-latency}\\
\toprule
Backend & Endpoint & Amostras & Sucesso & Erros & Média ms & p50 ms & p95 ms & p99 ms & Máx ms & Bytes médios \\\midrule
\endfirsthead
\toprule
Backend & Endpoint & Amostras & Sucesso & Erros & Média ms & p50 ms & p95 ms & p99 ms & Máx ms & Bytes médios \\\midrule
\endhead
clickhouse & \nolinkurl{health} & 355 & 355 & 0 & 2,04 & 1,11 & 1,73 & 36,16 & 41,58 & 38,00 \\
clickhouse & \nolinkurl{summary} & 355 & 355 & 0 & 33,27 & 26,94 & 58,26 & 69,35 & 109,56 & 48618,08 \\
clickhouse & \nolinkurl{workspace} & 355 & 355 & 0 & 161,81 & 154,94 & 255,12 & 322,38 & 376,13 & 340973,17 \\
clickhouse & \nolinkurl{entries} & 355 & 355 & 0 & 40,86 & 26,88 & 77,82 & 85,72 & 97,91 & 79332,68 \\
clickhouse & \nolinkurl{filter_search} & 354 & 354 & 0 & 11,16 & 6,96 & 47,34 & 51,51 & 53,81 & 264,00 \\
druid & \nolinkurl{health} & 54 & 54 & 0 & 84,08 & 64,04 & 129,56 & 969,61 & 1366,39 & 160,30 \\
druid & \nolinkurl{summary} & 54 & 50 & 4 & 296,30 & 225,79 & 594,39 & 1001,78 & 1190,42 & 48906,90 \\
druid & \nolinkurl{workspace} & 54 & 50 & 4 & 983,25 & 883,44 & 1748,37 & 2613,24 & 3099,00 & 343701,60 \\
druid & \nolinkurl{entries} & 53 & 50 & 3 & 263,41 & 122,84 & 284,10 & 3064,67 & 5712,79 & 79605,76 \\
druid & \nolinkurl{filter_search} & 53 & 53 & 0 & 1,76 & 1,42 & 3,45 & 6,79 & 8,85 & 77,00 \\
materialize & \nolinkurl{health} & 15 & 15 & 0 & 744,45 & 972,36 & 1029,08 & 1044,73 & 1048,65 & 279,00 \\
materialize & \nolinkurl{summary} & 15 & 15 & 0 & 1475,43 & 1087,59 & 2143,40 & 2144,74 & 2145,08 & 48852,53 \\
materialize & \nolinkurl{workspace} & 15 & 15 & 0 & 1920,18 & 1948,21 & 1979,76 & 1997,42 & 2001,83 & 344905,60 \\
materialize & \nolinkurl{entries} & 14 & 14 & 0 & 1097,86 & 1083,42 & 1245,35 & 1276,27 & 1284,00 & 79912,43 \\
materialize & \nolinkurl{filter_search} & 14 & 14 & 0 & 899,21 & 906,26 & 1007,73 & 1028,55 & 1033,75 & 265,00 \\
pinot & \nolinkurl{health} & 435 & 435 & 0 & 1,56 & 0,90 & 1,52 & 36,65 & 48,59 & 33,00 \\
pinot & \nolinkurl{summary} & 435 & 435 & 0 & 41,73 & 26,33 & 89,07 & 102,76 & 1135,61 & 36139,39 \\
pinot & \nolinkurl{workspace} & 435 & 435 & 0 & 125,27 & 109,93 & 198,71 & 288,32 & 568,79 & 256318,08 \\
pinot & \nolinkurl{entries} & 434 & 434 & 0 & 32,78 & 18,50 & 86,16 & 101,12 & 157,12 & 58733,06 \\
pinot & \nolinkurl{filter_search} & 434 & 434 & 0 & 2,46 & 1,39 & 2,13 & 41,91 & 46,84 & 77,00 \\
\bottomrule
\end{longtable}
\normalsize



\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{1.8cm}L{2.9cm}rrrrrrrrr}
\caption{Latência SQL por consulta sintética nas rodadas canônicas.}\label{tab:sql-latency}\\
\toprule
Backend & Consulta & Amostras & Sucesso & Erros & Linhas médias & Média ms & p50 ms & p95 ms & p99 ms & Máx ms \\\midrule
\endfirsthead
\toprule
Backend & Consulta & Amostras & Sucesso & Erros & Linhas médias & Média ms & p50 ms & p95 ms & p99 ms & Máx ms \\\midrule
\endhead
clickhouse & \nolinkurl{entries_count} & 6573 & 6573 & 0 & 1,00 & 3,22 & 2,82 & 4,65 & 10,29 & 61,45 \\
clickhouse & \nolinkurl{summary_by_role} & 6573 & 6573 & 0 & 14,00 & 4,91 & 4,20 & 7,67 & 16,11 & 146,97 \\
clickhouse & \nolinkurl{filtered_entries} & 6573 & 6573 & 0 & 50,00 & 5,54 & 4,88 & 8,60 & 17,34 & 61,99 \\
druid & \nolinkurl{entries_count} & 2375 & 2375 & 0 & 1,00 & 12,12 & 7,67 & 55,85 & 71,93 & 100,33 \\
druid & \nolinkurl{summary_by_role} & 2375 & 2375 & 0 & 14,00 & 16,16 & 11,14 & 60,19 & 75,67 & 100,45 \\
druid & \nolinkurl{filtered_entries} & 2374 & 0 & 2374 & N/D & N/D & N/D & N/D & N/D & N/D \\
materialize & \nolinkurl{entries_count} & 19 & 19 & 0 & 1,00 & 415,26 & 521,17 & 875,08 & 892,50 & 896,85 \\
materialize & \nolinkurl{summary_by_role} & 19 & 19 & 0 & 14,00 & 385,83 & 191,97 & 855,90 & 1091,34 & 1150,20 \\
materialize & \nolinkurl{filtered_entries} & 19 & 19 & 0 & 50,00 & 727,62 & 568,32 & 1432,35 & 1493,73 & 1509,08 \\
pinot & \nolinkurl{entries_count} & 16090 & 16090 & 0 & 1,00 & 1,76 & 1,41 & 3,04 & 4,41 & 105,87 \\
pinot & \nolinkurl{summary_by_role} & 16089 & 16089 & 0 & 14,00 & 1,94 & 1,58 & 3,32 & 4,79 & 86,29 \\
pinot & \nolinkurl{filtered_entries} & 16089 & 16089 & 0 & 50,00 & 1,88 & 1,52 & 3,25 & 4,79 & 129,59 \\
\bottomrule
\end{longtable}
\normalsize



\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{p{1.8cm}rrrrrrrr}
\caption{Tempos até o primeiro sucesso observável de API e SQL nas rodadas canônicas.}\label{tab:readiness}\\
\toprule
Backend & API summary & API workspace & API entries & Summary > 0 & Workspace > 0 & SQL count & SQL role & SQL filtered \\\midrule
\endfirsthead
\toprule
Backend & API summary & API workspace & API entries & Summary > 0 & Workspace > 0 & SQL count & SQL role & SQL filtered \\\midrule
\endhead
clickhouse & 51720 & 51756 & 51972 & 51720 & 51756 & 150579 & 150601 & 150605 \\
druid & 69834 & 71025 & 64029 & 69834 & 71025 & 152835 & 152870 & N/D \\
materialize & 69146 & 70158 & 72062 & 69146 & 70158 & 167129 & 168088 & 169127 \\
pinot & 120916 & 122052 & 122360 & 151893 & 151982 & 219857 & 219888 & 219892 \\
\bottomrule
\end{longtable}
\normalsize



## Convergência visual e experiência percebida

\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{p{1.8cm}rrrrrrrrr}
\caption{Métricas de convergência visual e propagação de eventos nas rodadas canônicas.}\label{tab:websocket-metrics}\\
\toprule
Backend & Meaningful & 1o snapshot & Entry -> fila & Evento -> snapshot & Venda -> sales & Snapshots/s & Entries/s & Snapshots & Entry.created \\\midrule
\endfirsthead
\toprule
Backend & Meaningful & 1o snapshot & Entry -> fila & Evento -> snapshot & Venda -> sales & Snapshots/s & Entries/s & Snapshots & Entry.created \\\midrule
\endhead
clickhouse & 104 & 258 & 104 & 154 & 154 & 2,3369 & 78,3223 & 231 & 7742 \\
druid & 45 & 556 & 45 & 511 & 508 & 2,3070 & 79,3577 & 228 & 7843 \\
materialize & 157 & 1439 & 157 & 1282 & 524 & 2,3353 & 53,4821 & 224 & 5130 \\
pinot & 42 & 42 & 155 & N/D & N/D & 0,0202 & 78,9367 & 2 & 7801 \\
\bottomrule
\end{longtable}
\normalsize



## Estabilidade operacional e cobertura diagnóstica

\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{1.8cm}L{2.4cm}rrrrL{4.6cm}}
\caption{Prontidão observada pelos health checks durante as rodadas canônicas.}\label{tab:health-timeline}\\
\toprule
Backend & Endpoint & Amostras & Não ok & 1o ok ms & Transições & Estados observados \\\midrule
\endfirsthead
\toprule
Backend & Endpoint & Amostras & Não ok & 1o ok ms & Transições & Estados observados \\\midrule
\endhead
clickhouse & \nolinkurl{backend_debug} & 134 & 134 & N/D & 0 & running \\
clickhouse & \nolinkurl{backend_health} & 134 & 0 & 51730 & 0 & ok \\
clickhouse & \nolinkurl{master_data} & 134 & 0 & 51691 & 0 & ok \\
clickhouse & \nolinkurl{realtime_gateway} & 134 & 0 & 51728 & 0 & ok \\
clickhouse & \nolinkurl{storage_writer} & 134 & 0 & 51722 & 0 & ok \\
druid & \nolinkurl{backend_debug} & 122 & 122 & N/D & 0 & desconhecido \\
druid & \nolinkurl{backend_health} & 122 & 3 & 64441 & 1 & warming\_up | ok \\
druid & \nolinkurl{master_data} & 122 & 0 & 53731 & 0 & ok \\
druid & \nolinkurl{realtime_gateway} & 122 & 0 & 54489 & 0 & ok \\
druid & \nolinkurl{storage_writer} & 122 & 0 & 53764 & 0 & ok \\
materialize & \nolinkurl{backend_debug} & 53 & 53 & N/D & 14 & ready | warming\_up \\
materialize & \nolinkurl{backend_health} & 53 & 0 & 68156 & 0 & ok \\
materialize & \nolinkurl{master_data} & 53 & 0 & 68124 & 0 & ok \\
materialize & \nolinkurl{realtime_gateway} & 53 & 0 & 68153 & 0 & ok \\
materialize & \nolinkurl{storage_writer} & 53 & 0 & 68149 & 0 & ok \\
pinot & \nolinkurl{backend_debug} & 134 & 134 & N/D & 1 & retrying | ready \\
pinot & \nolinkurl{backend_health} & 134 & 0 & 120928 & 0 & ok \\
pinot & \nolinkurl{master_data} & 134 & 0 & 120878 & 0 & ok \\
pinot & \nolinkurl{realtime_gateway} & 134 & 0 & 120924 & 0 & ok \\
pinot & \nolinkurl{storage_writer} & 134 & 0 & 120915 & 0 & ok \\
\bottomrule
\end{longtable}
\normalsize



\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{1.8cm}L{4.0cm}rrrrr}
\caption{Cobertura dos snapshots finais de debug nas rodadas canônicas.}\label{tab:debug-snapshots}\\
\toprule
Backend & Snapshot & OK & Campos & Timestamp & Entries & Balance sheet \\\midrule
\endfirsthead
\toprule
Backend & Snapshot & OK & Campos & Timestamp & Entries & Balance sheet \\\midrule
\endhead
clickhouse & \nolinkurl{backend_debug} & sim & 10 & não & não & não \\
clickhouse & \nolinkurl{backend_entries} & sim & 5 & não & sim & não \\
clickhouse & \nolinkurl{backend_filter_options} & sim & 13 & não & não & não \\
clickhouse & \nolinkurl{backend_health} & sim & 2 & não & não & não \\
clickhouse & \nolinkurl{backend_summary} & sim & 7 & sim & sim & sim \\
clickhouse & \nolinkurl{backend_workspace} & sim & 8 & sim & sim & não \\
clickhouse & \nolinkurl{master_data_health} & sim & 2 & não & não & não \\
clickhouse & \nolinkurl{realtime_gateway_health} & sim & 5 & não & não & não \\
clickhouse & \nolinkurl{storage_writer_health} & sim & 2 & não & não & não \\
druid & \nolinkurl{backend_debug} & sim & 6 & não & não & não \\
druid & \nolinkurl{backend_entries} & sim & 5 & não & sim & não \\
druid & \nolinkurl{backend_filter_options} & não & 0 & não & não & não \\
druid & \nolinkurl{backend_health} & sim & 3 & não & não & não \\
druid & \nolinkurl{backend_summary} & sim & 7 & sim & sim & sim \\
druid & \nolinkurl{backend_workspace} & sim & 8 & sim & sim & não \\
druid & \nolinkurl{master_data_health} & sim & 2 & não & não & não \\
druid & \nolinkurl{realtime_gateway_health} & sim & 5 & não & não & não \\
druid & \nolinkurl{storage_writer_health} & sim & 2 & não & não & não \\
materialize & \nolinkurl{backend_debug} & não & 0 & não & não & não \\
materialize & \nolinkurl{backend_entries} & não & 0 & não & não & não \\
materialize & \nolinkurl{backend_filter_options} & não & 0 & não & não & não \\
materialize & \nolinkurl{backend_health} & não & 0 & não & não & não \\
materialize & \nolinkurl{backend_summary} & não & 0 & não & não & não \\
materialize & \nolinkurl{backend_workspace} & não & 0 & não & não & não \\
materialize & \nolinkurl{master_data_health} & não & 0 & não & não & não \\
materialize & \nolinkurl{realtime_gateway_health} & não & 0 & não & não & não \\
materialize & \nolinkurl{storage_writer_health} & não & 0 & não & não & não \\
pinot & \nolinkurl{backend_debug} & não & 0 & não & não & não \\
pinot & \nolinkurl{backend_entries} & não & 0 & não & não & não \\
pinot & \nolinkurl{backend_filter_options} & não & 0 & não & não & não \\
pinot & \nolinkurl{backend_health} & não & 0 & não & não & não \\
pinot & \nolinkurl{backend_summary} & não & 0 & não & não & não \\
pinot & \nolinkurl{backend_workspace} & não & 0 & não & não & não \\
pinot & \nolinkurl{master_data_health} & não & 0 & não & não & não \\
pinot & \nolinkurl{realtime_gateway_health} & não & 0 & não & não & não \\
pinot & \nolinkurl{storage_writer_health} & não & 0 & não & não & não \\
\bottomrule
\end{longtable}
\normalsize



\begin{landscape}
\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{1.8cm}L{1.8cm}L{2.4cm}L{5.6cm}L{1.2cm}L{2.3cm}rrrr}
\caption{Falhas efetivamente observadas ao longo de todas as rodadas disponíveis.}\label{tab:round-failures}\\
\toprule
Classe & Backend & Cenário & Round ID & Tipo & Probe & Erros & Amostras & Sucesso & p95 ms \\\midrule
\endfirsthead
\toprule
Classe & Backend & Cenário & Round ID & Tipo & Probe & Erros & Amostras & Sucesso & p95 ms \\\midrule
\endhead
validação & materialize & validation-smoke & \nolinkurl{20260309T020307Z__materialize__validation-smoke__run-2} & sql & \nolinkurl{entries_count} & 16 & 16 & 0 & N/D \\
validação & materialize & validation-smoke & \nolinkurl{20260309T020307Z__materialize__validation-smoke__run-2} & sql & \nolinkurl{summary_by_role} & 16 & 16 & 0 & N/D \\
validação & materialize & validation-smoke & \nolinkurl{20260309T020307Z__materialize__validation-smoke__run-2} & sql & \nolinkurl{filtered_entries} & 16 & 16 & 0 & N/D \\
validação & materialize & validation-sql & \nolinkurl{20260309T020746Z__materialize__validation-sql__run-3} & sql & \nolinkurl{entries_count} & 17 & 17 & 0 & N/D \\
validação & materialize & validation-sql & \nolinkurl{20260309T020746Z__materialize__validation-sql__run-3} & sql & \nolinkurl{summary_by_role} & 16 & 16 & 0 & N/D \\
validação & materialize & validation-sql & \nolinkurl{20260309T020746Z__materialize__validation-sql__run-3} & sql & \nolinkurl{filtered_entries} & 16 & 16 & 0 & N/D \\
substituída & clickhouse & report-conclusion & \nolinkurl{20260309T024926Z__clickhouse__report-conclusion__run-1} & sql & \nolinkurl{entries_count} & 33073 & 33073 & 0 & N/D \\
substituída & clickhouse & report-conclusion & \nolinkurl{20260309T024926Z__clickhouse__report-conclusion__run-1} & sql & \nolinkurl{summary_by_role} & 33072 & 33072 & 0 & N/D \\
substituída & clickhouse & report-conclusion & \nolinkurl{20260309T024926Z__clickhouse__report-conclusion__run-1} & sql & \nolinkurl{filtered_entries} & 33072 & 33072 & 0 & N/D \\
canônica & druid & report-conclusion & \nolinkurl{20260309T032706Z__druid__report-conclusion__run-1} & api & \nolinkurl{summary} & 4 & 54 & 50 & 594,39 \\
canônica & druid & report-conclusion & \nolinkurl{20260309T032706Z__druid__report-conclusion__run-1} & api & \nolinkurl{workspace} & 4 & 54 & 50 & 1748,37 \\
canônica & druid & report-conclusion & \nolinkurl{20260309T032706Z__druid__report-conclusion__run-1} & api & \nolinkurl{entries} & 3 & 53 & 50 & 284,10 \\
canônica & druid & report-conclusion & \nolinkurl{20260309T032706Z__druid__report-conclusion__run-1} & sql & \nolinkurl{filtered_entries} & 2374 & 2374 & 0 & N/D \\
\bottomrule
\end{longtable}
\normalsize
\end{landscape}



## Recursos computacionais

\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{p{1.8cm}rrrrrr}
\caption{Uso consolidado de recursos computacionais por backend canônico.}\label{tab:resource-totals}\\
\toprule
Backend & Contêineres & CPU média & CPU pico & Memória média MB & Memória pico MB & Maior contêiner MB \\\midrule
\endfirsthead
\toprule
Backend & Contêineres & CPU média & CPU pico & Memória média MB & Memória pico MB & Maior contêiner MB \\\midrule
\endhead
clickhouse & 11 & 169,6943 & 183,6200 & 1923,79 & 2496,81 & 1339,39 \\
druid & 17 & 149,4246 & 101,1200 & 5281,33 & 5443,46 & 2046,98 \\
materialize & 11 & 109,3691 & 141,1800 & 2054,32 & 2255,34 & 1106,94 \\
pinot & 14 & 138,4581 & 116,7400 & 5144,59 & 5314,72 & 1499,14 \\
\bottomrule
\end{longtable}
\normalsize



A tabela consolidada de recursos permanece no corpo principal, mas o detalhamento por contêiner foi repartido por backend para preservar legibilidade sem truncar identificadores nem reduzir excessivamente o corpo tipográfico.

### Backend Clickhouse

\begin{landscape}
\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{2.4cm}L{8.6cm}rrrrr}
\caption{Detalhamento de recursos por papel de serviço para Clickhouse.}\label{tab:resource-details-clickhouse}\\
\toprule
Papel & Contêiner & CPU média & CPU pico & Memória média MB & Memória pico MB & Amostras \\\midrule
\endfirsthead
\toprule
Papel & Contêiner & CPU média & CPU pico & Memória média MB & Memória pico MB & Amostras \\\midrule
\endhead
\nolinkurl{api} & \nolinkurl{syntetic-ledger-dash-ui-api-1} & 17,3189 & 51,2100 & 61,38 & 71,80 & 35 \\
\nolinkurl{engine:clickhouse} & \nolinkurl{syntetic-ledger-dash-ui-clickhouse-1} & 87,8651 & 183,6200 & 913,58 & 1339,39 & 35 \\
\nolinkurl{frontend} & \nolinkurl{syntetic-ledger-dash-ui-frontend-1} & 0,2937 & 2,7900 & 9,74 & 10,01 & 35 \\
\nolinkurl{kafka} & \nolinkurl{syntetic-ledger-dash-ui-kafka-1} & 28,1274 & 104,5100 & 423,76 & 515,60 & 35 \\
\nolinkurl{kafka-ui} & \nolinkurl{syntetic-ledger-dash-ui-kafka-ui-1} & 4,5617 & 51,4500 & 190,45 & 195,90 & 35 \\
\nolinkurl{master-data} & \nolinkurl{syntetic-ledger-dash-ui-master-data-1} & 1,8611 & 5,4800 & 42,89 & 43,31 & 35 \\
\nolinkurl{otel-collector} & \nolinkurl{syntetic-ledger-dash-ui-otel-collector-1} & 2,0783 & 2,8700 & 60,16 & 68,17 & 35 \\
\nolinkurl{producer} & \nolinkurl{syntetic-ledger-dash-ui-producer-1} & 3,7017 & 4,8800 & 26,80 & 28,97 & 35 \\
\nolinkurl{realtime-gateway} & \nolinkurl{syntetic-ledger-dash-ui-realtime-gateway-1} & 9,0069 & 25,4400 & 42,78 & 46,03 & 35 \\
\nolinkurl{storage-writer} & \nolinkurl{syntetic-ledger-dash-ui-storage-writer-1} & 5,5811 & 14,5000 & 55,16 & 55,73 & 35 \\
\nolinkurl{zookeeper} & \nolinkurl{syntetic-ledger-dash-ui-zookeeper-1} & 9,2983 & 80,8200 & 97,10 & 121,90 & 35 \\
\bottomrule
\end{longtable}
\normalsize
\end{landscape}



### Backend Druid

\begin{landscape}
\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{2.4cm}L{8.6cm}rrrrr}
\caption{Detalhamento de recursos por papel de serviço para Druid.}\label{tab:resource-details-druid}\\
\toprule
Papel & Contêiner & CPU média & CPU pico & Memória média MB & Memória pico MB & Amostras \\\midrule
\endfirsthead
\toprule
Papel & Contêiner & CPU média & CPU pico & Memória média MB & Memória pico MB & Amostras \\\midrule
\endhead
\nolinkurl{api-druid} & \nolinkurl{syntetic-ledger-dash-ui-api-druid-1} & 3,1917 & 11,9600 & 58,93 & 63,18 & 35 \\
\nolinkurl{druid-broker} & \nolinkurl{syntetic-ledger-dash-ui-druid-broker-1} & 46,6140 & 79,7700 & 2043,73 & 2046,98 & 35 \\
\nolinkurl{druid-coordinator} & \nolinkurl{syntetic-ledger-dash-ui-druid-coordinator-1} & 2,6523 & 48,6400 & 289,36 & 290,60 & 35 \\
\nolinkurl{druid-historical} & \nolinkurl{syntetic-ledger-dash-ui-druid-historical-1} & 0,4700 & 1,7000 & 326,09 & 326,20 & 35 \\
\nolinkurl{druid-middlemanager} & \nolinkurl{syntetic-ledger-dash-ui-druid-middlemanager-1} & 30,9046 & 100,6000 & 1003,71 & 1024,00 & 35 \\
\nolinkurl{druid-overlord} & \nolinkurl{syntetic-ledger-dash-ui-druid-overlord-1} & 0,7480 & 2,7300 & 297,46 & 298,40 & 35 \\
\nolinkurl{druid-postgres} & \nolinkurl{syntetic-ledger-dash-ui-druid-postgres-1} & 0,4851 & 5,0700 & 54,66 & 56,31 & 35 \\
\nolinkurl{druid-router} & \nolinkurl{syntetic-ledger-dash-ui-druid-router-1} & 10,7831 & 44,3900 & 252,09 & 255,90 & 35 \\
\nolinkurl{frontend-druid} & \nolinkurl{syntetic-ledger-dash-ui-frontend-druid-1} & 0,7731 & 1,4900 & 10,67 & 10,87 & 35 \\
\nolinkurl{kafka} & \nolinkurl{syntetic-ledger-dash-ui-kafka-1} & 25,2083 & 101,1200 & 424,71 & 511,90 & 35 \\
\nolinkurl{kafka-ui} & \nolinkurl{syntetic-ledger-dash-ui-kafka-ui-1} & 4,5320 & 51,8500 & 190,38 & 196,10 & 35 \\
\nolinkurl{master-data} & \nolinkurl{syntetic-ledger-dash-ui-master-data-1} & 0,6874 & 3,4300 & 41,71 & 41,93 & 35 \\
\nolinkurl{otel-collector} & \nolinkurl{syntetic-ledger-dash-ui-otel-collector-1} & 2,0389 & 3,4000 & 61,46 & 69,68 & 35 \\
\nolinkurl{producer} & \nolinkurl{syntetic-ledger-dash-ui-producer-1} & 3,4431 & 4,6400 & 26,40 & 28,60 & 35 \\
\nolinkurl{realtime-gateway} & \nolinkurl{syntetic-ledger-dash-ui-realtime-gateway-1} & 9,5943 & 21,2100 & 44,17 & 49,58 & 35 \\
\nolinkurl{storage-writer} & \nolinkurl{syntetic-ledger-dash-ui-storage-writer-1} & 1,5906 & 2,8200 & 50,61 & 51,23 & 35 \\
\nolinkurl{zookeeper} & \nolinkurl{syntetic-ledger-dash-ui-zookeeper-1} & 5,7080 & 84,0900 & 105,18 & 122,00 & 35 \\
\bottomrule
\end{longtable}
\normalsize
\end{landscape}



### Backend Materialize

\begin{landscape}
\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{2.4cm}L{8.6cm}rrrrr}
\caption{Detalhamento de recursos por papel de serviço para Materialize.}\label{tab:resource-details-materialize}\\
\toprule
Papel & Contêiner & CPU média & CPU pico & Memória média MB & Memória pico MB & Amostras \\\midrule
\endfirsthead
\toprule
Papel & Contêiner & CPU média & CPU pico & Memória média MB & Memória pico MB & Amostras \\\midrule
\endhead
\nolinkurl{api-materialize} & \nolinkurl{syntetic-ledger-dash-ui-api-materialize-1} & 12,7200 & 56,4800 & 58,99 & 75,79 & 35 \\
\nolinkurl{frontend-materialize} & \nolinkurl{syntetic-ledger-dash-ui-frontend-materialize-1} & 0,1651 & 0,6700 & 10,31 & 10,43 & 35 \\
\nolinkurl{kafka} & \nolinkurl{syntetic-ledger-dash-ui-kafka-1} & 26,5540 & 102,5300 & 427,45 & 508,70 & 35 \\
\nolinkurl{kafka-ui} & \nolinkurl{syntetic-ledger-dash-ui-kafka-ui-1} & 0,1983 & 2,0900 & 218,83 & 219,10 & 35 \\
\nolinkurl{master-data} & \nolinkurl{syntetic-ledger-dash-ui-master-data-1} & 0,3306 & 4,6800 & 43,59 & 43,78 & 35 \\
\nolinkurl{materialized} & \nolinkurl{syntetic-ledger-dash-ui-materialized-1} & 47,0003 & 112,1000 & 1018,09 & 1106,94 & 35 \\
\nolinkurl{otel-collector} & \nolinkurl{syntetic-ledger-dash-ui-otel-collector-1} & 2,3309 & 5,8600 & 58,82 & 66,78 & 35 \\
\nolinkurl{producer} & \nolinkurl{syntetic-ledger-dash-ui-producer-1} & 3,6677 & 6,3600 & 33,33 & 35,69 & 35 \\
\nolinkurl{realtime-gateway} & \nolinkurl{syntetic-ledger-dash-ui-realtime-gateway-1} & 6,1231 & 13,2600 & 42,89 & 45,61 & 35 \\
\nolinkurl{storage-writer} & \nolinkurl{syntetic-ledger-dash-ui-storage-writer-1} & 1,5969 & 2,2400 & 47,50 & 47,91 & 35 \\
\nolinkurl{zookeeper} & \nolinkurl{syntetic-ledger-dash-ui-zookeeper-1} & 8,6823 & 141,1800 & 94,51 & 94,61 & 35 \\
\bottomrule
\end{longtable}
\normalsize
\end{landscape}



### Backend Pinot

\begin{landscape}
\scriptsize
\setlength{\LTleft}{0pt}
\setlength{\LTright}{0pt}
\setlength{\tabcolsep}{4pt}
\begin{longtable}{L{2.4cm}L{8.6cm}rrrrr}
\caption{Detalhamento de recursos por papel de serviço para Pinot.}\label{tab:resource-details-pinot}\\
\toprule
Papel & Contêiner & CPU média & CPU pico & Memória média MB & Memória pico MB & Amostras \\\midrule
\endfirsthead
\toprule
Papel & Contêiner & CPU média & CPU pico & Memória média MB & Memória pico MB & Amostras \\\midrule
\endhead
\nolinkurl{api-pinot} & \nolinkurl{syntetic-ledger-dash-ui-api-pinot-1} & 14,0256 & 50,8900 & 60,66 & 66,57 & 36 \\
\nolinkurl{frontend-pinot} & \nolinkurl{syntetic-ledger-dash-ui-frontend-pinot-1} & 0,7744 & 1,7100 & 9,76 & 9,85 & 36 \\
\nolinkurl{kafka} & \nolinkurl{syntetic-ledger-dash-ui-kafka-1} & 27,6675 & 101,0300 & 420,00 & 489,20 & 36 \\
\nolinkurl{kafka-ui} & \nolinkurl{syntetic-ledger-dash-ui-kafka-ui-1} & 0,1639 & 2,9100 & 185,38 & 186,00 & 36 \\
\nolinkurl{master-data} & \nolinkurl{syntetic-ledger-dash-ui-master-data-1} & 2,0878 & 8,6000 & 39,35 & 39,62 & 36 \\
\nolinkurl{otel-collector} & \nolinkurl{syntetic-ledger-dash-ui-otel-collector-1} & 2,0558 & 3,3100 & 55,37 & 67,69 & 36 \\
\nolinkurl{pinot-broker} & \nolinkurl{syntetic-ledger-dash-ui-pinot-broker-1} & 43,5428 & 102,7600 & 1276,22 & 1280,00 & 36 \\
\nolinkurl{pinot-controller} & \nolinkurl{syntetic-ledger-dash-ui-pinot-controller-1} & 1,6181 & 15,6800 & 1270,56 & 1274,88 & 36 \\
\nolinkurl{pinot-server} & \nolinkurl{syntetic-ledger-dash-ui-pinot-server-1} & 20,9681 & 95,4800 & 1485,48 & 1499,14 & 36 \\
\nolinkurl{pinot-zookeeper} & \nolinkurl{syntetic-ledger-dash-ui-pinot-zookeeper-1} & 6,1014 & 116,7400 & 119,47 & 147,10 & 36 \\
\nolinkurl{producer} & \nolinkurl{syntetic-ledger-dash-ui-producer-1} & 3,4728 & 4,2800 & 26,85 & 28,93 & 36 \\
\nolinkurl{realtime-gateway} & \nolinkurl{syntetic-ledger-dash-ui-realtime-gateway-1} & 6,8264 & 9,5100 & 42,98 & 44,45 & 36 \\
\nolinkurl{storage-writer} & \nolinkurl{syntetic-ledger-dash-ui-storage-writer-1} & 1,6053 & 2,0600 & 53,59 & 54,59 & 36 \\
\nolinkurl{zookeeper} & \nolinkurl{syntetic-ledger-dash-ui-zookeeper-1} & 7,5483 & 66,8300 & 98,93 & 126,70 & 36 \\
\bottomrule
\end{longtable}
\normalsize
\end{landscape}



## Síntese orientada pelos dados

As tabelas confirmam que o corpus canônico final preserva corretude contábil total em todos os backends, mas não preserva equivalência operacional entre eles. ClickHouse e Pinot dominam as superfícies HTTP e SQL na maior parte das consultas observadas, enquanto Druid e Materialize exibem custos muito superiores nessas mesmas interfaces.

Ao mesmo tempo, a camada de convergência visual exige leitura menos simplista. Druid mantém `frontend_time_to_first_meaningful_state_ms` muito baixo e cadência de snapshots comparável à de ClickHouse, mesmo com warm-up inicial e erros transitórios na superfície HTTP. Pinot, por contraste, é extremamente competitivo em leitura direta, mas sua cadência autoritativa de snapshots permanece muito inferior nas métricas coletadas.

O inventário histórico das rodadas também mostra por que o artigo não deve se apoiar apenas na última tabela-resumo: houve tentativas substituídas e cenários de validação com falhas concentradas em probes SQL e em fases de readiness. Isso justifica separar explicitamente corpus canônico, corpus auxiliar e evidência diagnóstica, além de orientar futuros reruns de dupla conformação nas trilhas com maior incidência de erro.
