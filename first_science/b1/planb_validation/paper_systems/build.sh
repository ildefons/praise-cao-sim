#!/usr/bin/env bash
# Standard pdfLaTeX build using the revised analytical interval tables.
set -euo pipefail
cd "$(dirname "$0")"
python3 plot_analytical_figures.py data/analytical_curve_intervals.csv data/combined_nine_policy_budget_summary.csv figures
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
echo "PRAISE_PAPER_BUILD_PASS $(pwd)/main.pdf"
