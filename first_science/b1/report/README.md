# B1 academic-style technical report (first draft)

**Status:** Internal author/coauthor working draft (v0.1), 16 October 2026. **Not published, and not yet publication-cleared.**

- [GitHub-readable manuscript with repaired display equations](B1_TECHNICAL_REPORT_GITHUB_VIEW_V0_1.md), using 26 native GitHub `math` blocks. This is the preferred browser reading copy.
- [Complete Pandoc/LaTeX source Markdown](B1_TECHNICAL_REPORT_DRAFT_V0_1.md), approximately 9,000 words across twelve chapters, executive synthesis and three technical/provenance/reference appendices.
- [Figure 1, Phase5 aggregate MAE](figures/phase5_aggregate_mae_v0_1.svg), built directly from independently audited V3b saved-result metrics.
- [Figure 2, Phase6 matched information–method MAE](figures/phase6_matched_mae_v0_1.svg), built from audited P4/G_SEQPAR six-way evaluation metrics.
- [Final drafting sign-off](../FINAL_AUDIT_SIGNOFF_2026-10-16.md), [original-to-B1 migration matrix](../MANUSCRIPT_MIGRATION_MATRIX_V0_1.csv), [68-item claim-to-draft crosswalk](CLAIM_TO_DRAFT_TRACEABILITY_V0_1.csv) and [draft QA report](REPORT_DRAFT_QA_V0_1_2026-10-16.md).

**Source PDF caution:** The source manuscript \`praise_caise_workshop_note_v11_45(1).pdf\` was *not* overwritten or rebranded. Tables and formulas carried into the new report are scoped by provenance and historical method version; the two charts are new visualizations of verified data, not new experiments.

## Overleaf source and compiled deliverables

**Build status: SUCCESS**. The [GitHub Actions XeLaTeX run](https://github.com/ildefons/praise-cao-sim/actions/runs/38920807623) compiled the complete report. Its outputs are now tracked on this branch.

- [Rendered **22-page PDF**](B1_TECHNICAL_REPORT_DRAFT_V0_1.pdf)
- [Overleaf **import ZIP**](B1_OVERLEAF_PROJECT_V0_1.zip), including `main.tex`, both LaTeX figure sources, and a copy of the compiled report PDF.
- [Full LaTeX source directory](overleaf/), containing `main.tex` and two PGFPlots figure files.
- [GitHub-readable Markdown with 26 math fences](B1_TECHNICAL_REPORT_GITHUB_VIEW_V0_1.md)

To import: **Overleaf → New Project → Upload Project → choose the ZIP**. Set main file `main.tex` and compiler **XeLaTeX**. For local PDF rebuilding, run:

```bash
cd first_science/b1/report/overleaf
latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex
```

The PDF was rendered, its 22 pages were inspected, and mathematical formulas and charts were checked for visible rendering errors. The LaTeX project is the editable authoritative manuscript format; the Markdown view is intended only for reading on GitHub.

## Academic-quality and release gates

The report is drafted to publication-grade standards **in structure and scientific precision**, but it is **not yet peer-review/public-arXiv ready**. Before public release, review:

1. Coauthor consent, attributions and affiliation details.
2. Bibliography entries, DOIs, up-to-date related work and potential overlap with the targeted methodological paper.
3. Original pilot operational Top1 B100/Top3 B300 ancillary numbers and the M2 paired-bootstrap width (reported, not independently recomputed).
4. A deeper I1 acquisition/region verification if any claimed nestedness guarantee goes beyond frozen-contract scope.
5. Whether exact historical AICon dependency and reproducible runtime environment can be reconstructed from source/commit provenance.
6. Final captions, figure labels, PDF appearance and any page overflow. Do not treat an automatically compiled PDF as editorial approval.

The B1 report is intended as an **eventually citable technical record**, potentially for arXiv after approval; the methodological paper should have a **distinct**, narrower, independently justified scientific thesis.

## Development constraints

Do not import unpublished PPG GP+DVI, readiness scores or old private experimental scenarios. Do not modify frozen simulator contracts, seed banks, scientific runs, archived manifests or historical results. The report can be revised independently.

