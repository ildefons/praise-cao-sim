#!/usr/bin/env bash
# Reproducible local rendering of the B1 report's academic-style Markdown source.
# The script does not execute scientific experiments or change frozen datasets.
set -euo pipefail
cd "$(dirname "$0")"
command -v pandoc >/dev/null || { echo "pandoc is required" >&2; exit 2; }
command -v xelatex >/dev/null || { echo "xelatex is required" >&2; exit 2; }
SOURCE="B1_TECHNICAL_REPORT_DRAFT_V0_1.md"
PDF="B1_TECHNICAL_REPORT_DRAFT_V0_1.pdf"
pandoc "$SOURCE" \
  --from=markdown+tex_math_dollars+raw_tex \
  --to=pdf --pdf-engine=xelatex \
  --toc --toc-depth=2 \
  --standalone \
  --output="$PDF"
echo "Wrote $PDF"
