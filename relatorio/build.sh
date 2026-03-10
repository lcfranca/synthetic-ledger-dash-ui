#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
OUTPUT_FILE="$DIST_DIR/synthetic-ledger-backend-benchmark-report.pdf"
GENERATED_DIR="$SCRIPT_DIR/generated"
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

mkdir -p "$DIST_DIR"
mkdir -p "$GENERATED_DIR"

"$PYTHON_BIN" "$REPO_DIR/scripts/benchmark/generate_report_tables.py" \
  --artifacts-dir "$REPO_DIR/artifacts/benchmark" \
  --output-dir "$GENERATED_DIR"

pandoc \
  "$SCRIPT_DIR/chapters/01-introducao.md" \
  "$SCRIPT_DIR/chapters/02-fundamentacao-teorica.md" \
  "$SCRIPT_DIR/chapters/03-estado-da-arte-tecnologico.md" \
  "$SCRIPT_DIR/chapters/04-modelo-do-problema-e-arquitetura.md" \
  "$SCRIPT_DIR/chapters/05-metodologia-de-benchmark.md" \
  "$SCRIPT_DIR/chapters/06-resultados-preliminares.md" \
  "$SCRIPT_DIR/generated/06-resultados-gerados.md" \
  "$SCRIPT_DIR/chapters/07-analise-tecnica-por-backend.md" \
  "$SCRIPT_DIR/chapters/08-discussao-comparativa-ampliada.md" \
  "$SCRIPT_DIR/chapters/09-implicacoes-de-engenharia-e-programa-experimental.md" \
  "$SCRIPT_DIR/chapters/10-matriz-de-decisao-arquitetural.md" \
  "$SCRIPT_DIR/chapters/07-conclusao.md" \
  "$SCRIPT_DIR/appendices-start.md" \
  "$SCRIPT_DIR/chapters/appendix-a-protocolo-de-coleta.md" \
  "$SCRIPT_DIR/chapters/appendix-b-especificacao-de-artefatos.md" \
  "$SCRIPT_DIR/chapters/appendix-c-dossies-operacionais.md" \
  "$SCRIPT_DIR/chapters/appendix-d-glossario-analitico.md" \
  "$SCRIPT_DIR/chapters/appendix-e-programa-de-reruns-e-cenarios.md" \
  --metadata-file "$SCRIPT_DIR/metadata.yaml" \
  --from markdown+raw_tex \
  --no-highlight \
  --pdf-engine=xelatex \
  --template "$SCRIPT_DIR/template.tex" \
  --top-level-division=chapter \
  --output "$OUTPUT_FILE"

echo "$OUTPUT_FILE"