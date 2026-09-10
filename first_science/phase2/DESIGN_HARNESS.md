# Phase 2 direct-trace design harness

This file mirrors the current PRAISE/CAO design document and acts as a hard development contract.

## Frozen provider information object

The public I1 schema is already frozen:

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`

with

`sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)`.

The horizon support is `H={0,5,...,240}` and the rho support is `R={0.95,0.975,0.9833333333333333,0.99,1.0}`. These definitions are not reopened by the direct-trace correction.

The private Phase-2 evidence is the frozen ProviderA/B/C provider-local request-ledger corpus extracted from the frozen physical regime on seeds `6000..6099`.

The active construction path is therefore

`T_i -> concrete provider-local A_i -> {sigma_i(A_i,H;rho) for all rho in R} -> I1_i`.

## Rho handling in Phase 2 - FROZEN

Phase 2 does **not** select a local `rho_i`.

`rho_i` is not an input to `T_i -> A_i` and is not part of provider-local A_i construction. Once `A_i` is fixed, Phase 2 materializes the full already-frozen `R` support into the I1 card.

A later method may consume one or more of those already-exposed rho slices according to its own separately frozen rule. No new rho value may be added after method outcomes are inspected.

## Only open Phase-2 scientific item

The only unresolved item is the concrete provider-local instantiation

`T_i -> A_i`.

This gap must not be expanded into a redesign of I1 itself or into a local-rho selection problem.

Until that concrete rule is explicitly agreed and frozen, Phase 2 must not:

- derive `A_i` from `A_G`;
- derive `A_i` from a chosen `rho_i`;
- split a global latency/cost/quality budget into provider budgets;
- define `A_i` by quantiles or percentiles;
- substitute a min/max support envelope without explicit agreement;
- search local `A_i` values to obtain an attractive local sigma shape;
- inspect Phase-1 global sigma, M0, or M1 outcomes to choose `A_i`;
- infer an unspecified `A_i` rule from historical code.

If implementation requires a concrete `A_i` rule and that rule is not explicit, the required behavior is **STOP AND RECONCILE ONLY `T_i -> A_i`**.

## What remains valid and read-only

- Phase-1 v2 benchmark and AR freeze;
- Phase-2 acquisition protocol;
- private ProviderA/B/C ledgers and their SHA-256 hashes;
- provider-local evidence audit;
- I1 card schema and sigma semantics;
- H/R support and accounting semantics;
- the decision that Phase 2 exposes all of R and selects no `rho_i`;
- `i1_provider_card.py` as the deterministic card builder once an exact `A_i` is supplied;
- generic Phase-3 M0 topology-aware LCQ composition kernel and its unit tests.

## M0 boundary

M0 does not choose `A_i`. Once Phase 2 freezes the three concrete `A_i` values and materializes/hash-freezes the corresponding I1 cards, M0 consumes those exact cards unchanged.

The M0 structural LCQ algebra is frozen. The separate question of which existing rho slice or slices M0 consumes is a Phase-3 method choice and is intentionally not fixed by Phase 2.
