# PRAISE / Plan B — B1 sequential-validation design freeze (v1)

**Status:** DESIGN FROZEN for the next retrospective development comparison  
**Freeze date:** 2026-11-05  
**Scope:** Within-domain algorithm selection using the archived eligible Phase-5 PRAISE battery. This is a protocol freeze, **not** an empirical validation or a freeze of an executable acquisition algorithm.

## Research question

> Under predetermined, limited validation budgets, can budget-aware sequential evaluation of algorithm–world–graph configurations reduce the expected loss of the final algorithm-selection decision compared with nonadaptive and budget-independent validation strategies?

The object is **terminal decision quality under a finite budget**. We are **not** rewarding good choices *during* the evaluation episode, and do not claim that more evaluations improve the underlying algorithms' predictive accuracy.

## Six agreed design principles

### 1. Fixed experimental domain and explicit estimand

The intended full catalogue is seven frozen predictor variants:

- `M1`
- `M2`
- `M3_FULL343` (Phase II V3b)
- `ORIGINAL_TOP14_B1400` (retrospective original-style, inherited lambda)
- `ORIGINAL_TOP1_B1400` (retrospective original-style, inherited lambda)
- `FIXED_CV_TOP14` (fixed support after public-I1 CV)
- `FIXED_CV_TOP1` (fixed support after public-I1 CV)

The eligible domain consists of the three provider worlds `P1`, `P3`, `P4` and four composition graphs `G_PAR`, `G_SEQ`, `G_PARSEQ`, `G_SEQPAR`: **12 world–graph cells**. Thus the intended action catalogue contains **7 × 12 = 84** possible evaluations. **M0 is excluded** because its numerical output does not cover the same full evaluation population. The earlier five-method replay (60 actions) is explicitly **development evidence only**, not the seven-method study.

The target estimand is each algorithm's equal-cell average of cell-level MAE on the frozen 12-cell domain:
`mu(a) = (1/12) * sum_{cell in E} MAE(a, cell)`.
Each cell contains 555 related SLA query–horizon measurements; those 555 measurements are **not** 555 independent cell observations. All seven methods must be verified on exactly the same 12 cells before the full study is called complete.

Adding a provider world or graph changes the target domain and estimand and requires a new version. Adding algorithms changes the candidate set and likewise requires a new version, rather than silently extending B1.

### 2. One atomic evaluation, with information revealed only on selection

An action is one previously unobserved `(algorithm, provider world, composition graph)` triple. The evaluator reveals that action's frozen cell-MAE result **only after the policy selects it**. Previously unselected results must never enter policy state, fitting, acquisition or tie-breaking. An action cannot be evaluated twice in the archival finite-population replay.

Every competing policy has the same initial evidence, action admissibility rules and final-decision estimator. For the development replay, the common initialization evaluates every candidate algorithm on the **same starting cell**, counts these evaluations against the budget, and varies/stratifies the starting cell across trials. Any change to initialization must be separately versioned and consistently applied.

### 3. Prespecified finite budgets; independent budget-conditioned episodes

For the next controlled development experiment, the **preselected evaluation-count budgets** are

**B ∈ {10, 15, 20, 30, 40} atomic actions.**

Each B defines a **separate episode from initialization**. Policies receive B at the outset, cannot exceed it, and recommend an algorithm upon exhausting it. A result at B=15 is **not** merely an intermediate sample from an otherwise identical 40-action episode. Because these budgets were agreed after preliminary Gate 1 results were inspected, they are **prespecified for the next comparison, not prospective relative to the archive**.

The complete catalogue comprises 84 evaluations (60 in the five-method development subset); therefore none of these test budgets exhausts the available evaluation population.

### 4. Decisions may depend on the remaining budget; terminal regret is primary

At step t, a budget-aware policy may use the evidence already acquired and the remaining allowance `B-t`:

`u_(t+1) = pi(D_t, B-t)`.

Its exploration/targeted-discrimination behavior may change within the episode. The principal scientific comparison must include at least one *fully specified* budget-aware candidate whose behavior can depend on remaining budget. Uniform random ordering, balanced coverage, and the existing budget-independent informed policy remain **valid controls**; controls need not artificially depend on B.

Let `a* = argmin_a mu(a)` under the frozen complete-domain reference and `a_hat_B` be the terminal selection. The **primary outcome** is expected simple regret
`R(B) = E[mu(a_hat_B) - mu(a*)]`.
The **secondary outcomes** are reference-best selection probability `P(a_hat_B = a*)` and the terminal regret distribution, including a specified upper-tail quantile. The reference is used only by the **evaluator** after the policy has issued its terminal decision, never to train or inform the policy.

