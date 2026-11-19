# PRAISE Plan B — E1a structural-surrogate value, executable protocol v1

**Date:** 19 November 2026  
**Scope:** F1/E1a implementation; retrospective prediction and fixed-mask decision diagnostic  
**Status:** DESIGN + CODE; awaiting tests and experiment execution **on the user's laptop**  
**Parent:** [`B1_ENHANCED_RESEARCH_PROGRAM_FREEZE_2026-11-19_V1.md`](B1_ENHANCED_RESEARCH_PROGRAM_FREEZE_2026-11-19_V1.md)

## 1. Scientific question

How much predictive and terminal-selection value comes specifically from sharing
information across the provider-world and graph factors? Does allowing
world-by-graph interactions correct useful structure or destroy sample efficiency
when observations are sparse?

This first step isolates the **surrogate** by holding the acquired observations
fixed. It is deliberately distinct from **E1b**, which will hold the acquisition
rule (joint-action KG) fixed while allowing each surrogate to generate its own
adaptive action history. E1a alone cannot demonstrate an improvement in KG.

## 2. Frozen materials and evaluation population

- Seven candidate composed-service predictors, no new algorithms.
- Three provider worlds P1/P3/P4 × four graphs G_PAR, G_PARSEQ, G_SEQ,
  G_SEQPAR: twelve conditions and 84 method–condition MAEs.
- Historical development matrix, SHA-256
  `0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d`.
- B0001 fresh-reference matrix, SHA-256
  `5c81f50af9fad98596f0eac17ec3e9afc7848661acf476740af48663119606a3`.
- The B0001 reference uses new white-box trajectories **on the same worlds and
  graphs**. It is not a new independent operating-condition population.
- Input bytes, method labels, condition order and unique finite loss values are
  verified before processing. Existing replay policies and frozen evidence are
  never modified. The script does not import any simulator.

## 3. Controlled Gaussian models

For each method independently, let the latent twelve-cell loss vector have
prior mean `0.17 * ones(12)`. Use the original working residual SD `0.055`;
this represents a modeling discrepancy rather than repeat sampling of a
finite-catalogue MAE. Model B is the **exact covariance-space equivalent** of
the current per-method additive coefficient prior:

