# B0001: P1 × G_PAR raw-reference audit and reference uncertainty

## Purpose

The frozen seven-method accuracy evaluation found M1's overall MAE just below
M3_FULL343's, despite M3 outperforming M1 in 10 of 12 individual cells. The
largest reversal is **P1__G_PAR**. Before interpreting that reversal, we need
to (1) independently verify that the WB results were correctly scored from
the original request ledger and (2) estimate how much the ranking depends on
the 1,000 simulated reference trajectories per cell.

This is an **analysis-only** stage. Do **not** rerun the physical simulator,
alter any frozen predictor, edit any reference file, or retrain after seeing
these results. This stage does not replay the nine selection policies.

## Pull and test

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
python first_science/b1/planb_validation/test_audit_b0001_p1_gpar_and_reference_uncertainty_v1.py -v
```

## 1. Read-only preflight (no reference values read, no output written)

```bash
python first_science/b1/planb_validation/audit_b0001_p1_gpar_and_reference_uncertainty_v1.py \
  --check \
  --authorization ~/praise/planb_b0001_final_wb_authorization_seven_arm_v1 \
  --reference ~/praise/planb_b0001_final_wb_seven_arm_v1 \
  --graph ~/praise/planb_b0001_graph_isolated_v1 \
  --staging ~/praise/planb_b0001_public_inputs_v1 \
  --audit ~/praise/planb_b0001_postrun_audit_v1 \
  --seven-arm ~/praise/planb_b0001_seven_arm_blind_freeze_v1 \
  --four-arm ~/praise/planb_b0001_four_arm_graph_science_v1 \
  --refaudit ~/praise/planb_b0001_final_reference_audit_v2 \
  --accuracy ~/praise/planb_b0001_seven_method_accuracy_v1 \
  --out ~/praise/planb_b0001_raw_audit_reference_uncertainty_v1
```

Expected final lines:

```
B0001_RAW_REFERENCE_AND_BOOTSTRAP_PREFLIGHT_PASS
NO_REFERENCE_VALUES_READ / NO_SIMULATIONS / NO_WRITES
```

## 2. Independent raw audit and registered bootstrap

Run the **same command**, changing only `--check` to `--run` (keep all 10
paths, including a *new* output directory). The tool will:

1. Independently reconstruct, from each raw frozen request ledger, all 1,000
   trajectory-level SLA pass/fail outcomes for 15 queries and 49 horizons.
   The check uses emission, completion, latency deadline, cost, quality, the
   cumulative fraction of decided requests, and the zero-decision convention.
   It is separate from the original reference scorer's implementation.
2. Stop immediately if **any** of the 8,820 calculated WB success counts
   differs from the frozen reference CSV. Its accuracy join must also match
   the previously frozen seven-method scores exactly.
3. Summarize P1__G_PAR by all 15 frozen SLA queries, including M1/M3 biases
   and raw decided-request failure breakdowns.
4. Produce **10,000** reference bootstrap replicates using the frozen seed
   **2026100201**. For each replicate, draw 1,000 complete trajectory ordinals
   with replacement; **use the same sampled ordinals in all 12 cells**;
   keep every predictor fixed; recompute seven equal-cell mean MAEs.
5. Report percentile 95% intervals for each method, for paired
   `MAE(M3_FULL343) - MAE(M1)` (positive means M1's error is smaller), and
   for the anomaly-cell contrast alone. Report proportions of bootstrap
   resamples with M1 or M3 smaller and each method ranked first.

The bootstrap uses trajectories, *not* independently sampled query/horizon
points, because all observations within each trajectory are correlated.

Typical progress messages:

```
B0001_INDEPENDENT_RAW_SLA_REFERENCE_CELL_PASS P1__G_PAR 735/735
... (12 cells)
B0001_P1_G_PAR_RAW_LEDGER_ANOMALY_AUDIT_PASS
B0001_ALL_8820_RAW_REFERENCE_SCORES_MATCH_FROZEN
B0001_REFERENCE_BOOTSTRAP 512/10000
... (10,000 total)
B0001_P1_G_PAR_AND_JOINT_REFERENCE_UNCERTAINTY_V1_PASS
NO_SIMULATIONS / NO_PREDICTOR_CHANGES / NO_REFERENCE_CHANGES
```

Files produced in `~/praise/planb_b0001_raw_audit_reference_uncertainty_v1/`:

| File | Content |
|---|---|
| `b0001_raw_audit_reference_uncertainty_v1.json` | Provenance, checks, P1 anomaly summary, paired M1/M3 uncertainty |
| `p1_gpar_query_diagnostics.csv` | 15 per-query anomaly/failure diagnostics |
| `seven_method_reference_uncertainty.csv` | All seven MAE percentile intervals and first-rank frequencies |
| `reference_bootstrap_10000_replicates.csv` | 10,000 paired bootstrap outcomes for reproducibility |

## Interpretation restrictions

- An exact raw rescore **confirms arithmetic/accounting consistency**, not
  correctness of the hidden physical model or causal reasons for M3's error.
- Bootstrap intervals quantify **finite N=1,000 WB Monte Carlo reference
  uncertainty only**. They do not include uncertainty over new physical
  worlds, model misspecification, or predictor training randomness.
- There are **555 correlated query/horizon scores per cell**; they are not
  555 independent references. The primary seven-method ranking remains the
  originally frozen 12-cell result, whether or not the bootstrap interval
  crosses zero. Do not remove P1__G_PAR post hoc.
- If the independent rescore fails, **do not interpret/bootstrap**: retain the
  failed cell/point and investigate it without changing frozen inputs.

## What to return for interpretation

Send the final terminal output and these three small files:

1. `b0001_raw_audit_reference_uncertainty_v1.json`
2. `p1_gpar_query_diagnostics.csv`
3. `seven_method_reference_uncertainty.csv`

The large 10,000-replicate CSV can stay local unless we need to reproduce an
individual percentile or rank calculation.
