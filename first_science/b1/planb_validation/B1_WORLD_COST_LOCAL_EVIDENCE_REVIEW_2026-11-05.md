# B1 independent-world / computational-cost feasibility — local evidence review (2026-11-05)

**Status: local source/manifests audit PASS; independent-world validation remains NO-GO pending generator and complete cost evidence.**

## Evidence received and provenance

User executed, on `praise-identifiability-feasibility` at `13042b33fb5685c4449d7af5b187e6ca6a7915ad`:

`test_audit_independent_world_cost_v0_1.py` (2/2 passed) and `audit_independent_world_cost_v0_1.py --repo .` (printed `B1_WORLD_COST_SOURCE_AUDIT_PASS`).

The following six output artifacts were supplied for review: `audit_manifest.json`, `WORLD_COST_FEASIBILITY_AUDIT.md`, `historical_stage_cost_summary.csv`, `historical_manifest_costs.csv`, `trajectory_workload_counts.json`, `world_contract_audit.json`.

**Independent review of uploaded bytes:** all five data/report files' SHA-256 digests matched `audit_manifest.json.output_sha256`. The detailed cost table contained **84 rows**: 3 I1; 9 original provider-candidate; and 12 each for Step-0 calibration, Step-0 confirmation, bundled Phase-II prediction, final WB, original Top14/Top1 and fixed-CV Top14/Top1. Every expected frozen manifest existed and reported a frozen/complete status. Input-source SHA-256 strings were present in the manifest; this review did *not* recompute those hashes from the user's local source checkout.

## Timings available from historical manifests

| Archived stage | Manifest coverage | Numeric stage durations | Sum of recorded per-unit Python wall time | Median per-unit wall minutes | Scope |
|---|---:|---:|---:|---:|---|
| I1 public-card acquisition | 3/3 | 0/3 | **Unrecorded in top-level manifests** | — | Per provider world |
| Step-0 calibration | 12/12 | 12/12 | 2.775012 h | 13.7199 | Per cell |
| Step-0 confirmation | 12/12 | 12/12 | 3.749752 h | 18.6359 | Per cell |
| M1/M2/M3 V3b predictions, bundled | 12/12 | 12/12 | 23.941684 h | 119.1352 | Per cell, no method breakdown |
| Final WB (N=1,000) | 12/12 | 12/12 | 17.567355 h | 86.3298 | Per cell |
| Original-style Top14 + Top1 | 12/12 | 0/12 | **Unrecorded** | — | Per cell |
| Fixed-CV Top14 + Top1 | 12/12 | 0/12 | **Unrecorded** | — | Per cell |
| Original provider-candidate preparation | 9/9 | 0/9 | **Unrecorded** | — | Per provider/world |

Total **recorded stage-duration sum = 48.033803 h**, of which **6.524764 h** is Step-0 and **41.509039 h** is bundled Phase-II prediction plus final WB. This is *not* a full 7-method battery estimate, true serial makespan, CPU-hours, or a floor on new-world cost. Stages can overlap and are machine/environment dependent. `simulation_wall_seconds`, where available, is nested within `python_wall_seconds` and must not be added.

World strata were identifiable in the archived 12 cells; Phase-II bundled prediction sums were P1=7.845 h, P3=7.983 h, P4=8.114 h. WB sums were P1=5.491 h, P3=6.325 h, P4=5.752 h. These are descriptive variations across only three fixed worlds, not a new-world cost distribution.

**One recoverable source detail:** in `run_phase5_i1_v2.py`, the nested `i1_region_evidence_manifest.json` and `i1_sigma_evidence_manifest.json` set `python_wall_seconds` for their separately acquired N=100 banks. Although `i1_freeze_manifest.json` lacks elapsed values in these historical files, these *nested* manifests may provide observed I1 acquisition time if inspected. Their sum still excludes public-card assembly and other I1 overhead. The local audit v0.1 did not inspect these submanifests.

The other missing cost categories should not be imputed from file modification times. Original-style graph benchmark tools print measured throughput, but those printouts are not frozen into the inspected cell manifests. Recover contemporaneous stage logs or documented worker metrics before quoting timings, and distinguish a benchmark projection from completed execution cost.

