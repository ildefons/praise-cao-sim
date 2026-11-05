# PRAISE B1 — executable five-budget comparison freeze (v1)

**Recorded 2026-11-05, after the earlier Gate 1 and B1.2 development diagnostics.** This file freezes the executable specifications of the **first development experiment**, in addition to the previously agreed six-principle design in B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md. The historical evaluation matrix was discussed before this policy was chosen. Accordingly, this is **not** preregistration or out-of-sample confirmation.

## Experiment

- Seven methods: M1, M2, M3_FULL343, ORIGINAL_TOP14_B1400, ORIGINAL_TOP1_B1400, FIXED_CV_TOP14, FIXED_CV_TOP1.
- Twelve eligible provider-world/graph cells: P1, P3, P4 × G_PAR, G_PARSEQ, G_SEQ, G_SEQPAR.
- Finite 7×12 archive, one nonrepeatable atomic action = reveal the MAE of one algorithm on one cell. Each MAE averages 555 **correlated** query/horizon scores.
- Five **independent** known fixed-budget episodes per trial: B ∈ {10, 15, 20, 30, 40}; this is a budget on completed atomic evaluations, not computational hours.
- Start every episode by evaluating all seven algorithms on one common physical cell (7 of B actions). Run 20 independently seeded replicates at **each of the 12 possible starting cells**. Thus 240 episodes per policy per budget. The common initialization permits paired comparisons. Random means **random after this common initialization**, not uniformly random from an empty history.
- Every policy uses the **same terminal estimator** and must choose one algorithm after exactly B actions. No arm can be resampled.
- The evaluation target is the equal-cell mean MAE of each method across the full 12-cell finite universe.

## Common terminal estimator

Use a fixed additive Gaussian model separately for each algorithm:

MAE(a,w,g) = intercept(a) + world_effect(a,w) + graph_effect(a,g) + observation_noise.

Fixed prior mean: intercept = 0.17, all effects = 0. Prior SDs: intercept = 0.12; world effects = 0.07; graph effects = 0.045. Fixed assumed observation SD = 0.055. These are heuristic hyperparameters inherited from Gate 1, **not calibrated intervals** for MAE prediction or white-box reference uncertainty. All observations are the frozen cell MAEs with no further simulator noise sampled. A posterior cell-average prediction supplies a single final recommendation: algorithm with lowest posterior mean (deterministic method-order tie).

## Selection policies, fully specified

1. **random:** uniformly choose one as-yet-unrevealed action without replacement.
2. **balanced:** choose by deterministic coverage score = -100 × number of evaluations already given to that algorithm -10 × that algorithm's number of evaluations in the candidate's world -2 × its number of evaluations in the candidate's graph. Break ties by the policy's random generator.
3. **informed:** use the existing Gate 1-style pairwise heuristic. For candidate (a,c), score the reduction in posterior variance of the estimated row-average of a, weighted over all competitors b by exp[-0.5 × (mean_a-mean_b)^2/(var_a+var_b)]. It is a **budget-independent** comparison control.
4. **budgeted_top2 (minimal candidate):** knowing total budget B, reserve ceil((B-7)/2) *additional* evaluations for balanced selection. For all remaining evaluations, calculate the currently two lowest posterior row-mean algorithms and choose an available evaluation **of either of those two** that maximizes the Gaussian posterior reduction in the variance of that algorithm's row mean. Ties use the candidate's random generator. At each step the current leaders are re-evaluated; selection may change. This is a simple budget-conditioned coverage-to-discrimination schedule, not an optimal policy or a validated novel acquisition rule.

At each episode step only already revealed (algorithm, cell, MAE) triples can enter posterior fitting and acquisition. The complete source matrix is available **only** to the replay harness to return the selected measurement and later score the terminal recommendation.

## Statistical outputs and primary comparison

- Primary metric: terminal **simple regret** = (full-domain average MAE of recommended algorithm) minus (full-domain average MAE of reference-best algorithm). Lower is better.
- Secondary: reference-best selection proportion; terminal regret's 90th percentile; distribution of regret and complete per-episode action histories.
- Report each metric for every one of the five budgets; never select the most favorable budget post hoc.
- Single **primary aggregate contrast**: budgeted_top2 versus balanced, equal-weight mean of terminal simple regret over the five frozen budgets. Also show budget-specific paired contrasts for random and informed versus balanced; interpret these as exploratory.
- Percentile bootstrap, 2,000 replicates; resample **whole episodes** within each of the 12 fixed initial-cell strata, maintaining matched replicate indices across the compared policies; the across-budget primary contrast uses matched draws per stratum across all budgets. Do not resample 555 within-cell SLA measurements. This quantifies trajectory/initialization randomness **inside the fixed finite archive**, not uncertainty over new independent provider worlds.
- RNG seed 20261105; distinct random streams by (budget, starting cell, replicate, policy). Results and action histories saved to an output directory outside the PRAISE repository; output SHA hashes and source manifest SHA hashes stored in run_manifest.json.

## Source/provenance gates

All seven methods must be loaded from three saved evaluation stages with frozen matching SHA-256 checks:

- Phase II: results/06_evaluation_v3b_fullsupport/primary_metrics.csv (M1, M2, M3_FULL343).
- Original-style: results/b1_pilot_m3_retrospective_v1/evaluation/metrics_retrospective.csv (ORIGINAL_TOP14_B1400, ORIGINAL_TOP1_B1400). The retrospective prediction-freeze SHA is checked.
- Fixed-CV: results/b1_fixed_cv_top1_top14_b1400_v1/evaluation/metrics.csv (FIXED_CV_TOP14, FIXED_CV_TOP1).

Demand exactly one valid n=555 cell-MAE value per action and 84 actions total. Reconcile the seven aggregate means to the internal report within 0.00006 to allow published rounding. Missing files, changed hashes or mismatches **abort**; never impute missing cell results using aggregate tables.

## Boundaries

Only B1.a evaluation-count budgets are studied. No new graph or provider simulations; no claim of wall-clock efficiency, optimal policy, novel best-arm theory, independent-world generalization, or sim-to-real validity. The saved action histories will allow a future incremental-budget extension, **but extension behavior is not evaluated here**. No new method variants or tuned switch points are to be introduced into this v1 comparison after seeing its outcomes.
