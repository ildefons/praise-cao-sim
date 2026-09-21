# M2-B6 external white-box evaluation

**Status:** contract frozen and implementation ready.  
**Date:** 21 September 2026.

B6 evaluates the already-frozen M2-B5 predictions. It does not rerun graph simulation, search providers, change candidates, or change ensemble weights.

## Primary evaluation

On the identical frozen `A_G`, same-rho diagonal and horizon support, compare:

- M0 from the frozen public I1 product rule;
- M1 from the fresh same-seed `BASE_M1` curve produced inside B5;
- M2 from the frozen 27-member equal-weight ensemble mean;
- Phase-1 white-box sigma recomputed on the exact B5 `A_G`.

Point-prediction metrics are MAE, RMSE, bias and maximum absolute error, over the whole surface and per rho.

For the frozen M2 min-max ambiguity range, report white-box coverage, mean/max width, mean/max distance outside the range, and fractions below/above the range.

The M2 range is not a confidence interval.

## Scientific ordering

B6 is deliberately two-stage.

### 1. Freeze B5 prediction inputs without reading white-box evidence

```bash
python first_science/phase4/m2_b6_joint_ensemble_whitebox.py --prepare-only
```

Expected marker:

```
M2_B6_PREDICTIONS_FROZEN_BEFORE_WHITEBOX_PASS
```

This validates the full B5 manifest, checks the 27 equal-weight members plus separate M1 reference, verifies the B5 hashes and writes:

```
first_science/phase4/results/m2_b6_joint_ensemble_whitebox_v1/
  m2_b6_prediction_freeze_manifest_v1.json
```

No Phase-1 graph white-box file is opened in prepare-only mode.

### 2. External evaluation

Only after the prediction-freeze manifest exists:

```bash
python first_science/phase4/m2_b6_joint_ensemble_whitebox.py
```

The runner refuses evaluation if any frozen prediction-side hash has changed since prepare-only.

Expected marker:

```
M2_B6_EXTERNAL_WHITEBOX_EVALUATION_COMPLETE
```

## Outputs

```
m2_b6_prediction_freeze_manifest_v1.json
m2_b6_pointwise_comparison.csv
m2_b6_overall_point_summary.csv
m2_b6_per_rho_point_summary.csv
m2_b6_ambiguity_summary.csv
m2_b6_whitebox_curve.csv
m2_b6_m0_m1_m2_whitebox.png
m2_b6_evaluation_manifest_v1.json
```

G0 B6 results are retrospective diagnostic evidence because G0 white-box behavior was already known during M2 method development. The frozen M2 method must later be tested unchanged on an untouched predeclared condition for a prospective validation claim.
