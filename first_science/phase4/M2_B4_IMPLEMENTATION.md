# M2-B4: frozen-prediction graph white-box evaluation

## Scientific question

M2-B3 showed that different independently confirmed public-I1-compatible
provider reconstructions can induce very different graph-level sigma_G surfaces,
especially for ProviderC. M2-B4 asks which of those already-frozen graph
predictions agree with the frozen Phase-1 graph white-box evidence, and whether
the white-box curve lies inside the one-at-a-time prediction envelope.

M2-B4 is evaluation only. It does not run graph simulation, search provider
parameters, replace candidates, or retune a surrogate.

## Two-step firewall

M2-B4 deliberately requires two invocations.

First:

    python m2_b4_frozen_prediction_whitebox.py --prepare-only

This validates the completed non-smoke M2-B3 run and writes SHA-256 fingerprints
for:

- the M2-B3 manifest;
- the complete frozen graph-sigma curves;
- the frozen M2-B3 variant design;
- the public I1 manifest.

The prepare-only path does not read the graph white-box ledger.

Second:

    python m2_b4_frozen_prediction_whitebox.py

The evaluation refuses to start unless the previously written fingerprints still
match byte-for-byte. Only after that check does it open the frozen Phase-1 graph
ledger.

## Evaluation

For each rho on the same-rho diagonal, the Phase-1 graph white-box ledger is
re-evaluated using exactly the A_G boundary already stored in the frozen M2-B3
predictions. Every one of the ten prediction surfaces is compared with that same
white-box curve.

Reported metrics include whole-surface and per-rho MAE, RMSE, bias, and maximum
absolute error. Whole-surface MAE improvement relative to BASE_M1 is also
reported as a descriptive post-hoc evaluation quantity.

Two envelopes are computed pointwise over (rho,H):

1. all ten frozen one-at-a-time predictions, including BASE_M1;
2. the nine A4 substitution predictions excluding BASE_M1.

For each envelope the runner reports white-box coverage fraction, mean/max
envelope width, and mean/max distance of white-box points that fall outside the
envelope.

## Outputs

The output directory is:

    results/m2_b4_frozen_prediction_whitebox_v1/

Key files are:

- m2_b4_prediction_freeze_manifest_v1.json
- m2_b4_variant_accuracy_summary.csv
- m2_b4_per_rho_accuracy_summary.csv
- m2_b4_prediction_whitebox_comparison.csv
- m2_b4_prediction_envelopes.csv
- m2_b4_envelope_metrics.csv
- m2_b4_providerC_vs_whitebox.png
- m2_b4_all10_envelope_vs_whitebox.png
- m2_b4_whitebox_evaluation_manifest_v1.json

## Interpretation gate

After M2-B4, interpret whether the frozen one-at-a-time inverse ambiguity explains
the graph white-box behavior. Do not automatically launch a 3x3x3 factorial or
retune provider surrogates from graph white-box results.
