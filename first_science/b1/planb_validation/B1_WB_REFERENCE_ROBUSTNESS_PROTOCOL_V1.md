# PRAISE B1 — White-box reference robustness protocol v1

**Freeze date:** 2026-11-05. **Status:** post-result, development-only robustness protocol. The B1 v1 acquisition rules, five budgets, and their original results remain unchanged.

## What is frozen

The positive five-budget development result is preserved in [B1_FIVE_BUDGET_DEVELOPMENT_RESULTS_REVIEW_V1.md](B1_FIVE_BUDGET_DEVELOPMENT_RESULTS_REVIEW_V1.md). Its seven-method matrix has SHA-256 `0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d`. The selection-policy implementation is the existing `b1_budget_comparison_v1.py` and [B1_EXECUTABLE_POLICY_FREEZE_V1.md](B1_EXECUTABLE_POLICY_FREEZE_V1.md). This stage must never change either, tune the switching point, alter algorithms' predictions, or overwrite original outputs.

## Two white-box sensitivity tests

**Test A — trajectory-bootstrap reference sensitivity.** Use the frozen 1,000 binary white-box trajectory outcomes per cell and the pointwise predictions for **all seven algorithms**. Resample **complete trajectory indices**, not any of the 555 mutually dependent query–horizon columns. Apply each index draw jointly to the 12 cells (the original Phase-5 WB bootstrap convention), and score every algorithm against the same resampled references. Check that recomputed original 84 MAEs match the archived frozen matrix before proceeding. Default: **300 independent resampling draws**, RNG seed **20261106**.

Calculate, for each draw, the winning algorithm and the M2–M3 margin. Rescore the **originally frozen terminal recommendations without modifying policy decisions**, yielding a new reference-uncertainty distribution for the prespecified primary contrast: `budgeted_top2 minus balanced`, mean terminal simple regret across `B=10,15,20,30,40`. This tests **scoring-reference uncertainty**, conditional on original recommendations, not the effect of reference noise on which experiments would be chosen.

**Test B — disjoint-half selection stress test.** Repeat **4 random 500/500 partitions**, both orientations. For each partition, calculate algorithm×cell MAEs independently from one WB half and from the other. Run the unchanged random, balanced, informed, and budgeted Top2 selection rules with one half supplying only **revealed experimental observations**; score the final recommended algorithm against the **disjoint second half**. Repeat **2 random episodes for each of 12 common starting cells**, for each of the five frozen budgets and four policies. This uses **3,840 total policy episodes**. It tests sensitivity of the **whole decision process** to noisier reference estimates while maintaining a scoring firewall. Its 500-trajectory observations deliberately have more noise than B1's original 1,000-trajectory observations.

Both tests use existing frozen provider worlds and methods, so **neither constitutes validation on independent worlds**.

## Predeclared interpretation gate (screening, not a new hypothesis test)

Consider a prospective new-world confirmation study **only if** the following hold:

1. The original seven-method 84-cell MAE matrix is reproduced from frozen pointwise predictions and complete WB trajectories, without mismatches.
2. The original winner is retained in at least **90%** of the 300 reference-bootstrap draws.
3. The 95% percentile interval for the reference-rescored **across-budget Top2-minus-balanced contrast** lies entirely below zero.
4. The **aggregate mean** Top2-minus-balanced regret is negative in the disjoint-half policy reruns. The split sample is small, so do not make significance claims from four overlapping partitions.

These are decision-screening rules chosen after the original B1 development results, not prospective world-level significance criteria. Failure calls for diagnosing instability or reporting the conditional finding, **not optimizing the existing acquisition function until it wins**. Passing only justifies **planning** an independent new-world study, whose world count, power, computational costs, seed banks, candidate generation and stopping rules require a separate freeze **before** any new simulation or tuning.

## Nonclaims

- No independent-world, real-world or sim-to-real inference.
- No per-method execution-hour comparison.
- No joint confidence interval combining WB uncertainty, stochastic evaluation-policy randomness and world sampling; these are distinct sources of variation.
- Resampling the 1,000 WB trajectories does not make new provider worlds.
- The same existing data motivated the v1 policy; this analysis cannot erase that development history.
- A future continuation study if extra budget becomes available is deliberately postponed until after this gate and any justified independent validation.
