#!/usr/bin/env bash
# Standard pdfLaTeX build from frozen, checked-in paper evidence.
# No acquisition, bootstrap resampling, or white-box simulation is executed.
set -euo pipefail
cd "$(dirname "$0")"
python3 plot_nested_paper_figures_v1.py
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
echo "PRAISE_PAPER_BUILD_PASS $(pwd)/main.pdf"
