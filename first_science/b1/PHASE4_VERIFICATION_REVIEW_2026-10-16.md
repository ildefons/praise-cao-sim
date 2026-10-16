# PRAISE B1: Historical Phase-4 pilot and M3 mechanism audit review

**Reviewed 2026-10-16.** User-supplied audit bundle: `praise_b1_phase4_pilot_verification.zip`, SHA-256 `37e538e6bbefc28e881ea3f37f3ba9eba24753e7ef2f0c72b0c3a77c6a1e7056`.

## Verification result

`verify_phase4_pilot_v0_1.py` produced **60 PASS, zero FAIL**, split equally between pilot and post-hoc checks. It checked required file presence, both completed manifest statuses, saved CSV-hash matches, and recomputed MAE/RMSE/signed bias from 555 pointwise records per method over H60..240. Computed metrics match saved summary CSV rows to floating-point precision and the historical reported MAEs within their rounding accuracy.

### Frozen September pilot

| Method | n | MAE | RMSE | Bias |
|---|---:|---:|---:|---:|
| M1 | 555 | 0.185171171 | 0.230735799 | +0.185171171 |
| M2 | 555 | 0.068153487 | 0.094140553 | +0.047374708 |
| M3_B1400 | 555 | 0.030368445 | 0.035782880 | +0.028240347 |
| M3_B2000 | 555 | 0.027547333 | 0.033063741 | +0.024468396 |

Reference: `phase4/results/m3_v4_final_evaluation_v1/m3_v4_final_comparison.csv` and `m3_v4_final_error_metrics.csv`. Frozen status `PHASE4_M3_V4_FINAL_EVALUATION_COMPLETE_V1`.

### Retrospective cost-matched support/weight ablation

| Method | n | MAE | RMSE | Bias |
|---|---:|---:|---:|---:|
| TOP1_1400 | 555 | 0.028783784 | 0.034060271 | +0.024981982 |
| UNIFORM14_EQ_1400 | 555 | 0.054903475 | 0.065698434 | +0.053619048 |
| WEIGHTED14_EQ_1400 | 555 | 0.042220938 | 0.050158969 | +0.040661499 |
| WEIGHTED14_MINIMAX_1400 | 555 | 0.030368445 | 0.035782880 | +0.028240347 |

Reference: `phase4/results/m3_posthoc_stage_b_ablation_v1/stage_b_predictions.csv`, `stage_b_error_metrics.csv` and `stage_b_manifest.json`. Frozen status `PHASE4_M3_POSTHOC_STAGE_B_COST_MATCHED_ABLATION_COMPLETE_V1`.

## Supported boundaries

- The favorable original single-graph pilot existed as recorded and was not a transcription error.
- It **cannot** be generalized to the later Phase-5 battery. The method implementation, support, provider worlds, graph structures and reference study changed.
- Within the frozen September pilot, the cost-matched Top1 estimator had lower MAE than the production weighted-14 estimator. The pilot therefore does **not** establish a general gain from averaging multiple hypotheses.
- The retrospective ablation is mechanism diagnosis *after* pilot WB was known, not independent confirmation.
- The pilot and ablation evaluation metrics are now verified **from saved tables**, not reproduced from raw request/trajectory events, and the hash checks cover the comparison/metrics files named in the manifest, not all ledgers.

## Outstanding documentation items

The Phase-4 episode also contains M2-G1 prospective stress and G2 Step-0-calibrated validation; these must remain separate from the M3-v4 final pilot evidence. Method-version chronology and original file references are documented in `METHOD_VERSION_CHRONOLOGY_2026-10-16.md`.

A claim ledger should explicitly distinguish a *verified metric*, a *plausible mechanism interpretation*, and a *generalization claim that is unsupported*.
