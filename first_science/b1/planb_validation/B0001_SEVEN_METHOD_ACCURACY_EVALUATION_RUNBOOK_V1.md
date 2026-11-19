# B0001 — Seven-method prediction accuracy (Step 1)

## Scientific question

Which of the seven **previously frozen** prediction algorithms is most
accurate against the **independently generated and mechanically audited**
B0001 white-box reference? This is the first accuracy evaluation, **not**
the nine-policy selection replay.

The primary estimand is the **equal-condition mean MAE** over the 12 cells
P1/P3/P4 × G_PAR/G_PARSEQ/G_SEQ/G_SEQPAR. Each cell's MAE averages the 15
frozen queries over H=60,65,...,240 seconds (**555 correlated prediction
points per cell**). This is the existing Phase5/B1 evaluation convention;
H=0..55 is not part of the primary metric. Correlated query/horizon points
must not be treated as 555 independent experiments.

The seven methods are M1, M2, M3_FULL343, ORIGINAL_TOP14_B1400,
ORIGINAL_TOP1_B1400, FIXED_CV_TOP14 and FIXED_CV_TOP1. M0 is excluded from
this **seven-method selection comparison**, as registered before reference.

## Pull, test and check

In `~/praise/praise-cao-sim` on branch `praise-identifiability-feasibility`:

```bash
git pull --ff-only origin praise-identifiability-feasibility
python -m unittest -v first_science/b1/planb_validation/test_evaluate_b0001_seven_method_accuracy_v1.py

python first_science/b1/planb_validation/evaluate_b0001_seven_method_accuracy_v1.py \
  --check \
  --authorization ~/praise/planb_b0001_final_wb_authorization_seven_arm_v1 \
  --reference ~/praise/planb_b0001_final_wb_seven_arm_v1 \
  --graph ~/praise/planb_b0001_graph_isolated_v1 \
  --staging ~/praise/planb_b0001_public_inputs_v1 \
  --audit ~/praise/planb_b0001_postrun_audit_v1 \
  --seven-arm ~/praise/planb_b0001_seven_arm_blind_freeze_v1 \
  --four-arm ~/praise/planb_b0001_four_arm_graph_science_v1 \
  --refaudit ~/praise/planb_b0001_final_reference_audit_v2 \
  --out ~/praise/planb_b0001_seven_method_accuracy_v1
```

Expected: `B0001_SEVEN_METHOD_ACCURACY_PREFLIGHT_PASS`.
The check performs **zero calculations of prediction errors, zero
simulations, and zero writes**. It rehashes prediction and reference files.

## Execute the evaluation

Repeat the same command, replacing `--check` with `--run`.
Do not change the paths, method definitions, prediction files, or reference.

Expected: `B0001_SEVEN_METHOD_ACCURACY_EVALUATION_PASS`.

The new output directory will contain:

| File | Contents |
| --- | --- |
| `seven_method_matrix.csv` | Canonical 84 method/condition MAEs (`method,world,graph,mae`) for the later selection-policy replay |
| `overall_accuracy.csv` | Seven rows: primary equal-cell MAE, RMSE, signed bias, maximum error and noise-adjusted RMSE |
| `method_cell_metrics.csv` | 84 rows: error measures for each algorithm × condition |
| `stratified_accuracy.csv` | World, graph, regime, rho and interaction summaries |
| `pointwise_primary_joined.csv` | 46,620 prediction/reference pairs in the registered H60..240 window |
| `b0001_seven_method_accuracy_evaluation_v1.json` | Input provenance and SHA-256 of all output tables |

The script refuses to overwrite an existing result directory, refuses any
input/output path overlap, and verifies against the **exact mechanical-audit
JSON separately uploaded November 19** (SHA-256
`211e5b75cef98bdc4232c4dc74c532705c936269a64513f6e5e9afbeffcca4e4`).

## Interpretation boundary

The results are **deterministic point estimates of predictive error** given
the finite N=1000 white-box reference. They do not yet include trajectory-
level bootstrap uncertainty, formal significance claims, or nine-policy
replay/regret analysis. RMSE adjusted for reference noise is a historical
descriptive correction, not a complete treatment of clustered uncertainty.

Please share the terminal output and, initially, these small files:

- `b0001_seven_method_accuracy_evaluation_v1.json`
- `seven_method_matrix.csv`
- `overall_accuracy.csv`
- `method_cell_metrics.csv`

We will inspect their integrity and scientific meaning before proceeding to
the separately frozen nine-policy replay (Step 2).
