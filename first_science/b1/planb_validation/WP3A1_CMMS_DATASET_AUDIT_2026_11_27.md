# WP3a.1 CMMS dataset audit — 27 November 2026

**Decision: dataset suitability PASS for a retrospective finite-catalogue replay; WP3a.2 protocol still to be agreed.** No acquisition policy was executed, no priors or loss definitions were frozen, and no manuscript changes were made. WP1, WP2 and WP5a remain frozen.

## 1. Source and provenance

User-supplied cmms-benchmark-7D80(1).zip (401 entries), SHA-256:
`f146fff83bba95cc970faf96cc65ea3943f6508f48351d4a9389120e4aaaa4c2`.

Canonical input candidate: `paper_data/all_clusters_merged.csv`, SHA-256:
`e6c2a7bb5231c267f1974cefde6bb745bf5bf7f98ba1df7eb612707d92c57038`.

Paper source: `paper/main_online.tex`, title *Fair Comparison of Scheduling Algorithms on Heterogeneous Edge Clusters: A Continuous Adaptive Benchmark*, Zihang Wang, Boris Sedlak, Juan Luis Herrera, Schahram Dustdar. Repository URL in that source: https://github.com/Daniel-Wang23333/cmms-benchmark.git. Archive README states MIT; LICENSE copyright 2026 CMMS-Benchmark Authors. No authenticated upstream commit is established from the ZIP alone; paper_data/README.md reports generation on 19 April 2026 from commit chain 41b8976 to 1e09bc9. Record ZIP and CSV digests. Do not equate reported commit chain with exact ZIP revision. The source paper and benchmark data are external to our PRAISE simulator, although Dustdar is a coauthor of both papers; describe as external benchmark, not independent research group or prospective blind confirmation. No contact with authors is needed for aggregate replay.

## 2. Catalogue and replication audit

Actual merged CSV: 424 episode rows, 31 columns, no nulls, finite numeric values, no identical rows and no duplicate (cluster, controller, scenario, run_id) keys. Each of five per-cluster summaries reproduces its exact subset of merged data on the 29 shared columns; corresponding edccs_final CSVs are byte-identical duplicates, not additional data. Do not use deprecated artifacts or duplicate edccs_final summaries as evidence.

| Configuration | NoOp | LL | Heuristic | Myopic | DQN | AIF-Hier | Round-Robin | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2-node-homo-light | 12 | 12 | 12 | 12 | 12 | 20 | 12 | 92 |
| 2-node-het-light | 12 | 12 | 12 | 12 | 12 | 20 | 12 | 92 |
| 5-node-light | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 84 |
| 8-node-light | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 84 |
| 8-node-heavy | 12 | 12 | 12 | 12 | 12 | 12 | 0 | 72 |

The paper's six-controller portfolio and plot_paper_figures.py CTRL_ORDER and CSV loader exclude Round-Robin. Excluding its 48 rows leaves **376 episodes across all 120 cells** (6 controllers x 5 joint cluster-load configurations x 4 workload patterns). 112 cells have exactly runs 1-3; eight AIF-Hier cells in the two 2-node configurations have runs 1-5. A balanced runs-1-to-3 subset has 360 episodes and identical cell coverage. Full data should not be described as 424 six-controller episodes, as the paper setup table might suggest. Some cluster READMEs also give inconsistent totals and state runs 1-3 only; actual CSV keys resolve this. The heavy README confirms the supplemental NoOp, LL and Myopic data, superseding older statements that heavy has only three controllers.

No missing cells, no zero-length denominators, no observed skip-budget violations; zero Raw SLO episodes (two) are retained as valid observed poor performance. No evidence that absent/failed historical attempts have all been disclosed. Source logs and raw per-step histories and learned checkpoints are not included in this supplied snapshot outside deprecated artifacts. Episode-level summary checks are possible, but end-to-end rerunning original hardware campaign is not established.

## 3. Condition semantics and structure

Use composite configuration h in {2-node-homo-light, 2-node-het-light, 5-node-light, 8-node-light, 8-node-heavy}; workload pattern s in {ramp_up, burst, steady_overload, oscillating}. Normalize scenario names by removing scenario_ and _heavy suffix; validate suffix against workload and cluster. Physical load is not independently crossed with all hardware: HEAVY is observed only at 8-node. The four named patterns have different event sequences/intensities between light and heavy, not identical scripts.

