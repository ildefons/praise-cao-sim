# PRAISE first science - Phase 2 / I1

Phase 2 owns construction of the provider information object `I1`. Phase 1 is the frozen Step-0 white-box benchmark. Numerical M0/M1 evaluation starts only after the public I1 representation is explicitly frozen, materialized, inspected, and hash-frozen.

The current evidence path is deliberately simple:

`frozen physical regime -> fresh Phase-2 full trajectories -> provider-local subtraces/ledgers T_i -> explicitly frozen public I1_i`

There is no `A_G -> A_i` step and no provider-envelope calibration step authorized by the current design.

## 2A - provider evidence acquisition - FROZEN AND RETAINED

`config_phase2_i1_acquisition_v1.json` defines the completed acquisition protocol:

- frozen physical regime `D300000000_d0.200`;
- independent seeds `6000..6099`;
- 100 full native trajectories;
- each full trajectory reduced to ProviderA/B/C local request ledgers;
- 119900 provider-request rows per provider;
- provider-corpus SHA-256 fingerprints recorded in `phase2_i1_freeze_manifest_v1.json`.

The old `phase2_i1_freeze_manifest_v1.json` remains the evidence-corpus checkpoint. Historical statements in that manifest about who supplies `A_i` are not an active final-I1 design contract. The underlying provider evidence and hashes are unchanged.

`inspect_provider_local_evidence.py` is the read-only audit of these exact ledgers.

## 2B - direct-trace construction principle - FROZEN

`config_phase2_i1_direct_trace_v2.json` and `DESIGN_HARNESS.md` mirror the current design document.

The frozen principle is:

`T_i -> explicitly specified I1_i`

where `T_i` is provider `i`'s frozen local evidence. The implementation must not insert an unstated transformation merely because older code expects one.

The following are explicitly forbidden unless the design document is revised first:

- `A_G -> A_i` localization;
- global latency/cost/quality budget splitting;
- quantile or percentile based `A_i` construction;
- replacing percentiles by min/max support extrema without an explicit design decision;
- searching local `A_i` values to obtain a preferred sigma shape;
- using Phase-1 global sigma, M0, or M1 outcomes to construct I1;
- inferring unresolved scientific choices from historical code.

If implementation needs an unspecified scientific choice, the required action is **STOP AND RECONCILE THE DESIGN DOCUMENT**.

## 2C - public I1 representation - REOPENED / CURRENT HARD STOP

The previous active schema

`I1_i=(A_i,W_i,R,{sigma_i(A_i,H;rho)})`

is reopened because forcing the direct provider traces through a required single rectangular `A_i` repeatedly led to invented envelope-selection rules. It remains useful historical code, but it is not currently authorized as the final public I1 contract.

"Use the traces directly" fixes the evidence path. It does not, by itself, mean that raw private ledgers become public. The exact public transformation

`I1_i = F(T_i)`

must be written and frozen in the design document before more final-I1 materialization code is written.

The previously frozen H/rho support is retained as reserved support if the reconciled representation still contains a cumulative-admissibility sigma surface. It is not permission to assume that the old single-`A_i` schema survives unchanged.

## 2D - M0/M1 boundary while I1 is reopened

The generic Phase-3 M0 topology-aware LCQ composition kernel remains frozen and unit-tested. It may continue to exist independently of the final I1 adapter.

However, numerical `I1 -> M0` consumption is blocked until the final public I1 representation is frozen. M0 may not force a particular provider representation merely because its current structural kernel accepts rectangular local contracts.

The same rule applies to M1: no final M1 fitting/integration code may dictate the I1 representation.

## Removed premature branch

The percentile-based local-AR diagnostic and the p99/p99/minQ materialization branch were removed because they violated the design harness. They are not part of the active Phase-2 implementation.

## Validation

Starting from the repository root:

```bash
python first_science/phase2/test_phase2_direct_i1_contract.py
python first_science/phase2/inspect_provider_local_evidence.py
```

Expected harness markers:

```text
PHASE2_DIRECT_I1_DESIGN_HARNESS_TESTS_PASS
UNSPECIFIED_I1_REPRESENTATION_HARD_STOP_PASS
PERCENTILE_A_I_BRANCH_REMOVED_PASS
M0_STRUCTURAL_KERNEL_PRESERVED_NUMERIC_ADAPTER_BLOCKED_PASS
```

The evidence audit should continue to verify the already frozen ProviderA/B/C corpus hashes.

## Freeze rule

The provider acquisition evidence is read-only. The next scientific action is not card materialization. It is to state the exact public direct-trace I1 representation in the design document. Only after that representation is explicitly frozen may implementation continue.
