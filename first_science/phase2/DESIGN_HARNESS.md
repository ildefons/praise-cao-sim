# Phase 2 direct-trace design harness

This file mirrors the current PRAISE/CAO design and acts as a hard development contract.

## Frozen provider information object

The public I1 schema is frozen:

`I1_i=(A_i,W_i,R,{sigma_i(A_i,H;rho): H in H, rho in R})`

with

`sigma_i(A_i,H;rho)=P(c_i(A_i,H)>=rho)`.

The horizon support is `H={0,5,...,240}` and `R={0.95,0.975,0.9833333333333333,0.99,1.0}`.

The active construction path is

`T_i -> calibrated provider-local A_i -> full sigma_i(A_i,H;rho) surface -> hash-frozen public I1_i`.

## Rho handling in Phase 2 - FROZEN

Phase 2 does not select a provider-specific `rho_i`. The A_i calibration uses the frozen anchor query `rho_anchor=0.95`. After A_i is fixed, Phase 2 materializes the complete frozen R support. M0 later reads `rho_i=rho_G` at evaluation time.

## T_i -> A_i - FROZEN

For each provider and each coordinate `X in {L,C,Q}` separately, scan observed provider-local threshold candidates and compute `sigma_i(A_i^X,H;rho_anchor)`.

Freeze `rho_anchor=0.95`, `H*=120 s`, and `sigma_target=0.95`. Choose the coordinate threshold whose first crossing below `sigma_target` occurs closest to `H*`. Combine the thresholds into

`A_i={L_i<=l_i*, C_i<=c_i*, Q_i>=q_i*}`.

The joint `sigma_i(A_i,120;0.95)` is an observed outcome, not a calibration target. Constant Q uses its unique observed value.

## Materialization and handoff - FROZEN

`materialize_frozen_i1_cards.py` is the only production materializer. It must:

- verify the frozen private provider-corpus hashes before use;
- derive A_i only with the frozen rule above;
- build the complete H x R public card;
- write one `card.json` and `sigma_surface.csv` per provider;
- hash those public artifacts in `i1_card_instances_manifest_v1.json`;
- give exactly those same files to M0 and M1.

The generated instance manifest is the authoritative record that concrete I1 instances exist. Source-code configuration must not pretend that a runtime materialization has occurred.

## Phase-3 firewall - FROZEN

Phase 3 must not read private provider ledgers, acquisition seeds, or hidden provider parameters. It must not run `T_i -> A_i` again. It may only load and hash-verify the public I1 instances.

White-box Phase-1 outcomes are allowed only after an M0 prediction has been formed, for evaluation.

## Forbidden constructions

Phase 2 must not derive A_i from A_G, a provider-specific rho_i, a global budget split, fixed request-level p95/p99 targets, support extrema, or M0/M1/white-box outcomes. The calibration may not be changed after seeing WB-vs-M0 results.

## M0 boundary - FROZEN

M0 consumes the public Phase-2 cards unchanged. For a global query `(A_G,H,rho_G)`, it reads `rho_i=rho_G` for every required provider and, under the independent-local-events anchor,

`sigma_hat_G,M0(H;rho_G)=product_i sigma_i(A_i,H;rho_G)`.

M0 performs no equal-violation-budget redistribution. The product is an analytic baseline prediction, not a global-rho certificate. Full applicability additionally requires the forward-composed A_i boundary, including deterministic graph/network terms, to be contained in A_G.
