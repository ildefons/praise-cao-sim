#!/usr/bin/env bash
# Standard-pdfLaTeX build of the PRAISE systems paper.
# Converts the archived historical SVG and renders a paper-only fresh-reference zoom
# from frozen summary data. No selection policy, bootstrap, or simulation is rerun.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p figures

convert_frozen_svg() {
  local source="$1"
  local target="$2"
  if [[ ! -s "$source" ]]; then
    echo "Missing source figure: $source" >&2
    exit 1
  fi
  if command -v inkscape >/dev/null 2>&1; then
    inkscape "$source" --export-type=pdf --export-filename="$target"
  elif command -v rsvg-convert >/dev/null 2>&1; then
    rsvg-convert -f pdf -o "$target" "$source"
  elif python3 -c 'import cairosvg' >/dev/null 2>&1; then
    python3 - "$source" "$target" <<'PY'
import cairosvg,sys
cairosvg.svg2pdf(url=sys.argv[1],write_to=sys.argv[2])
PY
  else
    echo "SVG-to-PDF converter not installed: use Inkscape, rsvg-convert, or Python cairosvg." >&2
    echo "Ubuntu example: sudo apt-get install librsvg2-bin" >&2
    exit 1
  fi
  test -s "$target"
}

convert_frozen_svg \
  "../results/b1_nine_policy_13_budget_extension_v1/figures/historical_nine_policy_13_budget_regret.svg" \
  "figures/historical_nine_policy_13_budget_regret.pdf"
# The paper's fresh-reference panel uses a tighter axis (0--0.012), with every
# archived 95% interval still visible. The original shared-axis plot is untouched.
python3 plot_fresh_reference_zoom_v1.py
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
echo "PRAISE_PAPER_BUILD_PASS $(pwd)/main.pdf"