All acquisition rules, posterior/estimator settings, tie-breaking rules and stopping conditions must be specified and committed **before** producing the comparative results. The B1 *design* is frozen now; the **executable budget-aware candidate rule has not yet been frozen** and must not be retrospectively described as prespecified.

### 5. Same evaluation conditions; distinguish action-count and actual computation budgets

All policies use the same dataset, revealed-action interface, common starting conditions, allowed catalogue and terminal scoring procedure. They are compared at **identical B** for each budget-conditioned experiment. Final recommendation quality is not conflated with cumulative quality during evaluation.

- **B1.a (immediately executable):** one action counts as one unit of budget. This is a proxy, not a claim of equal computational cost.
- **B1.b (conditional):** use cumulative **marginal computational cost** (including documented reusable setup and cell-specific reference expenses where appropriate) if the cost audit can allocate these costs reliably to actions and histories. A cost-aware policy must be re-run under this budget; simply relabeling the horizontal axis of an action-count trajectory is not a genuine B1.b comparison.

The current Phase II prediction manifests bundle M1/M2/M3 wall-clock times per cell, so the existing audit **does not yet support trustworthy method-specific marginal-hour estimates**. Report B1.a separately and do not claim actual-hour efficiency without reconciling B1.b.

### 6. Statistical evaluation is essential for *every* policy

For each **preselected budget**, use repeated, independently randomized **episodes**, particularly for the purely random baseline. A single random trajectory does not characterize random selection. Randomize evaluation orders/seeds and vary the starting cell under the same stated design. Analyze **terminal** outcomes over the repeated episodes:

- Mean simple regret, with uncertainty intervals.
- Probability of choosing the full-reference best, with uncertainty intervals.
- Regret distribution, including upper-tail behavior.
- Differences across the entire preselected budget set, not isolated favorable budgets.

Use paired conditions (same starting cell and controlled RNG design) for policy contrasts when feasible; bootstrap at the **whole-episode level**, never at the level of 555 correlated query–horizon rows or resampled steps within a trajectory. Generate independent random sequences first; bootstrap cannot create independent sequences from a single trajectory. If several episodes share the same starting cell and deterministic policy, report the effective diversity honestly.

Intervals from repeated replay sequences quantify **sequence/random-initialization variability inside the fixed archive**, not generalization to independent provider worlds. A WB-reference split, if performed, distinguishes reference noise but still does not provide new independent worlds. Multiple budget-specific contrasts are exploratory unless multiplicity and primary contrasts are prespecified.

## Controls, development comparisons and stopping discipline

The initial controls are **random**, **balanced coverage**, and the **existing informed policy** (a budget-independent diagnostic). The first substantive candidate should be a **simple, reproducible, budget-conditioned rule**; advanced kernels, free-energy objectives, hypervolume acquisition, and elaborate optimizers are not part of the B1 design. Avoid optimizing a transition point post hoc and calling it prespecified.

Every strategy must yield a terminal decision at every selected B, and the complete curve across selected budgets is reported. A claim of superior performance requires a meaningful improvement in **terminal simple regret**, not merely the highest selection accuracy at one hand-picked B. Cost consequences remain conditional on the audit.

If the simple policy cannot outperform strong coverage/racing-style controls reproducibly, **stop method proliferation** and consolidate the negative/competitive result instead of adding complexity to chase a score. Positive development evidence should motivate independent confirmation with new provider worlds or configurations before general claims.

## Provenance and non-claims

- This design does **not** retroactively preregister Gate 1/B1.2, which already inspected this archive and suggested the present questions.
- The five-method pilot was a retrospective readout from archived fixed outcomes, and 180 replays do not constitute 180 independent provider worlds.
- The 12 cells are a finite eligible domain, originally selected after a Step-0 gate; excluded P2 cases are not implicitly covered.
- Predictor simulation budgets differ (e.g., M1:100, M2:2700, M3 FULL343:1400 graph trajectories per cell), so equal evaluation counts do not imply cost matching.
- The seven-method archive must pass completeness and provenance checks before being treated as the reference population. The prior original-style variants' per-cell metrics must be located and reconciled rather than assumed from aggregate MAE.
- The protocol is a **methodology development design**, not a proof of optimal acquisition, an identifiability theorem, or sim-to-real validity.

## Change-control rule

This file is **version 1** of the agreed design. Any substantive modification to the six principles, evaluation domain, budget grid, primary metric, or comparison rules must be proposed explicitly and committed as a **new version** with its rationale. Executable policy definitions, independent reference splitting and randomization details are next implementation specifications, not silently implicit in this design freeze.
