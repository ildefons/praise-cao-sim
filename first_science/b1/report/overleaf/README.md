# Full B1 Overleaf project (first typeset draft)

**Main document:** `main.tex`  
**Compiler:** pdfLaTeX (Overleaf default)  
**Scientific source:** [B1 technical report draft](../B1_TECHNICAL_REPORT_DRAFT_V0_1.md)  
**Status:** Internal draft. Neither author approval nor public release is implied.

The Overleaf project is deliberately **self-contained**: its two charts are included as `figures/phase5_aggregate.tex` and `figures/phase6_aggregate.tex` and use the standard PGFPlots package. No external images, minted/shell-escape, file links or simulator results are needed to compile this directory.

This LaTeX is a format conversion of the existing 9,000-word B1 report, preserving its method definitions and evidence status. The complete technical derivations and bibliography are retained in `main.tex`. The historical CAiSE PDF and scientific simulation data are not modified.

## Overleaf

Create a new blank project and upload `main.tex` and the `figures/` directory (or upload the self-contained ZIP, which also includes the rendered report PDF). Leave Overleaf's **default pdfLaTeX compiler** selected, with `main.tex` as the main file. Click Recompile. No special compiler selection, custom fonts, or shell escape are required.

## Local build

```bash
cd first_science/b1/report/overleaf
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

## Known publication-readiness issues

The bibliography was inherited from the pilot and has not been freshly verified. Some historical secondary numerical figures and raw YAFS dependency provenance checks remain open in `../REPORT_DRAFT_QA_V0_1_2026-10-16.md`. Coauthor approval and venue policy must precede public arXiv distribution.
