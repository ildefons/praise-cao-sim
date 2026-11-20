# B1: structured-Gaussian-prior sensitivity audit (v1)

**Date:** 20 November 2026  
**Status:** prespecified sensitivity grid and read-only replay code; **awaiting user execution on laptop**  
**Purpose:** determine whether the paper's substantive policy conclusions are fragile to the heuristic prior standard deviations, assumed residual scale, or intercept mean.

## Why this audit is necessary

The three original scales `tau_alpha=0.12`, `tau_world=0.07`, `tau_graph=0.045` and the working residual SD `sigma=0.055` were inherited from the retrospective Gate 1 probe. Its original file states that these were heuristic, not fitted or calibrated. However, the three-method historical MAE table was already available at Gate 1; the surviving record does **not** establish that human choice of these numbers was independent of that table.

The code-level information boundary is separate: at each step an acquisition selector receives only revealed method–condition MAEs. This audit addresses **hyperparameter robustness**, not a historical proof of absence of informal prior-selection bias.

## Frozen design, before inspecting sensitivity outcomes

- **Two reference archives:** exactly the existing historical and fresh-reference 7×12 MAE matrices; their SHA-256 values are verified by `b1_nested_budget_replay_v1.py`.
- **Nine policies:** Random, Balanced, Informed, joint one-step KG, two-stage adaptive KG, two-stage uniform KG, original budgeted Top2, two-stage adaptive Top2, and two-stage uniform Top2.
- **Same posterior within each scenario:** all policies use an identical per-method additive Gaussian prior and residual variance. No policy-specific tuning.
- **No changed acquisition criteria:** import original selection/posterior functions from the frozen project code. Only replace the five hyperparameters **in memory** under a restore-on-exit scope. Reuse the existing documented seven-row B=80 Balanced compatibility fix.
- **Same episode design:** 12 initial conditions × 20 replicate indices × 2 archives. The six budget-independent policies have one trajectory to budget 80, evaluated at 13 nested prefixes; all three Top2 policies are rerun separately at each budget using their existing budget-dependent random streams.
- **Budgets:** 10, 15, 20, 25, 30, 35, 40, 45, 55, 65, 70, 75, 80 distinct action evaluations.
- **Primary estimand:** unweighted mean terminal simple regret across these thirteen budgets. Each evaluation outcome is revealed only after the policy selects that action; full matrices are used for retrospective scoring.
- **No physical simulation / no white-box generation / no changes to existing reference results or paper.**

### Prior sensitivity scenarios

The base prior parameters are standard deviations, not variances. `intercept_mean` is the mean of each method's intercept prior, shared across methods; the other coefficient means remain zero.

| Scenario | tau_alpha | tau_world | tau_graph | sigma | intercept_mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| base | 0.120 | 0.070 | 0.0450 | 0.0550 | 0.17 |
| intercept_half | 0.060 | 0.070 | 0.0450 | 0.0550 | 0.17 |
| intercept_double | 0.240 | 0.070 | 0.0450 | 0.0550 | 0.17 |
| world_half | 0.120 | 0.035 | 0.0450 | 0.0550 | 0.17 |
| world_double | 0.120 | 0.140 | 0.0450 | 0.0550 | 0.17 |
| graph_half | 0.120 | 0.070 | 0.0225 | 0.0550 | 0.17 |
| graph_double | 0.120 | 0.070 | 0.0900 | 0.0550 | 0.17 |
| noise_half | 0.120 | 0.070 | 0.0450 | 0.0275 | 0.17 |
| noise_double | 0.120 | 0.070 | 0.0450 | 0.1100 | 0.17 |
| world_graph_swap | 0.120 | 0.045 | 0.0700 | 0.0550 | 0.17 |
| all_prior_half | 0.060 | 0.035 | 0.0225 | 0.0550 | 0.17 |
| all_prior_double | 0.240 | 0.140 | 0.0900 | 0.0550 | 0.17 |
| mean_low | 0.120 | 0.070 | 0.0450 | 0.0550 | 0.10 |
| mean_high | 0.120 | 0.070 | 0.0450 | 0.0550 | 0.24 |

The factors 0.5×/2× stress magnitude across a broad range; swapping world/graph tests the substantive hierarchical ordering. The mean scenarios check whether the starting MAE level matters. This is a **fixed finite sensitivity grid**, not a hyperparameter search. No favorable variant will be selected for the paper's primary figures.

## Mandatory internal reproduction check

For `base` with 20 repeats per start, all **234 mean regrets** (2 archives × 9 policies × 13 budgets) must match the already committed `paper_systems/data/combined_nine_policy_budget_summary.csv` to absolute tolerance `1e-11`. A failure **stops** the audit: the sensitivity comparison is not a faithful re-execution of the original policy experiment and must be diagnosed before interpreting any case.

All scenarios validate exact episode counts and unique `(archive, policy, budget, start, replicate)` keys; manifests contain SHA-256 hashes of source matrices and generated ledgers. Already completed scenarios may be reused only when their recorded design and all output hashes pass verification. The script never silently overwrites an existing output.

