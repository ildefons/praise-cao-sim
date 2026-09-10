# Phase 2 rho-conditioned I1 design harness

This file mirrors the current PRAISE/CAO design and acts as a hard development contract.

## Public provider information object

The active public I1 object is

`I1_i=({A_i(rho_region)},W_i,R_region,R_query,{sigma_i(A_i(rho_region),H;rho_query)})`

with

`sigma_i(A_i(rho_region),H;rho_query)=P(c_i(A_i(rho_region),H)>=rho_query)`.

The horizon support is `H={0,5,...,240}` and

`R_region=R_query={0.95,0.975,0.9833333333333333,0.99,0.995}`.

`rho_region=1` is forbidden for the current finite GMM-content construction because a Gaussian mixture has unbounded support.

The official first M0/M1 evaluation uses only

`rho_region=rho_query=rho_i=rho_G`.

The off-diagonal Cartesian card surface remains available for later sensitivity work but does not define an automatic local-to-global rho allocation rule.

## Evidence partition - FROZEN

The two scientific roles must use trajectory-disjoint private evidence.

`T_i^Gamma` is the existing frozen 100-trajectory corpus from `config_phase2_i1_acquisition_v1.json`. It is used only to fit the joint provider model and construct `A_i(rho_region)`.

`T_i^sigma` is the independent 100-trajectory corpus from `config_phase2_i1_sigma_acquisition_v1.json`. It is used only to estimate `sigma_i(A_i(rho_region),H;rho_query)` after the regions are fixed.

Required invariant:

`T_i^Gamma ∩ T_i^sigma = empty` at the trajectory-seed level.

The active frozen banks are `6000..6099` for `T_i^Gamma` and `6100..6199` for `T_i^sigma`.

The materializer must hash-verify both corpora, verify that the sigma acquisition manifest matches its frozen contract, and reject overlapping seed banks or identical provider-corpus hashes.

## T_i^Gamma -> A_i(rho_region) - FROZEN

For each provider:

1. use completed `(L,C,Q)` observations from `T_i^Gamma` only;
2. require current-benchmark Q to be degenerate and preserve its exact value;
3. fit a full-covariance Gaussian mixture in `(log L,log C)`;
4. choose `K` by minimum BIC over the predeclared range `1..4`;
5. draw one deterministic `N=100000` sample from the fitted joint model;
6. for each increasing `rho_region`, choose the minimum-area origin-anchored rectangle `[0,l]x[0,c]` containing at least the requested model probability content;
7. constrain successive regions to be nested.

Thus

`Gamma(T_i^Gamma,rho_region)=A_i(rho_region)`.

Phase-1 white-box outcomes, `T_i^sigma`, M0 results, and M1 results are forbidden inputs to Gamma.

## T_i^sigma -> sigma surface - FROZEN

After all `A_i(rho_region)` regions are fixed, estimate the complete

`A_i(rho_region) x rho_query x H`

surface using only `T_i^sigma`.

The region-construction corpus `T_i^Gamma` must not be reused to estimate the public sigma surface. This prevents self-calibration bias.

The established cumulative provider-local request-decision semantics remain unchanged, including Wilson trajectory-level confidence intervals.

## Materialization and handoff - FROZEN

`materialize_rho_conditioned_i1_cards.py` is the active rho-conditioned materializer. It must:

- derive regions from `T_i^Gamma` only;
- estimate sigma from `T_i^sigma` only;
- verify trajectory-seed disjointness and corpus hashes before use;
- build the complete `H x R_region x R_query` public card;
- expose no private traces, seeds, fitted GMM parameters, BIC tables, or synthetic samples;
- hash the public `card.json` and `sigma_surface.csv` artifacts;
- give exactly the same public files to M0 and M1.

The historical `materialize_frozen_i1_cards.py` and `results/i1_cards_v1/` are provenance only and are not the active scientific construction.

## Phase-3 firewall - FROZEN

Phase 3 must not read `T_i^Gamma`, `T_i^sigma`, acquisition seeds, fitted GMM parameters, or hidden provider parameters. It must not reconstruct `A_i`.

Phase 3 may only load and hash-verify finished public rho-conditioned I1 instances. White-box Phase-1 outcomes are allowed only after an M0/M1 prediction has been formed, for external evaluation.

## M0 baseline - FROZEN

M0 consumes the public Phase-2 cards unchanged. On the official same-rho diagonal, the independent all-required anchor uses

`sigma_hat_G,M0(H;rho_G)=product_i sigma_i(A_i(rho_G),H;rho_G)`.

Its LCQ topology algebra and deterministic Phase-1 graph/network adapter are unchanged. Because `A_i` now depends on `rho_G`, the induced `A_G^M0(rho_G)` may also vary with rho.

Evaluation reports region agreement `J_A` and whole-horizon sigma MAE together. When regions differ, sigma MAE is a joint reference discrepancy and must not be described as isolated probability-composition error.

## Forbidden constructions

Phase 2 must not derive `A_i` from `A_G`, Phase-1 white-box outcomes, M0/M1 results, a post-hoc global budget split, or the sigma-estimation corpus. It must not reuse the same trajectories to both select `A_i(rho)` and estimate their public sigma curves.

Do not start the I1-M1 numerical fit until the independent-evidence I1 materialization and the resulting M0 two-axis diagnostic have been inspected and accepted.
