# PRAISE first science - Phase 2 / I1

Phase 2 owns construction of the provider information object `I1`. Phase 1 is the frozen Step-0 white-box benchmark. The public I1 schema is already frozen. The only currently open Phase-2 scientific item is the concrete provider-local instantiation `T_i -> A_i`.

The active path is:

`frozen physical regime -> fresh Phase-2 full trajectories -> provider-local subtraces/ledgers T_i -> concrete provider-local A_i -> sigma_i(A_i,H;rho) -> frozen I1_i -> M0/M1`

There is no `A_G -> A_i` step.

## 2A - provider evidence acquisition - FROZEN AND RETAINED

`config_phase2_i1_acquisition_v1.json` defines the completed acquisition protocol:

- frozen physical regime `D300000000_d0.200`;
- independent seeds `6000..6099`;
- 100 full native trajectories;
- each full trajectory reduced to ProviderA/B/C local request ledgers;
- 119900 provider-request rows per provider;
- provider-corpus SHA-256 fingerprints recorded in `phase2_i1_freeze_manifest_v1.json`.

The provider evidence and hashes remain read-only. `inspect_provider_local_evidence.py` audits these exact ledgers.

## 2B - public I1 object - FROZEN

`config_phase2_i1_provider_card_v2.json` is the active public-card contract.

For each provider:

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`

with

`sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)`.

The frozen support is:

- `H={0,5,...,240}`;
- `R={0.95,0.975,0.9833333333333333,0.99,1.0}`.

The provider traces/ledgers remain private. The public object contains the fixed local admissibility region `A_i`, workload/context information `W_i`, the frozen rho support, and the corresponding local sigma surface plus confidence metadata.

The I1 schema is not reopened by the direct-trace correction.

## 2C - direct-trace A_i instantiation - CURRENT HARD STOP

`config_phase2_i1_direct_trace_v2.json` and `DESIGN_HARNESS.md` enforce the exact remaining boundary.

The only unresolved mapping is:

`T_i -> A_i`.

`A_i` belongs to Phase-2 information construction and must come from provider `i`'s own frozen local evidence. M0 and M1 may not choose or alter it.

Until the exact operational rule is explicitly agreed and frozen, Phase 2 must not:

- derive `A_i` from `A_G`;
- split a global latency/cost/quality budget into local budgets;
- define `A_i` using quantiles or percentiles;
- silently replace percentiles with a min/max support envelope;
- search `A_i` values to obtain a preferred local sigma shape;
- use Phase-1 global sigma, M0, or M1 outcomes to choose `A_i`;
- infer an unspecified rule from historical code.

If code needs a concrete `A_i` before that rule is explicit, the required action is **STOP AND RECONCILE ONLY `T_i -> A_i`**. Do not reopen I1.

## 2D - final I1 materialization - BLOCKED ONLY ON 2C

Once the three concrete `A_i` values are frozen, `i1_provider_card.py` can deterministically compute

`sigma_i(A_i,H;rho)`

from the existing provider-local ledgers for the complete frozen `H x R` support. No simulator rerun is required merely to materialize those surfaces.

The final cards are then inspected and hash-frozen. The exact same finished I1 cards are supplied unchanged to M0 and M1.

## Removed premature branch

The percentile-based local-AR diagnostic and p99/p99/minQ materialization branch were removed because they filled the open `T_i -> A_i` step with an unagreed choice. Their removal does not change the frozen I1 schema.

## Phase-3 boundary

The generic M0 topology-aware structural kernel is already frozen and unit-tested. Numerical M0 evaluation is blocked only until the concrete `A_i` values and final I1 card instances are frozen.

## Validation

Starting from the repository root:

```bash
python first_science/phase2/test_phase2_direct_i1_contract.py
python first_science/phase2/inspect_provider_local_evidence.py
```

Expected harness markers:

```text
PHASE2_DIRECT_I1_DESIGN_HARNESS_TESTS_PASS
I1_SCHEMA_REMAINS_FROZEN_PASS
ONLY_T_I_TO_A_I_INSTANTIATION_OPEN_PASS
PERCENTILE_A_I_BRANCH_REMOVED_PASS
M0_KERNEL_PRESERVED_PENDING_FINAL_I1_INSTANCES_PASS
```

## Freeze rule

The acquisition evidence, I1 schema, sigma semantics, H/R support, accounting semantics, and M0 structural kernel are read-only. The only open design choice is the concrete provider-local `T_i -> A_i` rule. Once that is frozen, Phase 2 proceeds mechanically to final card materialization and hash freeze.