## Interpretation gates (decided before results)

Primary questions, assessed for **each** archive and every one of the fourteen scenarios:

1. **Adaptive condition selection:** is the thirteen-budget mean regret of two-stage adaptive KG lower than uniform two-stage KG? Report number of scenarios with a negative difference, full range of effect sizes, and nominal exploratory bootstrap intervals.
2. **Information-acquisition value:** is adaptive KG better in mean regret than Random and Balanced? Report each comparison's sign over all scenarios; if reversals occur, the corresponding claim is prior-sensitive.
3. **Competitive performance:** compare adaptive KG with the *best observed* of the three Top2 policies in every scenario; report the range of absolute differences, the worst adaptive/Top2 regret ratio, and adaptive KG's rank among all nine policies. An observation that adaptive KG is no longer the best is **not** automatically a failure of competitiveness, but it does prevent an unconditional statement that it is the best.
4. **Posterior prior strength:** compare each individual and joint scale perturbation, and the world/graph ordering reversal, to identify influential assumptions. The mean and residual-noise scenarios must be included in the conclusion.

The condition "all sign comparisons unchanged over this prespecified grid" supports **robust direction within the tested prior range**, not mathematical proof of prior independence, robustness to every possible hyperparameter value, or an independent prospective confirmation. Do not equate non-significant differences with equivalence. The fresh-reference archive independently resamples white-box trajectories but retains the same methods and conditions.

### Uncertainty and randomization

The summary stage uses independent policy bootstrap draws within the same initial-condition strata. For the six nested policies, one replicate resampling is reused over all thirteen budget prefixes. For Top2, each budget is a separately seeded episode design and is resampled separately. Bootstraps are conditional on the two fixed MAE matrices. The script reports nominal 95% exploratory confidence intervals for each scenario's contrasts, **not** familywise simultaneous inference over all fourteen sensitivity cases. The existing manuscript's adjusted primary contrasts remain the primary inferential analysis.

## Local execution (user laptop only)

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/test_b1_prior_sensitivity_replay_v1.py -v

python first_science/b1/planb_validation/b1_prior_sensitivity_replay_v1.py \
  --historical-matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --fresh-reference-matrix first_science/b1/planb_validation/results/b0001_original_policies_v1/01_baseline/seven_method_matrix.csv \
  --out-root ~/praise/planb_b1_prior_sensitivity_2026_11_20_v1 \
  --preflight-only
```

**First, reproduce the baseline:**

```bash
python first_science/b1/planb_validation/b1_prior_sensitivity_replay_v1.py \
  --historical-matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --fresh-reference-matrix first_science/b1/planb_validation/results/b0001_original_policies_v1/01_baseline/seven_method_matrix.csv \
  --out-root ~/praise/planb_b1_prior_sensitivity_2026_11_20_v1 \
  --scenarios base
```

Only continue if the log contains `PRIOR_BASE_REPRODUCES_ALL_234_PAPER_MEANS` and `B1_PRIOR_SENSITIVITY_REPLAY_PASS`.

**Then run all prespecified scenarios** (the verified base output is skipped automatically):

```bash
python first_science/b1/planb_validation/b1_prior_sensitivity_replay_v1.py \
  --historical-matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --fresh-reference-matrix first_science/b1/planb_validation/results/b0001_original_policies_v1/01_baseline/seven_method_matrix.csv \
  --out-root ~/praise/planb_b1_prior_sensitivity_2026_11_20_v1 \
  --scenarios all
```

The full grid replays nine acquisition policies across two archives and may require a substantial local compute session. Each successfully completed scenario is finalized separately, so a rerun verifies and skips completed scenarios without overwriting them. Unexpected incomplete scenario folders are left untouched and reported rather than deleted.

**Finally, audit the grid:**

```bash
python first_science/b1/planb_validation/b1_prior_sensitivity_replay_v1.py \
  --analyse-only \
  --out-root ~/praise/planb_b1_prior_sensitivity_2026_11_20_v1 \
  --analysis-out ~/praise/planb_b1_prior_sensitivity_2026_11_20_v1/analysis
```

The interpretation inputs are:

- `analysis/prior_sensitivity_decision_table.csv`: thirteen-budget aggregate regret of each key policy, best Top2, absolute/relative margins, adaptive policy rank, and sign-stability indicators.
- `analysis/all_scenario_aggregate_contrasts.csv`: exploratory bootstrap intervals for adaptive KG against each of the eight competitors, separately by archive and scenario.
- `analysis/sensitivity_analysis_manifest.json`: hashes, complete scenario grid, and uncertainty-scope declaration.

**Before editing the manuscript**, review the sign/rank/margin ranges across all scenarios and determine whether the central conclusions remain justified, need narrower scope, or fail the sensitivity gate. No paper changes are authorized by this protocol alone.
