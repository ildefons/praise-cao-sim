# WB / I1 provenance due diligence

**Date:** 22 September 2026  
**Status:** OPEN_INCIDENT_ROOT_CAUSE_IDENTIFIED  
**Execution policy:** no further G2 calibration or final M2 validation runs until this audit is closed.

## 1. Scope

This audit was opened after observing that the G0 and G1 white-box (WB) sigma surfaces differed radically while the frozen M0/M1/M2 predictions changed only modestly.

The question is whether this behavior reflects:

1. a failure of I1;
2. a failure of the I1 -> latent lift;
3. a failure of graph integration;
4. a failure of the experiment/provenance contract; or
5. a combination of these.

## 2. Scientific definition required for an M-axis integration test

For the intended fixed-I1 method sweep,

```
(I1,M0) -> (I1,M1) -> (I1,M2)
```

the WB reference must be the composed execution of the **same hidden provider processes that generated I1**, under the public graph/workload condition being tested.

Changing graph/topology/network parameters while holding the provider processes fixed is a valid integration-transfer experiment.

Changing the hidden provider processes while holding I1 fixed is a different experiment: stale-information/provider-drift robustness. It must not be interpreted as a pure integration-method accuracy test.

## 3. Reconstructed physical-regime history

### Final G0 regime

The final Phase-1 fresh-confirmation G0 benchmark used:

```
D300000000_d0.200
N = 100
seeds = 5000..5099
scientific_confirmation_pass = true
```

This final run superseded an earlier finalist.

### Superseded D330 finalist

`D330000000_d0.150` was an earlier N=10 proposal/freeze. Its fresh confirmation on seeds `4000..4099` failed the final selection gate (the mixed case exceeded the frozen area gate, approximately 0.7796 > 0.75). It was therefore **not** the final G0 physical regime.

### Source-file inconsistency

Despite that supersession, `phase1/config_phase1_discovery_v1.json` still contains:

```
confirmation.frozen_after_selection =
"D330000000_d0.150 matched latency/cost/mixed SLA-native battery"
```

while the current pilot design and Phase-2 I1 acquisition use `D300000000_d0.200`.

The tracked `phase1/selected_whiteboxes.json` is also still an empty placeholder, so it cannot repair this provenance gap.

This is a stale-source-of-truth defect.

## 4. I1 provenance

Both Phase-2 I1 acquisition roles are explicitly tied to the final D300 regime:

```
region construction T_i^Gamma:
    D300000000_d0.200
    seeds 6000..6099

sigma estimation T_i^sigma:
    D300000000_d0.200
    seeds 6100..6199
```

The public I1 therefore describes D300/d0.20 providers, not D330/d0.15 providers.

The pilot design independently states the frozen Phase-1 physical regime as `D300000000_d0.200`.

## 5. G0, G1 and G2 provenance status

### G0 B6

B6 reads:

```
phase1/results/phase1_v2_fresh_confirmation_v1/
    all_top_level_request_ledgers.csv
```

but the B6 contract pins only the ledger path and trajectory count. It does **not** pin a provider-process physical ID or hash.

Historical provenance establishes this ledger as the final D300 fresh-confirmation benchmark, but the evaluation contract itself does not enforce that invariant.

Status: **scientifically intended/matched, contractually under-specified**.

### Original G1

The G1 WB contract explicitly rebuilt the hidden providers as:

```
D330000000_d0.150
A mean instructions = 280.5M
B mean instructions = 330.0M
C mean instructions = 379.5M
```

while the frozen public I1 remained D300-derived.

Thus original G1 was not:

```
same providers + changed graph
```

It was:

```
changed hidden providers + stale D300 I1 + changed graph
```

Status: **invalid as a pure M-axis integration validation; valid only as a provider-drift/stale-information stress test**.

### Current G2 contract

The current frozen G2 Step-0 contract copied the same D330 hidden WB model.

Status: **BLOCKED before execution**. It must not be used for final M2 validation in its current form.

## 6. Paired corrected-G1 diagnostic

A paired N=20 forensic diagnostic was run using the exact original G1 seeds `31000..31019`.

Held fixed:

