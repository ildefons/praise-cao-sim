# Phase 2 direct-trace design harness

This file mirrors the current PRAISE/CAO design and acts as a hard development contract.

## Frozen provider information object

The public I1 schema is frozen:

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`

with

`sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)`.

The horizon support is `H={0,5,...,240}` and the rho support is `R={0.95,0.975,0.9833333333333333,0.99,1.0}`.

The private Phase-2 evidence is the frozen ProviderA/B/C provider-local request-ledger corpus from seeds `6000..6099`.

The active construction path is

`T_i -> calibrated provider-local A_i -> full sigma_i(A_i,H;rho) surface -> I1_i`.

## Rho handling in Phase 2 - FROZEN

Phase 2 does **not** select a provider-specific `rho_i`.

The recovered A_i calibration uses the already-frozen anchor global query `rho_anchor = rho_G = 0.95`. This number belongs to the anchor trace-calibration experiment, not to an M0 allocation of provider tolerances. After `A_i` is fixed, Phase 2 materializes the complete frozen `R` support.

A later method may consume one or more already-exposed rho slices. For M0, that separate Phase-3 rule is `rho_i = rho_G` at evaluation time.

## T_i -> A_i - FROZEN

The concrete provider-local rule is the recovered 0.95-at-120 coordinate calibration.

For each provider and each coordinate `X in {L,C,Q}` separately, scan observed provider-local threshold candidates and compute the cumulative-admissibility curve

`sigma_i(A_i^X,H;rho_anchor)`.

Freeze

- `rho_anchor = 0.95`,
- `H* = 120 s`,
- `sigma_target = 0.95`.

Choose the coordinate threshold whose **first crossing below `sigma_target` occurs closest to `H*`**. Then combine the independently calibrated thresholds into

`A_i = {L_i <= l_i*, C_i <= c_i*, Q_i >= q_i*}`.

The **joint** `sigma_i(A_i,120;0.95)` is not forced to equal 0.95. It is an outcome of combining the coordinate thresholds. In the current anchor `Q_i` is constant, so its unique observed value is used directly rather than fabricating a quality crossing.

This is a predeclared trace-only calibration. It is not post-hoc tuning against M0 or M1.

## Forbidden constructions

Phase 2 must not:

- derive `A_i` from the global boundary `A_G`;
- derive `A_i` from a provider-specific `rho_i`;
- split a global latency/cost/quality budget into provider budgets;
- replace the frozen rule by a fixed request-level p95/p99 or other percentile target;
- replace it by a support min/max envelope;
- inspect Phase-1 global sigma, M0, or M1 outcomes to choose `A_i`;
- change the calibration after seeing the WB-vs-M0 diagnostic.

## What remains valid and read-only

- Phase-1 v2 benchmark and AR freeze;
- Phase-2 acquisition protocol and provider-ledger hashes;
- provider-local evidence audit;
- I1 card schema, H/R support, and accounting semantics;
- the recovered `T_i -> A_i` coordinate calibration;
- the decision that Phase 2 exposes all of `R` and selects no provider-specific `rho_i`;
- the frozen Phase-3 M0 topology-aware LCQ composition kernel and same-rho probability rule.

## M0 boundary - FROZEN

M0 does not choose `A_i`. It consumes the Phase-2 cards unchanged.

For a global query `(A_G,H,rho_G)`, the frozen M0 rho rule is

`rho_i = rho_G  for every required provider`.

Under M0's deliberately simple independent-local-events model,

`sigma_hat_G,M0(H;rho_G) = product_i sigma_i(A_i,H;rho_G)`.

M0 performs no equal-violation-budget redistribution. This product is an analytic baseline prediction, not a guaranteed global-rho certificate.

The forward LCQ boundary algebra remains topology-aware. Full M0 applicability to an exogenous `A_G` additionally requires the forward-composed fixed `A_i` boundary, including deterministic graph/network terms, to be contained in `A_G`.