From config/workload_scenarios.yaml, LIGHT durations (seconds) 180,180,180,300 and peak streams 8,7,6,8; HEAVY durations 200,200,200,320 and peaks 13,12,10,13, respectively. Observed steps match or are one below nominal duration. Platform uses actual heterogeneous Jetson/Ryzen testbed and video inference (paper main_online.tex experimental setup). This provides an external physical evaluation rather than another synthetic simulation. Distinguish hardware configuration from load intensity; 5x4 is a complete factorial of composite configuration and pattern labels, not a fully crossed hardware x load x pattern design.

Existing additive surrogate is applicable with one intercept, five configuration effects, four pattern effects (10 coefficients). Equal prior variance within each factor type and shared prior across methods give constant prior row sum kappa=20*tau_alpha^2+4*tau_h^2+5*tau_s^2. WP2 recommendation and KG equivalence then hold for uniform catalogue weights. It is not evidence that the additive model fits CMMS; that is to be tested. Equal condition weights imply 20% weight on heavy and 40% on the 8-node hardware, not deployment-frequency estimates. No imputation of missing hardware-heavy combinations or causal inference about separate hardware/load effects. Light-only or alternative structural sensitivity can be predeclared as secondary, not chosen after acquisition results.

## 4. Metric integrity

Raw SLO = fraction of non-SKIP stream-windows meeting conjunctive latency, throughput and detection-quality thresholds. According to run_multi_experiment.py extract_summary, warmup and SKIP windows are omitted from this denominator; SKIP has separate episode-level threshold 30%. Steady-state SLO also excludes post-switch transient windows. Transition tax = SS SLO - Raw SLO, which need not be positive. The current summary code and paper specify these conventions despite a stale comment in config/slo.yaml about SKIP as a failure.

All 424 Raw and steady-state fractions reproduce the count-based formula 1 - violations/windows within 0.00005 (4-decimal rounding); transition tax matches SS-minus-Raw within 0.0001. Raw SLO range [0,0.9868]; skip ratio range [0,0.2538]; all skip budget flags are zero and consistent with reported ratios. Among the six controllers, 129 episodes have nonzero skip ratio. Therefore raw SLO is not fraction of all requested stream-windows served successfully. Candidate alternative including skipped work as unsuccessful is 1-(1-skip_ratio)*Raw_SLO, using reported rounded values. This is a different service objective, not the paper's raw SLO.

paper_data/aggregate_slo.csv contains 34 configuration-controller rows including 4 Round-Robin groups. All 30 six-controller groups match raw CSV episode counts, means and sample SDs to reported 4 decimals. Paper appendix per-scenario table matches 117/120 raw cell means within 0.5 percentage point; the three small discrepancies (max 0.537 pp) are NoOp 8-light steady overload, NoOp 8-heavy burst and Myopic 5-light burst. CSV is canonical, not rounded table. Using all AIF repetitions rather than runs 1-3 changes exactly eight cell means, by at most 0.02076 in Raw SLO. Across 120 cells, median within-cell sample SD 0.01463; 9 cells exceed 0.05, 2 exceed 0.10; max 0.26705. Do not treat episodes or stream windows as independent replications without evidence; no claim of negligible reference uncertainty.

## 5. What can and cannot transfer

The original experiment includes per-(cluster, scenario) DQN training (one seed-0 checkpoint, ten episodes per source paper); replacement DQN runs and supplemental AIF runs are described in cluster READMEs. The controller label denotes a configuration-dependent training/deployment procedure, not one universal trained checkpoint. This is selection among controller families as instantiated in the benchmark, not transfer of trained controllers to unseen hardware or scenarios. Shared scripts do not prove common random numbers or paired noise; run_id is ordinal, not verified shared stochastic seed. Hardware/session drift and training variation are not identifiable from summaries.

Define one non-replicable acquisition as revealing an aggregate for a controller-condition pair using a fixed offline episode bundle. Actual hardware experiments are repeatable in principle; our cell-level reveal rule is an explicit design abstraction, not a physical restriction. Policies never see unqueried reference values or associated metrics. Regret/PCS refer to the realized archived cell-mean target, not the unknown population expectation. External benchmark was already selected with knowledge of its published results; avoid claiming prospective blinded confirmation.