\[
K_B(c,c')=0.12^2+0.07^2\mathbf1[w=w']+0.045^2\mathbf1[g=g'].
\]

The compared models are:

| Label | Prior covariance for twelve-cell vector | Role |
| --- | --- | --- |
| `A_independent` | `K_A = diag(diag(K_B))` | No cross-condition transfer |
| `B_additive` | `K_B` | Original crossed-factor sharing |
| `C_interaction_25` | `0.75 K_B + 0.25 K_A` | **Primary** interaction-aware model |
| `C_interaction_50` | `0.50 K_B + 0.50 K_A` | Prespecified stronger-interaction sensitivity |

Thus all models have exactly the same marginal prior variance and mean.
C reallocates a declared fraction of variance from shared components to an
independent method-specific world–graph interaction. Its interaction is shrunk
to zero in the limit of zero allocated fraction. The C25 versus C50 contrast
is a sensitivity analysis, **not** a grid search for a winner. No hyperparameter
is fitted to the complete historical or B0001 matrix.

Given observed subset `S`, posterior predictive means for all twelve cells are
computed by the Gaussian covariance identity:

\[
\widehat{f}_a=0.17\mathbf1 + K_{:,S}(K_{S,S}+0.055^2 I)^{-1}
(Y_{a,S}-0.17\mathbf1).
\]

The posterior uses only `Y[a,S]`; hidden outcomes are accessed solely to score
predictions afterward. For B, mean posterior predictions match the original
coefficient-space posterior in `b1_budget_comparison_v1.py`.

## 4. Exact-mask experiment

For every mask size `n=1,...,11`, enumerate **all** `choose(12,n)` subsets of
observed conditions. Across sizes there are exactly `2^12 - 2 = 4094`
nonempty proper subsets. At each mask:

1. Every one of the seven methods reveals its loss on exactly the same `n`
   conditions, equivalent to `7n` nonadaptive validation actions.
2. Evaluate all models with **identical observations** and a common terminal
   recommendation objective: the lowest posterior estimated mean across all
   twelve cells.
3. Score hidden-cell predictions only after computing the posterior.
4. Compare the recommended method with the complete matrix's best method;
   calculate simple regret and whether the recommendation is correct.

This fully enumerated paired design requires no mask RNG or mask Monte Carlo.
It does not reproduce a 10..80-budget KG trajectory, because all methods get
the same set of observed conditions. That is exactly why it isolates the
surrogate from adaptive acquisition.

### Endpoints and contrasts

- **Primary diagnostic:** mean absolute error over the unobserved cells.
- **Secondary diagnostics:** held-out RMSE, marginal Gaussian negative
  log-predictive density (working-model score), absolute error in the seven
  method domain means, terminal simple regret, best-method selection rate,
  and method–condition-specific error (especially P1 × G_PAR).
- **Paired comparisons:** B minus A; primary C25 minus B; sensitivity C50
  minus B. Negative differences mean the **first** model is better for all
  three loss-based metrics.
- Present all eleven mask sizes and both archives, including adverse results.
  The same candidate and cell priors, model noise, and input matrices apply to
  every comparison.

Exact-mask averages are descriptive expectations over subsets **conditional
on the two fixed matrices**. They are not independent-world replications and
must not be given confidence intervals based on pretending masks are
independent worlds. Highly overlapping subsets and seven correlated methods
are not independent observations.

## 5. Go/stop checks

1. Input hashes and 7×12 completeness pass; otherwise **STOP**.
2. Synthetic tests verify equal initial marginal scales, covariance
   validity, no hidden-outcome leakage, exact subset count and identity with
   the original additive Gaussian posterior; otherwise **STOP**.
3. The output directory must not preexist; the runner refuses to overwrite it.
4. A manifest records source hashes, exact model settings, script SHA,
   output hashes and limitations.
5. If B improves over A, report within-archive support for sharing. If
   C improves over B, report the interaction/variance tradeoff. If neither
   improves, report the negative result and reconsider the additive
   contribution claim. These are **exploratory** outcomes because the
   historical and B0001 losses have already been inspected.

## 6. Execution — user's Ubuntu laptop only

From the repository root:

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
python first_science/b1/planb_validation/test_b1_e1a_surrogate_structure_v1.py -v
```

Check inputs without producing results:

```bash
python first_science/b1/planb_validation/b1_e1a_surrogate_structure_v1.py \
  --historical-matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --fresh-reference-matrix first_science/b1/planb_validation/results/b0001_original_policies_v1/01_baseline/seven_method_matrix.csv \
  --preflight-only
```

Expected preflight marker: `E1A_PREFLIGHT_PASS no outputs written`.

After passing preflight, run the exact retrospective comparison:

```bash
python first_science/b1/planb_validation/b1_e1a_surrogate_structure_v1.py \
  --historical-matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --fresh-reference-matrix first_science/b1/planb_validation/results/b0001_original_policies_v1/01_baseline/seven_method_matrix.csv \
  --out ~/praise/planb_e1a_surrogate_structure_2026_11_19_v1
```

Expected terminal marker: `E1A_EXHAUSTIVE_MASK_PASS ...`.

Outputs in the new local directory:

| File | Content |
| --- | --- |
| `summary_by_observed_count.csv` | Mean outcomes for each model, archive and mask size |
| `paired_structural_contrasts.csv` | Paired differences and mask-wise win/tie proportions |
| `heldout_cell_diagnostics.csv` | Condition-specific prediction failures |
| `per_mask_metrics.csv` | All 4,094 matched masks × models × archives |
| `condition_index.csv` | Canonical condition index mapping |
| `manifest.json` | Source/output hashes and documented limitations |

Share the success marker, the summary/contrast CSVs and manifest for scientific
analysis. Preserve all outputs under their versioned directory; do not edit
or replace the frozen evidence.

## 7. Boundary of this delivery and next gate

This version supplies **E1a only**. It deliberately contains no new KG
implementation or E1b results. After examining E1a, prepare a separate,
reviewed **E1b joint-action KG A/B/C protocol**, freezing model-specific
posterior acquisition variances, matched thirteen-budget histories, seeds,
terminal estimators and statistical contrasts. E1b must remain a new replay,
separately named and never silently substituted into original nine-policy
figures. No new physical-world generation or computational-cost claim is
authorized by this E1a protocol.
