# PRAISE sequential validation paper — LaTeX v0.77

**Status:** method-focused working manuscript (20 November 2026), pending
local compilation and section-by-section review before submission.
The canonical source is [main.tex](main.tex) on
`praise-identifiability-feasibility`.

## What changed

- Primary method: one Gaussian surrogate per candidate predictor, with
  world and graph factors sharing posterior information between conditions.
- Algorithmic contribution: two-stage adaptive KG selects a method using
  average KG over its remaining conditions, then selects an informative
  condition. A matched uniform-condition KG policy uses the same first stage.
- Evidence: the six budget-independent policies use nested budget prefixes;
  the three Top2 policies retain their original budget-specific episodes.
  Both reference matrices, nine policies and thirteen budgets are represented.
- Figures 3 and 4 use the verified 234-row `data/combined_nine_policy_budget_summary.csv`.
  The paper's statistic tables are reconciled to the frozen adaptive-versus-uniform
  and KG-versus-Top2 aggregate ledgers stored under `data/`.
- Figure 2 is a within-method condition-sharing schematic. The former detailed
  case-study workflow diagram is preserved, but not built, in
  [supplement_case_pipeline.tex](supplement_case_pipeline.tex).
- Discussion and conclusion now distinguish the statistical sharing mechanism,
  the adaptive two-stage acquisition rule and the evidence for policy performance.

The manuscript no longer states that joint-action KG has the lowest mean
regret: in the consistent nested comparison, adaptive two-stage KG does on
both archives. The adapted KG-versus-uniform advantage is supported by an
adjusted interval historically but remains uncertain on the fresh reference.

## Pull and compile on the laptop

The paper uses **standard pdfLaTeX** and no `fontspec`, shell escape,
external SVG converter, BibTeX or XeLaTeX engine. Figure generation requires
the existing `matplotlib` and `numpy` Python packages.

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

cd first_science/b1/planb_validation/paper_systems

python test_plot_nested_paper_figures_v1.py -v
python plot_nested_paper_figures_v1.py --preflight-only

bash build.sh
```

Expected markers:
- `PAPER_FIGURE_PREFLIGHT_PASS no files written`
- `PAPER_FIGURES_PASS no episodes or statistical resamples executed`
- `PRAISE_PAPER_BUILD_PASS .../main.pdf`

The output is `main.pdf` in this directory. The generated figure PDFs
are in `figures/`, and all generated PDFs/LaTeX auxiliary files are
**local artifacts**. Do not commit them.

```bash
xdg-open main.pdf
```

To recompile TeX only, after the paper's figure PDFs exist:

```bash
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
```

## Frozen paper evidence

- `data/combined_nine_policy_budget_summary.csv`: nine policy mean-regret
  curves and nominal 95% intervals in both archives.
- `data/nested_six_plus_frozen_top2_plot_manifest.json`: exact source
  provenance and original summary hashes.
- `data/kg_condition_adaptivity_aggregate_contrasts.csv` and its manifest:
  matched adaptive-versus-uniform KG comparisons with independent
  policy-resampling and preserved across-budget dependence.
- `data/kg_vs_top2_*_aggregate_contrasts.csv` and matching manifests:
  cross-design adaptive-KG comparisons with three frozen Top2 variants.

The plotting script verifies exact policy/budget coverage, source designs,
all input hashes, all thirteen-budget contrast means, and unclipped confidence
intervals before writing figures. It reads only the committed summary files
and never runs acquisition episodes, bootstrap resampling or simulations.

### Interpretation boundaries

The evaluation is retrospective on two fixed seven-predictor by twelve-condition
loss matrices. Bootstrap intervals describe acquisition-randomization
uncertainty conditional on each matrix; they do not resample the underlying
white-box reference trajectories. Multiple comparisons against three Top2
variants are corrected within each archive; KG adaptive-versus-uniform
contrasts are corrected across the two archives. The analyzed contrasts
were chosen after examining earlier curves. Alternative surrogate structures,
new operating environments and measured evaluation costs remain future work.

## Review workflow

Review the PDF section by section. The title, contributions and methodological
definition are deliberately aligned with the Results, Discussion and Conclusion.
Avoid reintroducing labels meaningful only to the archive scripts, numerical
seeds, or internal development chronology into the paper. The project is
venue-neutral pending target-format selection.
