# B1: independent original-style M3 retrospective evidence review

**Audit date:** 20 October 2026. **Result:** 316 PASS, 0 FAIL. Archive supplied by the experiment operator; no graph simulation replay.

## Archived inputs and integrity

Archive: b1_m3_retrospective_evidence.zip
SHA-256: 43ca9c78f3d41b5d2949baec7773855c70b3722d170ce8038bb967ac256fd011
Science code: first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py
Local results namespace: first_science/phase5/results/b1_pilot_m3_retrospective_v1/

The experiment was designed AFTER earlier Phase-5 final WB results were known. Reused original Step-0 eligibility (12 cells: P1/P3/P4 by four graphs), 15 queries/cell, H=60..240 seconds at step 5, and frozen N1000 WB reference. P2 not restored. V2-style method: 48 public-I1 LHS candidates/provider, 100-trajectory local rescore, lambda=30 Gibbs KL, weighted Top14 B1400; separately simulated Top1 B1400. Baseline: executed seven-fit V3b FULL343 B1400.

## Independently checked archive contents

- All 12 global prediction-manifest hash links match the included per-cell prediction manifests.
- The 24 included Top14/Top1 prediction tables match their manifest SHA-256 values and have 735 complete query-horizon predictions each, H0..240; probabilities are valid and B1400.
- The nine per-provider weight files match support-manifest hashes, have exactly 48 candidates each, and each set sums to one.
- The three 14-member joint support files match support manifests and allocations totaling B1400.
- The 14 highest Cartesian-product joint weights were independently recovered from all 48^3 provider-weight products in each world, matching the archived Top14 entries and retained masses.
- The evaluation manifest hashes match its global prediction-freeze, metrics and pointwise tables.
- The 19,980 scored pointwise rows (3 methods x 12 cells x 555 points) have consistent shared WB values across methods; all error values and aggregate/cell/provider/graph MAEs were independently recomputed.

**316 checks passed and none failed.** This is independent numerical and SHA-link reconciliation of the uploaded subset.

| Method | MAE | RMSE | Signed bias |
|:--|--:|--:|--:|
| Executed Phase-5 V3b FULL343 | 0.121890 | 0.180806 | +0.065105 |
| Retrospective original-style Top14 | 0.154155 | 0.212843 | +0.044867 |
| Retrospective original-style Top1 | 0.162280 | 0.225373 | +0.054562 |

Retained Top14 masses: P1 0.99640442073833; P3 0.9967711039774327; P4 0.9989251244257544.
FULL343 beats Top14 in 11/12 world-graph cases. Original Top14 beats separately simulated Top1 in 8/12 cases.
P3/G_PAR contributes 49.35% of the aggregate Top14-minus-FULL343 MAE gap. P3/G_SEQ reverses the ranking: Top14 0.083016 versus FULL343 0.116330. Excluding P3/G_PAR leaves mean remaining-cell FULL343 advantage 0.017828.

## Limits of the review and scientific inference

The ZIP omits twelve Top14 member-curve CSV files and raw native graph trajectory ledgers. Consequently we did not reconstruct member curves from raw YAFS events or independently rerun the simulator. The originally frozen standalone V3b baseline and raw WB tables are not themselves packaged in this ZIP; their values were audited inside the included retrospective pointwise join and compared with the previously verified baseline aggregate.

This is not independent confirmation: the retrospective method was specified after the reference results were inspected. Matched B1400 graph propagation does NOT equal matched provider-local reconstruction cost. The original-style 48-member proposal and V3b seven-fit proposal use different fitting/selection procedures and cannot isolate ensemble-size causality. Shared queries, horizons and simulation seeds create dependence across the 6,660 points. Internal omitted-weight bounds apply only to the reconstructed candidate distribution, NOT to white-box accuracy.

**Publication role:** Evidence-backed, explicitly retrospective Section 8.4 and limitations; a new preregistered holdout is needed for confirmatory claims.