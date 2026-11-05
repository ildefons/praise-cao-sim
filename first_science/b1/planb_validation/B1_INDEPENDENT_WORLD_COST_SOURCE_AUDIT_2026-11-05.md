# B1 independent-world validation — source-level feasibility audit (2026-11-05)

**Status: source audit complete; fresh-battery simulation NOT YET FEASIBLE TO APPROVE.**  
**Basis:** frozen `first_science/phase5/config_phase5_recoverability_battery_v2.json`, `config_phase5_graph_prediction_v3b_fullsupport.json`, `config_phase5_final_wb_v3b_fullsupport.json`, Step-0/I1 executors, and both B1 retrospective Top14/Top1 source contracts. This document is a **source-level audit**, not a completed local runtime measurement or independent scientific test.

**Frozen prior results:** [B1 development](B1_FIVE_BUDGET_DEVELOPMENT_RESULTS_REVIEW_V1.md) and [white-box robustness](B1_WB_ROBUSTNESS_RESULT_FREEZE_2026-11-05.md).  
**Proposed confirmation scope (still not frozen for execution):** [scope v0.1](B1_INDEPENDENT_WORLD_VALIDATION_SCOPE_V0_1.md).  
**Local cost inventory runner:** [audit_independent_world_cost_v0_1.py](audit_independent_world_cost_v0_1.py).

## 1. World-generation feasibility

### What the source actually implements

The existing Phase-5 battery defines **four fixed parameter configurations**, within a single Gamma-service, one-server FCFS provider family; there is **no independent stochastic distribution over physical world parameters** from which a new validation population can simply be sampled:

| Original world | D (million instructions) | delta | Mean instructions A/B/C (million) | Historical Step-0 |
|---|---:|---:|---|---|
| P1 | 330 | 0.00 | 330 / 330 / 330 | Eligible, four graphs |
| P2 | 330 | 0.15 | 280.5 / 330 / 379.5 | All four graphs failed |
| P3 | 360 | 0.00 | 360 / 360 / 360 | Eligible, four graphs |
| P4 | 360 | 0.10 | 324 / 360 / 396 | Eligible, four graphs |

Other physics held fixed in the source include: three providers, instruction CV 0.3, effective IPT 10^9, cost rate 3, execution fraction 0.5, quality 0.5, workload period 0.2 seconds, and four topology ASTs (G_PAR, G_SEQ, G_PARSEQ, G_SEQPAR). P2 is **not** a valid fourth sampled world: its Step-0 failures were frozen, and it cannot be substituted into B1's 12-cell estimand.

The current scripts load this fixed world catalogue and have baked-in P1/P3/P4 eligibility assumptions; **they do not constitute a production new-world generator**. A proposed generalization experiment must first create a versioned way to supply newly sampled physical configurations, while retaining the semantics of the seven methods and the *unchanged* B1 selection/terminal rules.

### Unresolved study-population decisions

A minimal transfer-oriented sampling design could assign **three role strata** approximating the historical conditions: lower-load homogeneous (P1 role), higher-load homogeneous (P3 role), and higher-load heterogeneous (P4 role). This is a *design candidate*, not a selected probability distribution or a claim of broad transfer. Independently sample new physical parameters in each stratum and keep the frozen four graph ASTs.

Before any draws, define and freeze: strata's parameter ranges and distributions, random seeds, parameter validity limits (including risk near utilization 1), the Step-0 eligibility procedure, and what to do with failed cells. The historical P2 all-four failure is evidence that **eligibility attrition cannot be presumed negligible**. A rule to repeatedly replace failed worlds would yield a **conditional eligible-world population**, not unconstrained generalization; record *every* attempted draw, failure and resource cost, and impose a prespecified attempt cap. Whether full 12-cell batteries can be completed at an acceptable yield is unmeasured.

If the three role strata cannot legitimately be interpreted as independent draws from one or more defined populations, a valid study may still be a broader fixed-grid transfer, **but must not be labeled independent-population confirmation**.

## 2. Exact simulation-workload floor for one new complete 7×12 battery

The 7 algorithms' **prediction** trajectories per world×graph cell are contractually:

| Method | Graph trajectories per cell | 12-cell total |
|---|---:|---:|
| M1 | 100 | 1,200 |
| M2 (27 × 100) | 2,700 | 32,400 |
| M3_FULL343 | 1,400 | 16,800 |
| ORIGINAL_TOP14_B1400 | 1,400 | 16,800 |
| ORIGINAL_TOP1_B1400 | 1,400 | 16,800 |
| FIXED_CV_TOP14 | 1,400 | 16,800 |
| FIXED_CV_TOP1 | 1,400 | 16,800 |
| **Prediction subtotal** | **9,800** | **117,600** |
| Independent final WB | 1,000 | 12,000 |
| **Graph execution subtotal** | **10,800** | **129,600** |

