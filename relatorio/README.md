# Pacote do Relatorio

Esta pasta concentra as fontes versionaveis do relatorio tecnico em um formato compilavel com Pandoc + LaTeX.

## Estrutura

- `metadata.yaml`: metadados globais do documento.
- `frontmatter.md`: resumo executivo, sumario em ingles e nota de escopo.
- `chapters/`: capitulos e apendices em Markdown.
- `template.tex`: template LaTeX customizado para a versao de relatorio.
- `build.sh`: script reprodutivel de compilacao.
- `dist/`: saida compilada.

## Compilacao

Execute:

```bash
./relatorio/build.sh
```

O PDF final sera gerado em `relatorio/dist/synthetic-ledger-backend-benchmark-report.pdf`.