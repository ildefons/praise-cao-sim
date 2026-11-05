# B1 graph-stage timing: recovered measurements (2026-11-05)

## Evidence

The uploaded recovery archive contains three logs. All five output files match SHA-256 values in `recovery_manifest.json`. No command-level shell `real` markers were found. But `log_timing_evidence.csv` preserves complete graph-stage progress lines from the original runner's `time.perf_counter()` timer. The timer is in `_execute_payloads` within `first_science/phase5/run_phase5_graph_prediction_v3b_fullsupport.py`. A completed stage is identified by `models n/n | trajectories 1400/1400 | elapsed=X.Y min`.

Fixed-CV original log SHA-256: `284d11d75bba922a6c4ca24946931c35ffc5a25df9a59c06db4d17465cfacc3e`. Original-style replay log SHA-256: `6008915e8aa0b947e2b5710aec93032c0f025e170827c680175b2e6174801786`.

## Measured graph job-group elapsed time

| Group | Complete cells | Sum (minutes) | Hours |
|---|---:|---:|---:|
| Fixed-CV Top14 | 12 | 308.0 | 5.1333 |
| Fixed-CV Top1 | 12 | 288.3 | 4.8050 |
| **Fixed-CV, both groups** | **12 each** | **596.3** | **9.9383** |
| Original-style Top14 (later replay only) | 10 | 250.2 | 4.1700 |
| Original-style Top1 (later replay only) | 10 | 212.9 | 3.5483 |
| **Original-style, later replay groups** | **10 each** | **463.1** | **7.7183** |

Exactly 24 fixed-CV and 20 original-style complete stage records were found, one of each method per cell. In the original-style replay, P1/G_PAR and P3/G_PAR were previously completed and reused from cache, accounting for the two missing cells.

These are **measured process-pool graph-job phases**, not the full commands' elapsed time. Their runner timer excludes some post-job merging, curve scoring, CSV writing, and additional command overhead. The fixed-CV full `--stage all` command's total wall time has **not been recovered**. The observed values are printed to 0.1 minute (combined 24-stage rounding uncertainty at most about 1.2 minutes). Top1 `models 4/4` means four scheduling blocks of the **same** model, not four candidate models.

For the original-style full 12-cell completion, separate terminal `real` measurements had been recorded in earlier project messages: 81m45.026s, 81m06.518s, and a subsequent 734m48.127s replay reusing those two cells; together **14h57m39.671s** over three invocations. These shell times are **not** part of the newly uploaded recovery CSV.

## Scientific and cost interpretation

The earlier recovery report's claim of `0 shell time markers` is correct, but its implied lack of useful measured fixed-CV timing is incomplete. We now know the **actual graph-stage subtotal** for all 12 fixed-CV cells (9.9383 h), while exact full-command duration remains unknown. The original-style 10-cell replay recorded 7.7183 h inside graph phases but 12.2467 h at the command level: different scopes, not a transferable overhead ratio.

Do **not** combine the stage subtotal with previous full-command durations and present that sum as a new independent-battery runtime. New-world reconstruction, eligibility attrition, and full fixed-CV overhead remain unpriced. Independent world generation is not approved. All seven predictors, B1 policy, five budgets, and archived scientific outcomes remain frozen.
