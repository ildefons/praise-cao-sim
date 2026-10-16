# B1 academic-style technical report (first draft)

**Status:** Internal author/coauthor working draft (v0.1), 16 October 2026. **Not published, and not yet publication-cleared.**

- [Main manuscript](B1_TECHNICAL_REPORT_DRAFT_V0_1.md), approximately 9,000 words across twelve chapters, executive synthesis and three technical/provenance/reference appendices.
- [Figure 1, Phase5 aggregate MAE](figures/phase5_aggregate_mae_v0_1.svg), built directly from independently audited V3b saved-result metrics.
- [Figure 2, Phase6 matched information–method MAE](figures/phase6_matched_mae_v0_1.svg), built from audited P4/G_SEQPAR six-way evaluation metrics.
- [Final drafting sign-off](../FINAL_AUDIT_SIGNOFF_2026-10-16.md), [original-to-B1 migration matrix](../MANUSCRIPT_MIGRATION_MATRIX_V0_1.csv), [68-item claim-to-draft crosswalk](CLAIM_TO_DRAFT_TRACEABILITY_V0_1.csv) and [draft QA report](REPORT_DRAFT_QA_V0_1_2026-10-16.md).

**Source PDF caution:** The source manuscript \`praise_caise_workshop_note_v11_45(1).pdf\` was *not* overwritten or rebranded. Tables and formulas carried into the new report are scoped by provenance and historical method version; the two charts are new visualizations of verified data, not new experiments.

## Build PDF on the original repository checkout

Requires Pandoc 3.x, XeLaTeX and a working converter for SVG images (for example Inkscape). Run:

\`\`\`bash
cd ~/praise/praise-cao-sim
git pull
cd first_science/b1/report
bash build_pdf.sh
\`\`\`

The result is \`B1_TECHNICAL_REPORT_DRAFT_V0_1.pdf\`. This command **does not** perform a scientific experiment. Build output is not an authority for source results; the Markdown, figures and evidence registry are.

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