The original Phase-II M1+M2+M3+WB 12-cell workload was `12×(100+2700+1400+1000)=62,400` graph trajectories. The full seven-method design is therefore **2.08×** as many *graph trajectories*, not necessarily 2.08× wall time: graphs, model parameters, I/O, worker load and stage interactions are heterogeneous.

Other frozen inputs required **before** the 12-cell score:

- **I1 public-card acquisition:** 2 disjoint banks ×100 full-world trajectories per provider-world role, **600 full-world trajectories** for three worlds. The three providers' local ledgers are extracted from each same full-world trajectory; do not triple-count the I1 executions.
- **Step-0:** 200 calibration +200 confirmation graph-WB trajectories per cell, **4,800** across twelve cells *only if all calibrations pass*. Failed draws still consume cost, including attempted worlds excluded from a complete battery.
- **Original-style Top14/Top1 provider preparation:** 48 candidates/provider ×100 local rescore trajectories ×3 providers ×3 worlds = **43,200 provider-local candidate trajectories**, before graph prediction.
- **Fixed-CV Top14/Top1 preparation:** another **43,200 provider-local candidate trajectories** from the separate policy-transfer candidate bank; its Top14 and Top1 graph predictions share that provider-level bank.
- **Additional V3/V3b provider reconstruction and search, postprocessing, infrastructure and retries:** **not priced** by these counts.

These are **different categories of simulation**. Adding them into one homogeneous trajectory price, or multiplying the Phase-II elapsed time by 2.08, would not be defensible.

The B1 budget `B ∈ {10,15,20,30,40}` counts **algorithm×cell validation observations**, not simulator trajectories or execution hours. A fresh 12-cell validation battery needs the *entire seven-method reference table* to score all possible terminal selections even though each policy only reveals B entries.

## 3. Real runtime evidence and missing-cost problem

Historical Phase-II source records `python_wall_seconds` on each **combined** M1+M2+M3 prediction cell and on each final WB cell. I1 and Step-0 stages also record stage-level wall seconds. The original-style and fixed-CV retrospective prediction manifests provide source hashes/completeness, but do **not guarantee** individually measured method elapsed seconds; their graph execution and separate provider-preparation costs should not be imputed as zero.

A previous local timing inventory reported approximately **23.94 h combined Phase-II M1/M2/M3 prediction** plus **17.57 h final WB**, summed across the twelve historical cells. These are *historical sums of stage wall durations*, not a fresh-battery quote, and should be rechecked by the local audit below; they exclude the other four algorithm variants and much of the provider-search overhead. Some stages use parallel workers. Their summed stage durations are not guaranteed equal to elapsed project makespan or CPU-hours.

To complete the cost feasibility gate, use the local read-only auditor to quantify manifest coverage and exact measured durations per stage. **No trustworthy independent-battery wall-time estimate or number of affordable batteries is possible yet.** In particular, marginal cost for one additional B1 algorithm×cell action depends on whether world-specific public I1 and provider reconstruction have already been paid.

## 4. Feasibility decision

| Component | Audit finding | Gate |
|---|---|---|
| Reuse frozen seven algorithms/budgets/policy | Conceptually possible; preserve source freezes | **PASS with constraints** |
| Prospective independent physical world sampling | Not present in historical contracts | **BLOCKED** |
| Guarantee of 12 Step-0 eligible cells | Not established; P2 historically failed | **BLOCKED** |
| Numerical graph trajectory accounting | 129,600 baseline executions per complete battery | **ESTABLISHED** |
| Method-specific and shared marginal-hour accounting | Insufficient archived timing in source alone | **INCOMPLETE** |
| Number of independent batteries justified by variance/power and available resources | Not estimable until world and cost work | **DEFERRED** |
| Permission to run independent validation | Not yet | **NO-GO until feasibility cleared** |

### Next bounded action

Run the **read-only local timing inventory**, inspect its CSV/Markdown results, and reconcile missing cost stages. In parallel, construct and **separately review** a prospective three-role physical-world generator and its Step-0 eligibility/attrition contract. Avoid executing any new simulations until both documents and the independent confirmation analysis are frozen.

**No acquisition-policy changes, no budget-continuation experiment, no inferred novelty or wall-clock efficiency claim.**
