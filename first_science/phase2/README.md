# PRAISE first science - Phase 2 / I1

Phase 2 owns construction of the provider information object `I1`. Phase 1 is the frozen Step-0 white-box benchmark. The public I1 schema and the provider-local `T_i -> A_i` calibration rule are now frozen.

The active path is:

`frozen physical regime -> fresh Phase-2 full trajectories -> provider-local ledgers T_i -> calibrated provider-local A_i -> full sigma_i(A_i,H;rho) surface over R -> I1_i -> M0/M1`

There is no `A_G -> A_i` step and Phase 2 does not select a provider-specific `rho_i`.

## 2A - provider evidence acquisition - FROZEN

`config_phase2_i1_acquisition_v1.json` defines the completed acquisition protocol:

- frozen physical regime `D300000000_d0.200`;
- independent seeds `6000..6099`;
- 100 full native trajectories;
- each trajectory reduced to ProviderA/B/C local request ledgers;
- 119900 provider-request rows per provider;
- provider-corpus SHA-256 fingerprints in `phase2_i1_freeze_manifest_v1.json`.

## 2B - public I1 object - FROZEN

For each provider:

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`

with

`sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)`.

Frozen support:

- `H={0,5,...,240}`;
- `R={0.95,0.975,0.9833333333333333,0.99,1.0}`.

Provider traces remain private. The public card contains `A_i`, workload/context `W_i`, the frozen rho support, and the corresponding local sigma surface plus confidence metadata.

## 2C - T_i -> A_i calibration - FROZEN

The active rule is implemented in `i1_local_region.py` and encoded in `config_phase2_i1_provider_card_v2.json`.

Under the cumulative-admissibility semantics, freeze the anchor calibration at

- `rho_anchor = 0.95`,
- `H* = 120 s`,
- `sigma_target = 0.95`.

For each provider and for latency, cost and quality separately, scan observed local threshold candidates and select the threshold whose **first `sigma_i(A_i^X,H;rho_anchor)` crossing below 0.95 occurs closest to 120 s**. Combine those independently calibrated coordinate thresholds into

`A_i = {L_i <= l_i*, C_i <= c_i*, Q_i >= q_i*}`.

The resulting **joint** `sigma_i(A_i,120;0.95)` is not forced to 0.95. In the current anchor, quality is constant, so the unique observed `Q_i` value is retained directly.

This restores the already-agreed 0.95-at-120 trace calibration. It is not the rejected fixed-p95/p99 request-level percentile construction and it does not use M0/M1 outcomes.

## 2D - rho handling - FROZEN

Phase 2 selects **no provider-specific `rho_i`**. The `rho_anchor=0.95` above is the fixed global anchor query used during trace calibration, not an M0 tolerance allocation.

After `A_i` is fixed, the same provider evidence materializes the complete frozen `R` surface. M0 later reads the already-existing slice with `rho_i=rho_G` for every provider.

## 2E - current numerical diagnostic

`first_science/phase3/diagnose_real_wb_vs_i1_m0.py` derives the three `A_i` values from the frozen Phase-2 traces using the rule above, materializes the real I1 surfaces in memory, and compares

`sigma_hat_G,M0(H;rho_G) = product_i sigma_i(A_i,H;rho_G)`

against the independent Phase-1 v2 white-box sigma curve.

The diagnostic reports the coordinate crossing times, coordinate sigma values at `H*=120`, the resulting joint provider sigma at the anchor, the M0 product, WB values, and pointwise errors.

Full M0 boundary applicability, including deterministic pre/post/network terms, remains a separate check from this probability-composition diagnostic.

## Validation

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim
python first_science/phase2/test_phase2_direct_i1_contract.py
python first_science/phase3/test_diagnose_real_wb_vs_i1_m0.py
```

Expected markers include:

```text
PHASE2_DIRECT_I1_DESIGN_HARNESS_TESTS_PASS
A_I_H120_COORDINATE_CALIBRATION_FROZEN_PASS
REQUEST_LEVEL_PERCENTILE_A_I_BLOCKED_PASS
JOINT_SIGMA_NOT_FORCED_TO_CALIBRATION_TARGET_PASS

PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_TESTS_PASS
A_I_COORDINATE_FIRST_CROSSING_H120_RULE_PASS
CUMULATIVE_COORDINATE_ACCOUNTING_PASS
CONSTANT_QUALITY_NO_ARTIFICIAL_THRESHOLD_PASS
```

## Freeze rule

The Phase-1 benchmark, Phase-2 evidence, I1 schema, accounting semantics, H/R support, recovered `T_i -> A_i` calibration, and M0 same-rho rule are read-only unless a concrete scientific defect is found. Final I1 materialization and hash freezing can proceed once the calibrated card instances are inspected.
