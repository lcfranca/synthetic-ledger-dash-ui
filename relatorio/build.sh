#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
OUTPUT_FILE="$DIST_DIR/synthetic-ledger-backend-benchmark-report.pdf"

mkdir -p "$DIST_DIR"

pandoc \
  "$SCRIPT_DIR/frontmatter.md" \
  "$SCRIPT_DIR/chapters/01-introducao.md" \
  "$SCRIPT_DIR/chapters/02-fundamentacao-teorica.md" \
  "$SCRIPT_DIR/chapters/03-estado-da-arte-tecnologico.md" \
  "$SCRIPT_DIR/chapters/04-modelo-do-problema-e-arquitetura.md" \
  "$SCRIPT_DIR/chapters/05-metodologia-de-benchmark.md" \
  "$SCRIPT_DIR/chapters/06-resultados-preliminares.md" \
  "$SCRIPT_DIR/chapters/07-conclusao.md" \
  "$SCRIPT_DIR/chapters/appendix-a-protocolo-de-coleta.md" \
  "$SCRIPT_DIR/chapters/appendix-b-especificacao-de-artefatos.md" \
  --metadata-file "$SCRIPT_DIR/metadata.yaml" \
  --from markdown+raw_tex \
  --no-highlight \
  --pdf-engine=xelatex \
  --template "$SCRIPT_DIR/template.tex" \
  --top-level-division=chapter \
  --output "$OUTPUT_FILE"

echo "$OUTPUT_FILE"