Nominal duration and per-step scheduler overhead are different from validation costs. The latter is deployment decision overhead, not cost to reveal a cell. Training, preparation, repetitions and workload durations differ. Budget remains number of complete cell reveals; report equal episode counts only if balanced bundle chosen. No CPU-hour or measured wall-time savings from this data.

## 6. Recommendations to discuss before freeze

- Primary candidate: all 376 paper-scope episode rows, define one cell loss as 1 minus the arithmetic mean of recorded per-episode Raw SLO. Equal weight across 20 cells. This respects source comparisons and uses all available eligible data; it does not pool windows or weight configurations by number of repetitions. Preserve runs 1-3 balanced subset as prespecified replication sensitivity. If equal measurement effort is the primary design requirement, reverse primary and sensitivity before replay (not after).
- Keep separate skip-budget condition; all observed flags pass. Secondary skip-inclusive service objective can be fixed in advance if scientifically useful; steady-state SLO and decision overhead are distinct endpoints, not silently folded into primary scalar loss. No metric selection based on which acquisition policy wins.
- Priors must be specified on the new SLO-loss scale without fitting to all 120 outcome means. The frozen PRAISE mean 0.17 and variances are MAE-specific heuristic values, not justified simply by both metrics being in [0,1]. Agree a common outcome-independent prior and a small prespecified sensitivity grid, with matched priors across policies. If use training data for prior calibration, isolate it from evaluation target and budget.
- Same policy logic and common initialization of all six methods at one condition. Generalize dimensions and balanced coverage rules transparently. Freeze budget checkpoints and repetitions, seed policy, contrasts, metrics and tie handling. WP4 baselines remain separate work.
- Explicitly separate conditional replay uncertainty (policy randomization) from episode-sampling uncertainty in the reference target. Do not use 424 episodes as independent policy evaluation roots; do not pair unrelated runs across methods by run_id. WP5b may examine within-cell resampling with caveats.
- Data audit is complete; compatibility and protocol review (WP3a.2/3) still needed. No loss matrix or acquisition result generated for replay and no method is chosen on the basis of policy performance.

## 7. Minimal reproduction of catalogue checks

Run against the supplied archive with pandas/numpy:

```python
import zipfile, hashlib
import pandas as pd
import numpy as np
from pathlib import Path
p = Path("cmms-benchmark-7D80(1).zip")
with zipfile.ZipFile(p) as z:
    print(hashlib.sha256(p.read_bytes()).hexdigest())
    name = "paper_data/all_clusters_merged.csv"
    print(hashlib.sha256(z.read(name)).hexdigest())
    d = pd.read_csv(z.open(name))
    assert d.shape == (424, 31)
    assert not d.isna().any().any()
    assert np.isfinite(d.select_dtypes("number")).all().all()
    assert not d.duplicated(["cluster","controller","scenario","run_id"]).any()
    print(pd.crosstab(d.cluster, d.controller))
    s = d[d.controller != "round_robin"].copy()
    s["pattern"] = s.scenario.str.removeprefix("scenario_").str.removesuffix("_heavy")
    g = s.groupby(["cluster","pattern","controller"])
    assert len(s)==376 and g.ngroups==120
    assert g.size().value_counts().to_dict()=={3:112,5:8}
    assert len(s[s.run_id<=3])==360
    assert (d.total_windows>0).all() and (d.ss_windows>0).all()
    assert (d.slo_satisfaction_rate-(1-d.slo_violations/d.total_windows)).abs().max()<=0.0000500001
    assert (d.ss_slo_rate-(1-d.ss_violations/d.ss_windows)).abs().max()<=0.0000500001
    assert not d.skip_budget_violated.any()
    for cl in d.cluster.unique():
        q = pd.read_csv(z.open(f"paper_data/{cl}/summaries.csv"))
        t = d[d.cluster==cl]
        shared = [c for c in q.columns if c in t.columns]
        assert len(t)==len(q)==len(t.merge(q,on=shared,validate="one_to_one"))
        assert z.read(f"paper_data/{cl}/summaries.csv")==z.read(f"edccs_final/{cl}/summaries.csv")
    print("CMMS catalogue audit PASS")
```
