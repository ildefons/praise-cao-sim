# B1 original-style Top14/Top1 historical graph timing — recovered record (2026-11-05)

**Status:** original-style graph battery: measured historical run durations recoverable from earlier user terminal records. Fixed-CV graph battery: completion confirmed but **exact wall time not recovered**.

## Exact original-style terminal measurements (October 19–20, 2026)

The following are sourced from the user's earlier terminal messages in the PRAISE project, **not** from the per-cell prediction manifests. The earlier terminal `time` measurements covered:

| Command/run | Shell `real` | Interpretation |
|---|---:|---|
| First independent P1/G_PAR prediction | **81m45.026s** | Initial frozen original-style Top14 + Top1 2,800-trajectory cell; 4 workers |
| First independent P3/G_PAR prediction | **81m06.518s** | Initial frozen original-style Top14 + Top1 2,800-trajectory cell |
| Later `--stage predict` run | **734m48.127s** | Printed progress 12/12; re-used both previously frozen cells rather than rerunning them; completed remaining cells |
| **Sum of those three measured command-wall durations** | **897m39.671s = 14h57m39.671s** | Historical multi-run **combined** graph prediction time including runner overhead; not a single contiguous job or CPU-hours |

The later 734m48.127s run reported `user 1938m40.864s` and `sys 3m28.811s`, consistent with parallel execution and highlighting the distinction between wall clock and aggregate process CPU usage. **Do not add the two individually measured cells' 2,800 trajectories to the later run's actual simulated work again**: its 12/12 progress counter includes cached cases.

These observations record **fourteen- and one-member method simulations together**, not an independently timed *per-method* cost breakdown. An isolated per-method wall-clock claim must be supported by separate stage timers/log markers. The earlier output also reported P1/G_PAR Top1 `elapsed 24.2m`, P3/G_PAR Top1 `elapsed 22.3m`, and the final P4/G_SEQPAR Top1 `elapsed 20.7m`; these are limited **within-cell progress/readout durations**, not complete-battery Top1 cost evidence.

## Fixed-CV: remaining data gap

The fixed-CV `first_science/b1/local_audit/fixed_cv_top1_top14/run.log` reported successful completion of all 12 cells on October 29, 2026: `B1_FIXED_CV_TOP1_TOP14_STAGE_ALL_PASS`. Its documented runner prints `=== FIXED CV i/12: cell ===`, `PREDICTED AND FROZEN cell`, and Top14→Top1 progress, but does **not** itself instrument total `python_wall_seconds` in each frozen prediction manifest. The previously discussed **10–20 h was a projection only** and is **not** a measured interval.

Only a contemporaneous log with explicit elapsed time, a securely linked command `time` record, or independently recorded start/end timestamps for the same execution can close this gap. A file's modification/birth time or a difference between two `completed_utc` values is not a reliable replacement for an execution timer.

## Implications for cost accounting

The previously recorded 48.546109 hours is a *sum of measured but incomplete historical phase durations* for I1 + Step-0 + M1/M2/M3 + WB. The original-style **14.961020 h** is an additional historical multi-run wall-clock cost category. Arithmetic sum `48.546109 + 14.961020 = 63.507129 h` combines differently scheduled stage durations: **it must not be described as a measured end-to-end new seven-method battery wall time**, nor as a hard lower bound. Fixed-CV graph time, its candidate reconstruction, additional V3/V3b local reconstruction and eligibility-attrition work remain unpriced.

## Safe continuation

Run [recover_graph_timing_from_logs_v1.py](recover_graph_timing_from_logs_v1.py) against the historical *project-only* logs. It extracts explicit `time` records and progress markers, separately inventories frozen manifest completions, and does **not** run any graph or provider simulation. Interpret the resulting fixed-CV evidence before estimating independent-battery cost.

**Frozen B1 algorithms, acquisition policy, five budgets, archived metrics and WB reference remain unchanged.**
