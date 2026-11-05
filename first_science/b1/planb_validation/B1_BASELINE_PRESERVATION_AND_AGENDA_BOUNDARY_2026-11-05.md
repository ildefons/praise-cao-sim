# PRAISE Plan B — B1 baseline preservation and research-question boundary

**Decision recorded: 2026-11-05.** **Status: B1 v1 DESIGN, EXECUTABLE POLICY, RANDOMIZED COMPARISON AND RESULTS PRESERVED.** This is a *governance record*, not a new experiment or a reanalysis.

## Canonical scientific question (unchanged)

> Under predetermined, limited validation budgets, can budget-aware sequential evaluation of algorithm–world–graph configurations reduce the expected loss of the final algorithm-selection decision compared with nonadaptive and budget-independent validation strategies?

Source: [B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md](B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md).

The target is **terminal decision quality under a finite number of nonrepeated algorithm×cell evaluations**. It is neither the optimization of underlying predictors nor proof that a particular prediction method is universally best.

## Immutable B1 v1 experimental reference

- Seven methods: `M1`, `M2`, `M3_FULL343`, `ORIGINAL_TOP14_B1400`, `ORIGINAL_TOP1_B1400`, `FIXED_CV_TOP14`, `FIXED_CV_TOP1`.
- Exactly twelve historic cells: P1/P3/P4 × G_PAR/G_PARSEQ/G_SEQ/G_SEQPAR.
- The complete archive is 84 unique method×cell observations. The archived `seven_method_matrix.csv` SHA-256 was verified as `0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d`.
- Four **equally subjected to repeated evaluation** decision strategies: `random`, `balanced`, `informed`, `budgeted_top2`.
- Five separately initialized, known budgets: `10,15,20,30,40`. Every episode starts with all seven algorithms evaluated on a common starting cell, counting as seven actions.
- **20 seeded episodes at each of 12 starting cells, per policy and per budget**, hence 240 per policy/budget and 4,800 total.
- **2,000 stratified bootstrap replicates for each policy's mean regret and probability of correct selection**, with paired differences against balanced and one predeclared equal-budget mean difference Top2−balanced.
- The identical Gaussian posterior/terminal-decision model and its heuristic hyperparameters remain unchanged.
- Policies are not identically stochastic: random selects a random unvisited action; the other policies are algorithmic and use RNG for tie-breaking. Their trial counts and bootstrap procedures are nevertheless equal.
- The **exact executable implementation is preserved**: `b1_budget_comparison_v1.py` (Git blob SHA-1 `b433e7d01da10dcad3448eedeea544ba7cefb33c` on the branch at the time this boundary was recorded).
- The original replay was completed on the user's local machine at `~/praise/planb_b1_fixed_budget_v1`. **Do not modify or overwrite that output directory**; it contains original source/output manifests, terminal episodes, action histories, budget summaries and paired contrasts. The local files' checksums were checked during the original evidence review but not recollected in this governance record.

## Positive development evidence (not new-world confirmation)

Original B1 Top2−balanced across-budget mean regret difference: **−0.0027652163** (95% **episode-bootstrap** interval **[−0.0036000084, −0.0018984935]**), a **27.9% reduction** in expected terminal regret on the fixed historical 12-cell archive. Top2 had lower mean regret than balanced at all five budgets. The complete reported results and within-archive limits are in [B1_FIVE_BUDGET_DEVELOPMENT_RESULTS_REVIEW_V1.md](B1_FIVE_BUDGET_DEVELOPMENT_RESULTS_REVIEW_V1.md).

The independent **white-box reference-uncertainty audit** remains a second frozen development milestone: original best M3 in 300/300 reference resamples; fixed-recommendation Top2−balanced contrast −0.002756, reference interval [−0.002853, −0.002647]; disjoint-half policy rerun contrast −0.003976. See [B1_WB_ROBUSTNESS_RESULT_FREEZE_2026-11-05.md](B1_WB_ROBUSTNESS_RESULT_FREEZE_2026-11-05.md). These checks do not constitute new provider-world confirmation.

**Interpretation boundary:** 240 episodes per policy/budget are seeded replay episodes, *not 240 independent provider-world draws*. Bootstrap intervals here concern within-archive episode randomness conditional on the frozen twelve-cell matrix; neither bootstrap nor reusing historical P1/P3/P4 justifies a population-level transfer claim.

## Changes explicitly NOT authorized

No edits to the original B1 v1 source, frozen predictor definitions, shared terminal estimator, policies, budgets, 20×12 repetition design, 2,000-bootstrap evaluation, existing archived metric matrix, episode histories, or frozen conclusions. New requirements discovered later must lead to a separately versioned independent study or a clearly labeled supplementary analysis; never silently replace the successful B1 v1 baseline.

A later DRAFT `B1_PROSPECTIVE_WORLD_STEP0_DESIGN_V0_1.md` proposed additional conditional world sampling. It is **not adopted as the new B1 question, not frozen for scientific execution, and not required for publication of the conditional B1 development result**. Its role-stratified parameter intervals and four-attempt recruitment rule remain only unapproved design alternatives. Do not run it or treat its assumptions as settled.

## Future discussion — not an execution directive

Discuss next steps in this order:

1. **Interpret and communicate** the preserved B1 randomized/bootstrapped outcome, provenance, decision-quality estimand and limitations in a concise scientific report.
2. **Assess the contribution and minimum validity threat** before launching new expensive simulations. In particular, investigate whether the apparent policy advantage transfers when the reference-best algorithm is *not always M3*, since on the original fixed archive M3 is the one best method by full-domain average. A hindsight fixed-algorithm rule is not a valid prospective baseline; any new comparison requires a separate, predeclared design.
3. **Only then decide** whether an independent, policy-unchanged confirmation study is worth its world-generation/eligibility/cost burden. Avoid unapproved narrow favorable-world recruitment and any post-result acquisition tuning.
4. Postpone **incremental-budget continuation** to a distinct new question/version once the scientific basis is clear.

This document preserves the existing result and its question; it does **not** approve new simulations, methods, policies, statistical estimands or worlds.
