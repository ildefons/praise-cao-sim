# PRAISE first science - Phase 2 / I1

Phase 2 owns construction of the provider information object `I1`. Phase 1 is the frozen Step-0 white-box benchmark. The public I1 schema is already frozen. The only currently open Phase-2 scientific item is the concrete provider-local instantiation `T_i -> A_i`.

The active path is:

`frozen physical regime -> fresh Phase-2 full trajectories -> provider-local subtraces/ledgers T_i -> concrete provider-local A_i -> full sigma_i(A_i,H;rho) surface over R -> frozen I1_i -> M0/M1`

There is no `A_G -> A_i` step and Phase 2 does not select a local `rho_i`.

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

The provider traces/ledgers remain private. The public object contains the fixed local admissibility region `A_i`, workload/context information `W_i`, the entire frozen rho support, and the corresponding local sigma surface plus confidence metadata.

The I1 schema is not reopened by the direct-trace correction.

## 2C - rho handling - FROZEN

Phase 2 selects **no special local `rho_i`**.

`rho_i` is not an input to `T_i -> A_i`. Once `A_i` is fixed, the complete frozen `R` support is materialized from the same provider-local evidence. This deliberately leaves multiple already-declared rho slices available to M0 and M1.

Which slice or slices a method consumes is part of that method's own frozen composition/integration rule. Phase 2 neither chooses the slice nor adds new rho values after seeing method results.

For M0, that separate Phase-3 choice is now frozen as `rho_i=rho_G` for every required provider. This does not change Phase-2 construction: I1 still exposes the whole frozen `R` support and selects no method-specific local rho.

## 2D - direct-trace A_i instantiation - CURRENT HARD STOP

`config_phase2_i1_direct_trace_v2.json` and `DESIGN_HARNESS.md` enforce the exact remaining boundary.

The only unresolved mapping is:

`T_i -> A_i`.

`A_i` belongs to Phase-2 information construction and must come from provider `i`'s own frozen local evidence. M0 and M1 may not choose or alter it.

Until the exact operational rule is explicitly agreed and frozen, Phase 2 must not:

- derive `A_i` from `A_G`;
- derive `A_i` from a chosen `rho_i`;
- split a global latency/cost/quality budget into local budgets;
- define `A_i` using quantiles or percentiles;
- silently replace percentiles with a min/max support envelope;
- search `A_i` values to obtain a preferred local sigma shape;
- use Phase-1 global sigma, M0, or M1 outcomes to choose `A_i`;
- infer an unspecified rule from historical code.

If code needs a concrete `A_i` before that rule is explicit, the required action is **STOP AND RECONCILE ONLY `T_i -> A_i`**. Do not reopen I1 and do not introduce a local-rho choice.

## 2E - final I1 materialization - BLOCKED ONLY ON A_i

Once the three concrete `A_i` values are frozen, `i1_provider_card.py` can deterministically compute the entire

`{sigma_i(A_i,H;rho): H in H, rho in R}`

surface from the existing provider-local ledgers. No simulator rerun is required merely to materialize those surfaces.

The final cards are then inspected and hash-frozen. The exact same finished I1 cards are supplied unchanged to M0 and M1.

## Removed premature branch

The percentile-based local-AR diagnostic and p99/p99/minQ materialization branch were removed because they filled the open `T_i -> A_i` step with an unagreed choice. Their removal does not change the frozen I1 schema or rho support.

## Phase-3 boundary - M0 FROZEN

The M0 topology-aware LCQ kernel and probability rule are now frozen and unit-tested. For a global query `(A_G,H,rho_G)`, M0 reads every provider card at the same already-exposed rho slice `rho_i=rho_G` and, under its independent-local-events model, predicts

`sigma_hat_G,M0(H;rho_G) = product_i sigma_i(A_i,H;rho_G)`.

It performs no equal-violation-budget redistribution and does not claim a global-rho lower-bound certificate. This deliberate limitation is part of the baseline comparison with richer methods.

## Validation

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim
python first_science/phase2/test_phase2_direct_i1_contract.py
python first_science/phase2/inspect_provider_local_evidence.py
python first_science/phase3/test_m0_analytic_composition.py
```

Expected contract markers include:

```text
PHASE2_DIRECT_I1_DESIGN_HARNESS_TESTS_PASS
I1_SCHEMA_REMAINS_FROZEN_PASS
ONLY_T_I_TO_A_I_INSTANTIATION_OPEN_PASS
PERCENTILE_A_I_BRANCH_REMOVED_PASS
M0_SAME_RHO_POLICY_FROZEN_PASS

PHASE3_M0_ANALYTIC_COMPOSITION_TESTS_PASS
M0_FORWARD_BOUNDARY_ALGEBRA_PASS
M0_SAME_RHO_POLICY_PASS
M0_INDEPENDENT_PRODUCT_BASELINE_PASS
M0_NOT_A_CERTIFICATE_PASS
```

## Freeze rule

The acquisition evidence, I1 schema, sigma semantics, H/R support, accounting semantics, the no-`rho_i` Phase-2 rule, and the Phase-3 same-rho M0 baseline are read-only. The only open Phase-2 design choice is the concrete provider-local `T_i -> A_i` rule. Once that is frozen, Phase 2 proceeds mechanically to final card materialization and hash freeze, after which numerical M0 evaluation can begin.
