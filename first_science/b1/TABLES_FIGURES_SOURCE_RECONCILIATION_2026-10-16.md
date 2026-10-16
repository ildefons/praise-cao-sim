# PRAISE B1, Substep 2.4: Archived display-source reconciliation

**Review date:** 2026-10-16  
**Input archive:** `praise_b1_display_source_evidence_v0_1.zip`  
**SHA-256:** `84f3f891061a2cc67fe0358b208ce47302ecf40bb35db65401abef3e75efaddd`  
**Historical source:** `praise_caise_workshop_note_v11_45(1).pdf`.  
**Outcome:** **22/22 requested files included; 0 missing; 0 skipped; 22/22 archive collector SHA-256 values match.** Also checked 13 selected hash links in the included scientific freeze manifests against their archived output files: **13/13 matched**.

This is numerical reconciliation from frozen summary/pointwise CSVs and original source manifests, not a new graph simulation or reconstruction from raw request ledgers.

## Verified original pilot results, H60–240

Read `phase4/results/m3_v4_final_evaluation_v1/m3_v4_final_comparison.csv`; recomputed `mean(|pred-WB|)`, `mean(pred-WB)` and per-regime metrics directly.

| Method | Rows | MAE | Bias |
|---|---:|---:|---:|
| M0 (applicable) | 333 = 9 queries × 37 | 0.572035 | -0.572035 |
| M1 | 555 | 0.185171 | +0.185171 |
| M2 | 555 | 0.068153 | +0.047375 |
| M3 production B1400 | 555 | 0.030368 | +0.028240 |
| M3 production B2000 | 555 | 0.027547 | +0.024468 |

**M0 applicability:** G0: 185 points (all five rho queries), G1: 148 points (four rho queries), G2: no points. Therefore M0's displayed MAE is not directly comparable with the other 555-point scores.

## Table 2: decision denominators reproduced independently

A 95% Wilson interval on each of the 555 N200 white-box query/horizon values, tested at `beta=.90`, yields **481 reference-certain points**. M0 has only **274 applicable and reference-certain points**.

| Method | Certain and applicable points | Agreement (%) | False accepts | False rejects |
|---|---:|---:|---:|---:|
| M0 | 274 | 33.94 | 0 | 181 |
| M1 | 481 | 37.63 | 300 | 0 |
| M2 | 481 | 86.07 | 67 | 0 |
| M3 B1400 | 481 | 96.47 | 17 | 0 |
| M3 B2000 | 481 | 97.09 | 14 | 0 |

These reproduce Table 2's displayed agreement after rounding. The archived Top1/Top3 matched-budget decision results also agree with their freeze-file metrics; the *operational* B100/B300 scores in Table 2 need a separate source-curve check (see gaps).

## Table 3: full matched-budget Top1/Top3 per-regime metrics verified

Recomputed `m3_top3_support_predictions.csv` on H60–240 and compared to the frozen support-summary CSV and the Table 3 printout. Each regime has **185** horizon-query points. The other method curves (WB, M1, M2, M3 B1400/B2000) are **identical, pointwise (maximum discrepancy 0)** between the independent pilot comparison and support-validation files.

| Method | Easy MAE / bias | Mid MAE / bias | Stress MAE / bias | Overall MAE |
|---|---|---|---|---:|
| M1 | .04097/.04097 | .15051/.15051 | .36403/.36403 | .18517 |
| M2 | .02364/.01046 | .07055/.03079 | .11027/.10088 | .06815 |
| Top1 B1400 | .02297/.02297 | .03454/.03144 | .02885/.02054 | .028784 |
| Top3 B1400 | .02416/.02416 | .03592/.03563 | .03155/.02632 | **.030543** |
| Top14 production B1400 | .02363/.02363 | .03553/.03502 | .03195/.02607 | .030368 |

All displayed Table3 rounded values match. The Stage-B retrospective Top1 B1400 file also agrees *exactly pointwise* with the support-validation Top1 B1400 file, and the two studies use identical white-box reference curves.

## Table 4: all 3 provider parameter triplets and public-I1 losses agree

Compared the printed Table4 directly with `m1_vs_top1_parameters.csv`, `m1_vs_top1_public_i1_fit.csv`, and the independent Oct5 `hidden_theta_comparison.csv`. Rounded manuscript values agree for all three providers and all KL/MSE columns.

| Provider | Truth / M1 / Top1 mean service time (s) | Truth / M1 / Top1 cost rate | Truth / M1 / Top1 CV | M1 / Top1 public-I1 KL | M1 / Top1 public-I1 MSE |
|---|---|---|---|---|---|
| A | .120/.035159/.022082 | 3/.501061/4.935772 | .300/1.455995/1.514221 | .200133/.259181 | .055136/.065032 |
| B | .150/.047880/.055156 | 3/2.102457/2.698021 | .300/1.255523/1.112100 | .140105/.110514 | .044898/.035301 |
| C | .180/.002682/.173967 | 3/87.306987/.551638 | .300/.994198/.341104 | .273175/.087948 | .060790/.029589 |

