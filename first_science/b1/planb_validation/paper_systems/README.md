# PRAISE sequential validation paper — LaTeX v0.96

**Status:** method-focused working manuscript (23 November 2026), pending
local compilation and section-by-section review before submission.
The canonical source is [main.tex](main.tex) on
`praise-identifiability-feasibility`.

## What changed

- Made both independent intercept/factor-effect redundancies explicit and
  explained why six independently identifiable combinations determine the
  condition predictions. Clarified that the strictly positive Gaussian prior
  variances yield a well-defined posterior but do not identify individual
  coefficients from data alone.

- Clarified why each eight-coefficient additive method surrogate has only six
  independently identifiable prediction combinations, with a concrete
  intercept/world-effect example and the role of the Gaussian prior.

- Moved the posterior latent-loss covariance formula and the P1/PAR sharing
  figure from Section 3.3 into Step 1 of Section 3.4, following the Gaussian
  coefficient update. Adjusted explanations to make the flow from acquisition
  to posterior sharing to predicted performance explicit; no numerical results changed.

- Consolidated the interpretation of the additive prior covariance and its
  generalization into a single explanation after the derived covariance.
  Removed the redundant general covariance equation (formerly Eq. 5), kept
  the Table 1 examples and prior-sensitivity qualification, and verified
  remaining LaTeX references.

- In Section 3.3, qualify prior-scale robustness using the fourteen-setting
  sensitivity analysis: aggregate regret directions are stable for adaptive KG
  against uniform KG, Random and Balanced in both archives; absolute regrets
  and individual-budget comparisons remain sensitive.
- Add a stable reference to the relevant Evaluation subsection and correct
  escaped LaTeX notation/reference typos in the surrogate case-study paragraph.

- Explained the coefficient prior $b_0,V_0$ in Section 3.3, including the
  explicit diagonal covariance blocks and their induced sharing kernel.
  Section 4 now distinguishes the baseline numerical prior settings from the
  structural assumptions and explains the heuristic scales and sensitivity.

- Clarified in Section 3.3 that the Gaussian model coefficients are reused
  across operating conditions within each candidate method, not across methods.

- Reorganized Section 3.3 to present the additive Gaussian performance model
  first, derive its prior covariance from the shared coefficient priors, and
  then generalize the structure-to-covariance mapping. Clarified the
  latent-loss versus independent-residual distinction and preserved stable
  equation labels and references. No results or simulations changed.

- Expanded the opening of the Section 3.3 additive Gaussian instance to explain
  the choice of provider worlds and graph factors, additive components, Gaussian
  priors and residual assumptions, and the scope of this deliberately simple
  implementation before presenting the model equation.

- Clarified Section 3.3's structure-to-covariance translation and moved Table 1
  after the derived crossed-factor covariance. Table 1 now states explicit
  illustrative covariance formulas (crossed, nested, continuous, interaction)
  and identifies only the crossed-factor case as evaluated.

- Replaced the bridging paragraph in Section 3.3 to connect shared
  operating-condition characteristics with the need to estimate unobserved
  method performance and the following covariance model. No results changed.

- Clarified Section 3.2's retrospective validation procedure: archived errors are
  revealed only for selected method--condition evaluations, and the full
  catalogue is used only after recommendation to measure selection quality.

- Rewrote the opening of Section 3.2 (Validation protocol) to explain the
  shared statistical model, per-method posterior estimates, evidence acquired
  by each policy, and resulting divergence across allocation strategies.

- Refined all three Introduction contribution statements to distinguish the novel
  continuum-structure-to-sharing methodology, the method-then-condition KG rule,
  and evidence from the controlled budget comparisons. Claims now explicitly
  preserve uncertainty and note that unstructured-surrogate comparisons remain open.

- Review pass: reformulated RQ1–RQ3 around budget-efficient selection,
  sharing across structured conditions, and acquisition organization.
  Aligned contributions, evaluation interpretations, discussion, and conclusion;
  explicitly distinguish a demonstrated sharing mechanism from the untested
  incremental benefit of sharing over an independent-cell surrogate.

- Introduction now grounds general continuum heterogeneity in the reviewed 2024
  and 2025 computing-continuum surveys, with case-specific provider information
  and composition topology clearly separated. Removed the unsupported application
  trio as methodological foundations; their papers remain in Related Work.

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
- Discussion and conclusion distinguish the statistical sharing mechanism,
  the adaptive two-stage acquisition rule and the evidence for policy performance.
- Added fixed-grid sensitivity of the additive Gaussian prior: fourteen settings
  change the intercept/world/graph standard deviations, residual scale or prior mean.
  Aggregate adaptive-versus-uniform, Random and Balanced comparisons retain their
  direction in both archives for all fourteen settings. Per-budget effects vary;
  Appendix A after the references in [main.tex](main.tex) and archived tables
  document the details.

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
- `data/prior_sensitivity_decision_table.csv`: 28 scenario-by-archive
  thirteen-budget decision comparisons for the fourteen-case prior grid.
- `data/prior_sensitivity_aggregate_contrasts.csv`: 224 exploratory nominal
  95% bootstrap contrasts, **not** familywise-adjusted over prior configurations.
- `data/prior_sensitivity_analysis_manifest.json`: scenario specifications,
  source-manifest hashes and exact hashes for the two analysis CSVs.
- `data/prior_sensitivity_budget_diagnostics.csv`: 26 archive-by-budget
  rows derived from all fourteen scenario-specific policy summaries.
- Appendix A in `main.tex`, placed after the bibliography: parameter grid,
  aggregate comparison counts, and budget-dependent sensitivity table.

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
were chosen after examining earlier curves. The prior-sensitivity grid checks
numerical parameters **within the additive surrogate**; it does not compare
distinct covariance structures or establish
whether the original heuristic numerical choices involved any informal use of
observed outcomes. Alternative surrogate structures, new operating environments
and measured evaluation costs remain future work.

## Review workflow

Review the PDF section by section. The title, contributions and methodological
definition are deliberately aligned with the Results, Discussion and Conclusion.
Avoid reintroducing labels meaningful only to the archive scripts, numerical
seeds, or internal development chronology into the paper. The project is
venue-neutral pending target-format selection.
