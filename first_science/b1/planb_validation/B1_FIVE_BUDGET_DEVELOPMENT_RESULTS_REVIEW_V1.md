# PRAISE Plan B — B1 five-budget development result review (2026-11-05)

**Status:** retrospective development finding, not independent confirmation.  
**Protocol:** [B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md](B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md)  
**Executable policy freeze:** [B1_EXECUTABLE_POLICY_FREEZE_V1.md](B1_EXECUTABLE_POLICY_FREEZE_V1.md)  
**Replay:** `b1_budget_comparison_v1.py`, source branch `praise-identifiability-feasibility`.

## Evidence received and audit

The local user run passed six synthetic unit tests, then reported
`SEVEN_METHOD_MATRIX_VERIFIED 7 methods x 12 cells = 84 atomic evaluations`.
Its printed matrix SHA-256, and the uploaded `seven_method_matrix.csv`, match:

`0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d`

The uploaded `run_manifest.json`, `budget_summary.csv`, `paired_regret_contrasts.csv`,
`terminal_episodes.csv`, `episode_action_history.csv` and matrix/provenance files
were inspected. All five provided replay output CSV hashes match
`run_manifest.json`. Independent recomputation from the uploaded files confirmed:

- 7 methods × 12 eligible cells, with an equal-cell average MAE.
- 5 fixed budgets **10, 15, 20, 30, 40** out of 84 possible actions.
- 12 initial cells × 20 randomized repeats = **240 episodes per policy per budget**.
- 4 policies × 5 budgets × 240 = **4,800 terminal episodes**.
- **110,400** archived action rows, exactly the expected budget total.
- All episodes respect their budgets and contain no repeated action.
- Every episode initially evaluates each of the seven algorithms at one shared cell.
- Saved simple regret equals archived complete-domain MAE of the recommendation
  minus the complete-domain best, within floating-point precision.

The seven full-domain means are M1 .157015; M2 .133951; M3_FULL343 .121890;
original-style Top14 .154155; original-style Top1 .162280;
fixed-CV Top14 .160948; fixed-CV Top1 .192105.
Reference-best: **M3_FULL343**.

## Main result (lower terminal simple regret is better)

| Budget | Random regret | Balanced regret | Informed regret | Budget-aware Top2 regret | Top2 correct | Balanced correct |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | .017404 | .018516 | .018690 | **.015194** | 45.4% | 37.1% |
| 15 | .016812 | .011998 | .016087 | **.009799** | 57.1% | 55.4% |
| 20 | .013044 | .009917 | .008455 | **.006917** | 63.8% | 58.3% |
| 30 | .010159 | .005487 | .006120 | **.002925** | 81.3% | 68.3% |
| 40 | .007138 | .003632 | .001592 | **.000888** | 93.3% | 78.8% |

The **single predeclared primary contrast** is Top2 minus balanced, equal-weight
mean of expected terminal regret over the five budgets:

- Estimated difference **−0.0027652 MAE units**.
- Reported stratified, paired, 2,000-replicate percentile bootstrap interval
  **[−0.0036000, −0.0018985]**.
- Across these five budgets, balanced mean regret = **.0099098**;
  Top2 mean regret = **.0071446**; relative mean regret reduction **27.9%**.

The per-budget Top2 minus balanced differences and nominal 95% intervals are:

| Budget | Difference | Nominal bootstrap 95% interval |
|---:|---:|---:|
| 10 | −.003321 | [−.005992, −.000874] |
| 15 | −.002199 | [−.004377, −.000078] |
| 20 | −.003000 | [−.004983, −.000869] |
| 30 | −.002562 | [−.003949, −.001148] |
| 40 | −.002743 | [−.003805, −.001675] |

The intervals for individual budgets are **not adjusted for simultaneous
coverage across five comparisons**. Their bounds should not be presented as
five separate confirmatory tests. The B=15 interval is particularly close
to zero. The aggregate contrast was declared in the executable policy
freeze before this run.

At B=20 the informed heuristic has a **higher exact-winner proportion** than
Top2 (67.5% vs 63.8%), but **higher mean regret** (.008455 vs .006917).
This illustrates why terminal *simple regret*, not just exact winner
frequency, is the primary metric.

## Within-archive consistency diagnostics

Post-result checking of `terminal_episodes.csv` gives:

| Budget | Starting cells with lower Top2 mean regret | Higher | Equal |
|---:|---:|---:|---:|
| 10 | 8 | 3 | 1 |
| 15 | 8 | 3 | 1 |
| 20 | 10 | 2 | 0 |
| 30 | 9 | 3 | 0 |
| 40 | 11 | 0 | 1 |

Averaging each starting cell's Top2-minus-balanced contrast across all
five budgets gives 11 of 12 starting cells with negative difference;
the one other starting cell has a small positive difference. By
**starting provider world**, the average contrasts are P1 −.003031,
P3 −.001716, P4 −.003549. This is descriptive stratification, **not
a world-level significance test**.

## Interpretation and limitations

1. **Positive development result.** The simplest frozen budget-aware
   coverage-then-top-two strategy outperformed balanced coverage in
   *expected terminal regret* at all five studied budgets, with a
   negative predeclared aggregate contrast. This demonstrates that
   a simple finite-budget controller is worth investigating.
2. **No novelty claim yet.** Fixed-budget selection, racing and
   targeted discrimination already exist. These data do not
   establish a novel optimization principle, nor that this heuristic
   is optimal.
3. **Conditioned on one historical 12-cell archive.** Repeated
   episodes randomize starting cells and action selection; they do
   **not** generate 240 independent provider worlds. The bootstrap
   resamples random sequences within the **12 fixed starting-cell
   strata**. Its interval is not a confidence interval over unseen
   provider worlds or structural regimes.
4. **Model-based selection uses fixed heuristic priors**, not
   independently calibrated prediction-error distributions. The
   reference is the same finite WB-derived archive used throughout
   retrospective development. WB MC uncertainty and dependence of
   555 query–horizon values per cell are not handled by this replay.
5. **Costs are action counts only.** Not cost-matched in
   graph trajectories, reconstruction expenses or marginal
   computational hours; B1.b is still pending.
6. **Development history matters.** Earlier Gate1/B1.2 experiments on
   this archive motivated the budget-aware policy. Freezing it before
   this five-budget comparison prevents within-run score chasing
   but **does not make the outcome independent confirmation**.
7. **No continuation claim.** The action histories are saved,
   but extending a completed small-budget episode after receiving
   new budget has not yet been evaluated.

## Recommended decision

**Stop acquisition-rule changes for B1 v1 and preserve this positive
development result.** The next step should be an explicit scientific
quality gate: audit the statistical reference uncertainty and the
distinction between observational replay randomness and variation
across independent new provider worlds. A prospective transfer or
new-world holdout can follow if its cost is justified. Replaying this
same archive with additional tuned acquisition variants cannot
supply independent confirmation.

Do not overwrite the frozen B1 design or prior result artifacts.