These are **retrospective diagnostic truths**. They do not prove structural I1 nonidentifiability or justify using hidden generating parameters in public reconstruction. The public-I1 loss ordering differs by provider (A favors M1, B/C favor Top1).

## Figure 2: finite-reference bootstrap bars and Pareto problem

The 10,000-replicate frozen N200 **white-box-reference** bootstrap from `wb_reference_bootstrap_summary.csv` reports:

| Method | Reference-resample MAE point estimate | Bootstrap percentile 95% range |
|---|---:|---:|
| M1 | .185171 | [.154018, .218355] |
| M2 | .068153 | [.057670, .090479] |
| M3 B1400 | .030368 | [.019644, .061705] |
| M3 B2000 | .027547 | [.018972, .058046] |

The paired `MAE(M2)-MAE(M3)` percentile intervals from the same archive are **[.026621,.043303]** (B1400) and **[.029522,.044804]** (B2000), matching the manuscript. This bootstrap resamples the *same white-box seed indices across query/horizon points*, not independent new physical provider worlds.

**Figure 2's claimed unrestricted “nondominated frontier” remains wrong in its plotted graph-trajectory-count-vs-MAE plane** because Table 2 includes a retrospective operational M3 Top1 `(B=100, MAE=.0399)`, which dominates the plotted M1 `(100,.1852)` in that plane. Qualification as “selected prospectively frozen primary operating points only” is mandatory; accounting for upfront local computation may reverse a total-resource ordering.

## Figure 3: numerical width anchors reproduced, including clipping effect

- **M1 B100:** computing the mean Wilson interval width on the 555 M1 graph estimates gives **.0374873** (manuscript .0375).
- **M3 B1400:** normal interval from the worst-case member-weighted variance has raw full width .0524099, but clipping each interval to [0,1] yields **mean .0493118** (manuscript .0493).
- **M3 B2000:** analogous raw width .0438337, clipped **mean .0424661** (manuscript .0425).
- **M2 B2700:** source does not include the 27-member paired seed-level bootstrap outcome matrix; the quoted mean width .0563 remains **not independently recomputed**, though its method and scaling are documented in Appendix B.

The budget forecasts are **algebraically consistent** with anchors and the approximate `c/sqrt(B)` law; they are not evaluated prediction-error/budget outcomes.

## Additional archived integrity checks

Manifest declarations and archived file hashes verified directly for:

- Phase4 final comparison, final metrics, regime means;
- Top3 support predictions, metrics, decisions, MC-width summary;
- Stage-B predictions, metrics, decisions, bootstrap summary;
- N200 reference-bootstrap summary; Stage-A truth-candidate table.

**13/13** selected scientific-manifest output SHA256 links agree. Collector includes all 22 requested evidence files with their own per-file SHA256 fingerprints. Missing and oversized archived results: **zero**.

## Remaining narrow gaps (must be labeled, not invented)

1. **Table2 operational Top1 B100 and Top3 B300 scores/decisions**: the submitted ZIP includes matched-budget Top1/Top3 B1400 curves and Stage-B Top1 B1400, *not* the original per-member first-100 source curves. The manuscript prints .0399/.0401 and 86.5% agreement, but those two source-row computations are **not** independently checked here. They are not contradicted.
2. **M2 B2700 Figure3 width .0563**: source lacks the shared-seed trajectory-level pass matrix or its original numerical-width summary CSV. No independent recomputation.
3. **Pixel-by-pixel Figure1 plot-to-series correspondence** and full underlying raw YAFS event generation are not attempted. Original plotted horizon grid and all included reference/method curves have consistent numeric source tables.

These are limited ancillary audit gaps, not evidence of incorrect main paper results.

## Manuscript corrections mandated by the audit

- Stage-aware Table2, with denominators and local vs recurring cost; Stage-B replay is *post-pilot experimental evidence* even if later readouts require no new simulator runs.
- Figure1 and Table2 use different Top1/Top3 budgets. Their displayed scores must not be interchanged.
- Figure2: partial nondominated set, with explicit choice-set restriction.
- Figure3: numerical precision projection only, using **clipped** pointwise intervals for M3. Do not claim outcome reliability or cross-world accuracy from B scaling.
- Appendix A's reference to a nonexistent MC-width column in Table2 must be fixed.
- Main Phase5/Phase6/P2 displays must not be represented as the same population/method-version as pilot figures.

**Substep 2.4:** completed at full numbered-display and major numerical-claim audit level; *exact ancillary source-level sign-off* has two limited open checks. It is scientifically safe to continue with **Step 2.5, simulator infrastructure and provenance**, without additional simulations.