## World-parameter and complete-battery findings

Historical P1/P2/P3/P4 are **four fixed points**: D=(330,330,360,360) million instructions and delta=(0,.15,0,.10), not draws from a specified distribution. P2 failed Step-0 in all four graphs; P1/P3/P4 supplied the original eligible 3×4 study.

One new complete **7×12 independent-validation reference battery** requires **117,600 prediction graph trajectories** and **12,000 final-WB graph trajectories**, totaling **129,600 graph-level trajectories** (2.0769× the original Phase-II+WB graph *trajectory count*, not 2.0769× hours). Also required when all 12 cells pass: 4,800 Step-0 trajectories; 600 I1 world-graph trajectories; and 43,200 provider-local candidate trajectories **for each** of original-style and fixed-CV preparations, plus unpriced V3/V3b provider reconstruction and overhead. These are heterogeneous operations, not additive identical-cost trajectories.

A complete finite reference 84-cell matrix is needed to calculate terminal regret, even though an acquisition policy reveals at most 40 of its entries. Thus B1's *evaluation-count budget* must not be used as a proxy for the *simulation cost of constructing a new independent validation battery*.

## Assessment and priority

1. **Evidence audit PASS.** All expected source-stage manifests present; timing missingness made explicit; supplied outputs hash-verified.
2. **Physical world generator NOT DEFINED.** Before simulation, preselect a generation distribution for role-preserving independently drawn P1-like, P3-like, and P4-like configurations (or label another study as a different estimand). Freeze parameter bounds, randomization/seed banks, applicability of each role, and the criterion/attempt cap for all four Step-0 graphs. Log *all* failures and costs. Draws passing the gate define a **conditional eligible-world population**; do not claim transfer to arbitrary worlds.
3. **New-world cost NOT PRICED.** Recover nested I1 timing, retrospective Top14/Top1 execution timing from archival logs if available, method-shared reconstruction expenses, hardware/worker settings, and costs of failed Step-0 draws. Use ranges rather than point estimates if evidence is incomplete.
4. **Validation battery count NOT JUSTIFIED.** Only after world generation and realistic cost are resolved should a statistical sizing/power protocol and an independent validation run be frozen.
5. **Preserve frozen B1.** No changes to seven algorithms, acquisition controller, five budgets, Gaussian terminal estimator, or historical results. Additional-budget continuation remains deferred.

**Decision:** positive B1 development and reference-uncertainty results stand, but **independent-world execution remains blocked**. Next cheapest evidence: retrieve existing nested I1 timings and original/fixed-CV logs **read-only**, plus draft a role-stratified world-generator contract for review. No new simulation needed for either action.

## Subsequent I1 timing recovery (2026-11-05)

The I1 missing-duration note above describes the *original top-level-manifest inventory* and is superseded for acquisition phases by [B1_I1_ACQUISITION_TIMING_RECOVERY_2026-11-05.md](B1_I1_ACQUISITION_TIMING_RECOVERY_2026-11-05.md). A read-only extraction of the nested region/sigma evidence manifests returned **0.150902 h (P1), 0.189828 h (P3), and 0.171576 h (P4)**, totaling **0.512306 h**. Adding these recorded acquisition-stage durations changes the historical *incomplete* stage-duration sum from **48.033803 h** to **48.546109 h**. This does not include I1 public-card assembly or the missing four Top14/Top1 variant runtimes and is not a new-world battery estimate.

## Follow-up: measured graph-stage times recovered from preserved progress logs

[Second-pass graph-stage timing audit (2026-11-05)](B1_GRAPH_STAGE_TIMING_RECOVERY_REVIEW_2026-11-05.md) supersedes the earlier statement that the **fixed-CV graph stage itself is wholly unmeasured**. Complete runner `time.perf_counter()` observations yield **308.0 minutes Top14 + 288.3 minutes Top1 = 596.3 minutes (9.9383 hours)** across all 12 fixed-CV cells, excluding ledger merging, prediction scoring and other command overhead. No shell `real` marker or exact full fixed-CV command duration was found. The frozen scientific results are unchanged.
