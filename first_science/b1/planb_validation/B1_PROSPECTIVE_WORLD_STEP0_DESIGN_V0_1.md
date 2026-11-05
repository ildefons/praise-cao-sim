# PRAISE B1 — Prospective world generator and Step-0 eligibility design v0.1

**Status: scientific design DRAFT for review; NOT FROZEN FOR EXECUTION.**  
**Date:** 2026-11-05. **No new-world simulation, Step-0 calibration, WB evaluation or B1-policy change is authorized.**

- Proposed machine-readable contract: [B1_WORLD_GENERATOR_DRAFT_V0_1.json](B1_WORLD_GENERATOR_DRAFT_V0_1.json)
- Deterministic, simulation-free sampler: [preview_new_worlds_v0_1.py](preview_new_worlds_v0_1.py)
- Synthetic tests: [test_preview_new_worlds_v0_1.py](test_preview_new_worlds_v0_1.py)
- Prior evidence: [development freeze](B1_FIVE_BUDGET_DEVELOPMENT_RESULTS_REVIEW_V1.md), [WB robustness freeze](B1_WB_ROBUSTNESS_RESULT_FREEZE_2026-11-05.md), [independent-world feasibility scope](B1_INDEPENDENT_WORLD_VALIDATION_SCOPE_V0_1.md), [cost review](B1_WORLD_COST_LOCAL_EVIDENCE_REVIEW_2026-11-05.md).

## 1. Scientific target and limited transfer claim

Question: **within the same Gamma-service, one-server FCFS provider family, does the frozen B1 budget-aware Top2 acquisition policy improve terminal simple regret relative to balanced allocation on *new physical configurations*?**

This is a **local within-family transfer test**, not evidence for arbitrary computing-continuum configurations, new provider-family distributions, different numbers of providers, graph grammar changes or a different SLA interface.

An independent validation *battery* consists of one independently drawn and Step-0-eligible physical provider world in each of three roles, crossed with the same four graphs `G_PAR/G_PARSEQ/G_SEQ/G_SEQPAR`. Exactly 12 world×graph cells and 7 predictor algorithms yield the required 84-cell-complete reference. The role labels `P1/P3/P4` are **controller design-matrix categories**; new physical values are *not* the original historical P1/P3/P4.

The predictor algorithms, acquisition policy, posterior and terminal estimator, all four controls, and five budgets **B = 10, 15, 20, 30, 40** remain frozen. A new-world adapter must make the existing selection functions consume new 7×12 per-battery data without importing the old archived evaluation values. The new battery's true best algorithm is computed separately: it need not be M3_FULL343.

## 2. Proposal: role-stratified physical-world distributions

The historical world template sets ProviderA = D(1−δ), ProviderB = D, ProviderC = D(1+δ); instruction CV=0.3; effective IPT=10^9 instructions/s; execution fraction x=0.5; W0 period 0.2 s. One-server FCFS, cost rate, quality and graph ASTs remain unchanged.

| Role label | Interpretation | Proposed uniform D range (million instructions) | Proposed δ |
|---|---|---|---|
| P1 | Lower-load homogeneous | **320–340** | Exactly **0** |
| P3 | Higher-load homogeneous | **350–370** | Exactly **0** |
| P4 | Higher-load heterogeneous | **350–362** | Uniform **0.060–0.095** |

**These bounds are proposed choices, not empirical confidence intervals or historically frozen values.** They are constrained to a neighborhood of the previously successful P1/P3/P4 conditions, for a relatively economical *first transfer test*. They intentionally do not include the historical failing P2 role. This design is narrower than a claim of robustness to arbitrary heterogeneity, near-overload and unfamiliar service distributions. It would be inappropriate to report it as broad population generalization.

Sampling independently per (battery, role, attempt), using a SHA-256-derived PRNG seed. The sampler rounds D to integer instructions and δ to 6 decimal places; exact collisions or accidental equality to any historical physical world raise errors instead of automatic redraws. The known **physical** constraint (before any Step-0 simulation) is:

\[
  \widehat{u}_{\max} =
  \frac{D(1+\delta)\,x}{\mathrm{IPT}\,T_W}\leq 0.995
  \]
where x=0.5, IPT=10^9 and T_W=0.2 s. The proposed P4 upper corner gives approximately 0.991. This is a stability cap based on the source model, **not a surrogate for Step-0**. No candidate may be repaired, clipped or selected using method performance or hidden WB outcomes.

Maintain both the private physical parameters (available only to the scientific simulator) and public-I1 cards (available to predictor generation) in separated, hashed namespaces. The B1 acquisition controller may see only its permitted revealed algorithm×cell errors, **never** D, δ, true provider means or reference WB.

## 3. Recruitment: exact four-graph Step-0 gate

For each prospective role candidate, preserve the **original** `run_phase5_step0_v2.py` eligibility semantics in a new-world-compatible adapter:

1. Produce and freeze public-I1 cards from disjoint region (100) and sigma (100) evidence trajectories. Reuse cards across the four graphs for that physical world.
2. For each graph, use **200 calibration graph-WB trajectories**, the original scale grid **0.50 to 2.00 in 0.01 increments**, original five rho labels/values and the original Easy [0.95,1], Mid [0.75,0.90] and Stress [0.40,0.75] target bands.
3. Select exactly **15 queries** (five rho values × three regimes). At each rho, require ordered scales **s_Stress < s_Mid < s_Easy** and at least **0.10** separation between adjacent mean sigma values over the H=60..240 s diagnostic range (the original 37-point grid).
4. Freeze the selected queries; then score them using **200 disjoint confirmation trajectories**. Require every query to stay in its own regime band and preserve the adjacent ≥0.10 gaps. **No new scales, no fallback query, no parameter repair and no reselection after failure.**
5. A physical world is **eligible only when all four graph cells have frozen `FROZEN_PHASE5_STEP0_PASS_V2`**. A calibration failure or `GATE_FAILED_STEP0` for even one graph makes that candidate ineligible for a *complete 12-cell B1 reference battery*. Preserve failures, diagnostics, seed evidence and hashes even when the battery ultimately cannot be completed.