- G1 graph;
- workload;
- frozen A_G;
- M0 predictions;
- M1 predictions;
- M2 predictions.

Changed only:

```
original hidden WB:  D330000000_d0.150
corrected hidden WB: D300000000_d0.200
```

The WB surface moved upward by:

```
mean corrected - original sigma = +0.539592
mean absolute WB shift         = 0.539592
maximum pointwise WB shift     = 0.80
```

Against the I1-matched D300 N=20 WB:

```
M0 MAE = 0.380617, bias = -0.380617
M1 MAE = 0.244204, bias = +0.243959
M2 MAE = 0.132503, bias = +0.095654
```

The pathological near-zero G1 WB largely disappears when provider provenance is matched.

This is strong causal evidence that the original G1 discrepancy was dominated by the provider/I1 provenance mismatch.

It is not yet a publication-quality accuracy result because N=20 quantizes sigma in steps of 0.05.

## 7. What this does and does not establish

### Established

1. The provenance chain contained a concrete stale-source defect.
2. I1 was generated from D300 providers.
3. Original G1 WB used D330 providers.
4. M0/M1/M2 did not have information telling them that the hidden providers had changed.
5. Replacing only the mismatched WB provider regime with D300 causes a very large sigma correction.
6. Therefore original G1 cannot be used to diagnose the quality of the M-axis integration mechanisms alone.

### Not yet established

1. M1/M2 graph integration is fully correct.
2. M2 is publication-quality accurate.
3. The finite M2 ambiguity range is calibrated.
4. G2's admissibility-region calibration design is correct.
5. A D300 matched WB will remain favorable under every new composition condition.

These require separate checks.

## 8. Remaining due-diligence gates before any new scientific run

### DD-1: raw G0 ledger fingerprint

Read the existing G0 top-level ledger only. No simulation.

Verify that its request-cost moments are consistent with D300 rather than D330. Under the frozen provider family, expected total request cost is a strong physical fingerprint because queue waiting and network latency do not contribute to operating cost.

### DD-2: I1 materialization identity

Recompute the public rho-conditioned I1 sigma surfaces from the already-frozen private `T_i^sigma` corpus and verify exact/expected numerical identity with the public cards and manifest hashes.

No new trajectories.

### DD-3: boundary/composition implementation

Re-run existing deterministic/unit checks for:

```
L_G = fixed + max_i L_i
C_G = fixed + sum_i C_i
Q_G = min_i Q_i
```

and verify the G0/G1 fixed network terms independently.

No statistical scientific run.

### DD-4: local lift identity

For M1 and every frozen M2 provider representative, report local I1 reconstruction error and compare local request-distribution summaries against the same D300 I1 card.

This separates inverse-lift error from graph-integration error.

### DD-5: matched graph transfer

Only after DD-1..DD-4 pass, run one matched-provider graph transfer diagnostic. The WB provider-process fingerprint must equal the I1 provider-process fingerprint by construction.

## 9. Mandatory contract repair

Introduce a canonical provider-process provenance object, separate from the graph condition, for example:

```json
{
  "provider_process_family": "native_gamma_service_v1",
  "provider_instruction_means": {
    "ProviderA": 240000000,
    "ProviderB": 300000000,
    "ProviderC": 360000000
  },
  "instruction_cv": 0.3,
  "effective_IPT": 1000000000,
  "cost_rate": 3.0,
  "execution_fraction_x": 0.5,
  "quality": 0.5,
  "workload_period": 0.2
}
```

Hash the canonical object.

Every I1 manifest and every WB validation manifest must carry this provider-process fingerprint.

For a pure integration validation:

```
WB.provider_process_sha256 == I1.provider_process_sha256
```

must be a hard runtime invariant.

A mismatch may be permitted only if the experiment is explicitly declared as:

```
experiment_role = "provider_drift_or_stale_information_robustness"
```

and must never be reported as an M-axis integration-accuracy validation.

## 10. Current execution status

```
G0 = retained, matched D300 reference, provenance enforcement needs repair
G1 original = reclassified as mismatched-provider stress diagnostic
G1 corrected N20 = due-diligence evidence only
G2 = BLOCKED
M1/M2 = not condemned; further due diligence pending
M3 = deferred
```
