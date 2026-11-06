#!/usr/bin/env bash
# Standard-pdfLaTeX build of the PRAISE systems paper.
# Converts the *existing frozen* SVG plot, without regenerating any data.
set -euo pipefail
cd "$(dirname "$0")"
SOURCE="../results/controlled_condition_ablation_v1/b1_controlled_seven_policy_regret_vs_budget_ci_v1.svg"
TARGET="figures/controlled_seven_policy_regret.pdf"
mkdir -p figures
if [[ ! -s "$SOURCE" ]]; then
  echo "Missing source figure: $SOURCE" >&2
  exit 1
fi
if command -v inkscape >/dev/null 2>&1; then
  inkscape "$SOURCE" --export-type=pdf --export-filename="$TARGET"
elif command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -f pdf -o "$TARGET" "$SOURCE"
elif python3 -c 'import cairosvg' >/dev/null 2>&1; then
  python3 - "$SOURCE" "$TARGET" <<'PY'
import cairosvg,sys
cairosvg.svg2pdf(url=sys.argv[1],write_to=sys.argv[2])
PY
else
  echo "SVG-to-PDF converter not installed: use Inkscape, rsvg-convert, or Python cairosvg." >&2
  echo "Ubuntu example: sudo apt-get install librsvg2-bin" >&2
  exit 1
fi
test -s "$TARGET"
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
echo "PRAISE_PAPER_BUILD_PASS $(pwd)/main.pdf"