This new *world-recruitment condition* is distinct from the original Phase-5 rule (which merely excluded failed cells and continued the other cells). We are explicitly targeting **four-graph-eligible new-world distributions** to preserve B1's unchanged 7×12 target. This is conditioning on Step-0 and changes the population being studied; it is not evidence about the unconditional draw distribution.

## 4. Bounded, outcome-blind recruitment

For each prospective validation battery and for each role, sample and hash a list of up to **4** candidates **before any Step-0 simulation**. Try candidates in their predetermined attempt order. Select the **first** candidate passing *all four* Step-0 graph cells. Every attempted candidate receives an immutable disposition and its exact failure reasons. The sampler's deterministic candidate sequence never depends on Step-0 outcomes.

A later candidate may be selected only after the previous candidate's gate has a final, recorded failure. Incomplete/missing status blocks progression (fail closed). If a role has no eligible candidate by the cap, mark the entire proposed battery **INCOMPLETE** and record attempt counts/cost; **do not** silently replace the battery or change the design to obtain a favorable result. Later independent batteries are separate, predetermined draws. Any stopped/unattempted candidates remain distinguishable from failures.

This is **predeclared conditional recruitment**, not cherry-picking based on B1 regret or method scores; reporting *all* attempted draws, failures and observed eligibility yield remains essential. The finite cap of 4 is provisional and must be reviewed against attrition/cost before execution, not changed based on confirmation outcomes.

One example dry-run configuration generates three prospective batteries × three roles × four candidate attempts = **36 UNASSESSED physical candidates**. **Three is solely a sampler preview size, not a statistical power calculation or proposed confirmation sample size.**

## 5. Statistical estimand and independence

For each complete independent battery, compute each algorithm's equal mean MAE over its own 12 cells and identify that *battery's* lowest-mean algorithm. Replay the unchanged B1 acquisition and controls at each of the five budgets, with the same number of random episodes and paired starts.

Define \(\Delta_b\) as the equal-budget mean of *Top2 minus balanced* expected simple regret within battery \(b\). The primary effect across independent batteries is \(E_b[\Delta_b]\), with uncertainty estimated over **independently sampled batteries**. Do not bootstrap individual query-horizon points, graph cells, policy sequences or white-box trajectories as though they were independent worlds. Report battery-level heterogeneity, relative improvement as secondary and all four selection accuracies.

Each incomplete recruitment battery counts toward **eligibility yield and cost**, but produces no complete 84-reference decision regret; conditioning on full eligibility must be explicit. Do not retrospectively move the confirmation target to a smaller collection of graphs or methods.

## 6. Engineering requirements before *any* new simulation

**Unresolved blocker:** historical Phase-5 scripts and data directories are tied to fixed P1/P2/P3/P4 world catalogue and legacy `results/` paths. The deterministic preview **is not a runnable Phase-5 adapter**. Before generating public-I1 or Step-0 scientific data, build and test a new adapter that:

- Reads an immutable single-battery provider-world manifest; exposes its **role labels** P1/P3/P4 without conflating them with historical physical worlds.
- Writes to a fully isolated new-battery evidence root; verifies no writes to existing frozen outputs. Do not edit legacy scientific configs or policy code in place.
- Uses separately frozen **nonoverlapping seed namespaces across independent batteries and stages**; preserves within-battery common-random-number conventions and reconstruction/algorithm definitions.
- Verifies the Step-0 15-query selection, status semantics, trajectory totals, per-graph confirmation manifests and private/public leakage firewall before accepting any role.
- Freezes all seven method predictions in each complete new 12-cell battery before unlocking an independent WB reference. Enforces full 7×12 numerical completeness and data provenance.
- Invokes the **unchanged** B1 policy functions on *new* battery arrays, with no use of the prior finite 12-cell development matrix. Validates array role/graph ordering and method labels.
- Has an engineering smoke test on **synthetic or throwaway** data before science, with simulator/adapter source and dependency versions pinned.

## 7. Cost / next decision gate

For one successful battery (three candidate worlds, no failures), frozen work includes 600 I1 trajectories, 4,800 Step-0 graph trajectories, 117,600 graph predictor trajectories, 12,000 final-WB graph trajectories, plus substantial provider candidate preparation and unrecovered setup costs. Four-attempt recruitment could incur additional I1 and Step-0 screening expenses; no practical confirmation sample count is justified yet.

**Next gates, in order:** (i) review/finalize physical sampling bounds and what population they represent; (ii) approve conditional recruitment and attempt cap or change the estimand **before** simulation; (iii) implement the isolated new-world adapter and independent seed namespaces; (iv) examine realistic full-battery cost and eligibility yield, with any separate sizing pilot clearly marked exploratory; (v) freeze primary analysis and sample size; **then** authorize confirmation if viable.

**Current status: DRAFT READY FOR REVIEW, independent-world simulation NO-GO.** Continuing an existing B1 episode with additional acquisition budget remains postponed.
