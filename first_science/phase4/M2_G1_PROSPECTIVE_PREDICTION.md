# M2 G1 prospective prediction protocol

**Status:** frozen G1 contract implemented on the prediction side.  
**White-box status:** forbidden until the full blind prediction freeze exists.

## Frozen G1 condition

Logical composition is unchanged:

```
Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost
```

Provider workload, public I1 cards, fixed stages, message sizes, bandwidth, M1
parameters, M2 members and M2 weights are unchanged.

Only the public provider-branch propagation delays change:

```
ProviderA: PR = 0.005 s
ProviderB: PR = 0.015 s
ProviderC: PR = 0.001 s
```

The provider assignment was frozen mechanically from
`numpy.random.default_rng(20260921).permutation([0.001,0.005,0.015])`.

The induced latency boundary is

```
l_G1 = 0.012002 + max(
    l_A + 0.010001,
    l_B + 0.030001,
    l_C + 0.002001
)
```

with unchanged cost and quality algebra.

## 1. Prepare-only validation

This stage performs no graph simulation and reads no G1 white-box information:

```bash
python first_science/phase4/m2_g1_blind_prediction.py --prepare-only
```

Expected marker:

```
M2_G1_PREPARE_ONLY_COMPLETE_NO_WHITEBOX
```

Verify that the design contains `BASE_M1` plus all 27 frozen M2 joint
combinations and reports the G1 seed bank `30000..30099`.

## 2. Prediction-side smoke run

```bash
python first_science/phase4/m2_g1_blind_prediction.py --smoke
```

This runs five trajectories for each of the 28 variants and writes to the
separate smoke directory:

```
first_science/phase4/results/m2_g1_blind_prediction_smoke_v1/
```

Expected marker:

```
M2_G1_SMOKE_PREDICTION_COMPLETE_NO_WHITEBOX
```

Smoke output is implementation evidence only, not scientific evidence.

## 3. Full blind G1 prediction

After the smoke run passes:

```bash
/usr/bin/time -v python first_science/phase4/m2_g1_blind_prediction.py \
  2>&1 | tee m2_g1_blind_prediction_full.log
```

The run executes 28 x 100 = 2800 prediction-side graph trajectories using
common random numbers `30000..30099`.

Expected final marker:

```
M2_G1_BLIND_PREDICTIONS_FROZEN_BEFORE_WHITEBOX_PASS
```

Primary frozen outputs:

```
m2_g1_public_condition_manifest_v1.json
m2_g1_joint_variant_design.csv
m2_g1_frozen_candidate_set.csv
m2_g1_m0_curve.csv
m2_g1_joint_graph_sigma_curves.csv
m2_g1_ensemble_curve.csv
m2_g1_request_distribution_summary.csv
m2_g1_cost_manifest_v1.json
m2_g1_prediction_freeze_manifest_v1.json
ledgers/<variant_id>.csv
```

The full prediction-freeze manifest hashes the G1 contract, public I1 manifest,
M0/M1 contracts, M2 semantic contract, G1 adapter, G1 simulator, runner,
candidate inputs, M0 curve, all member curves, ensemble curve and variant
design. It records `G1_whitebox_generated=false` and
`G1_whitebox_read=false`.

## White-box gate

Do not implement, generate, inspect or run the actual G1 white box until the
full blind prediction run has completed and
`m2_g1_prediction_freeze_manifest_v1.json` exists.

Only then should a separate G1 white-box generator be implemented against the
already-frozen public G1 condition, using independent seeds `31000..31099`.
