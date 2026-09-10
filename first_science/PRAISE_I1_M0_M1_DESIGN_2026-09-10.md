# PRAISE/CAO: I1-M0 and I1-M1

**Status:** execution source of truth. Phase 1 v2, rho-conditioned I1, and M0 are frozen. M1 is the next design stage.  
**Date:** 10 September 2026.

This note supersedes the 1 September execution-ready design where the two conflict.

## 1. Frozen state

- Phase 1 v2 is the technology-neutral white-box benchmark.
- Phase 2 I1 is the rho-conditioned, independent-evidence provider card construction.
- Phase 3 M0 is the topology-aware analytic boundary-case baseline.
- M0 and M1 receive exactly the same finalized public I1 cards.
- Neither M0 nor M1 may access `T_i^Gamma`, `T_i^sigma`, fitted GMMs, hidden provider parameters, or Phase-1 provider traces.
- The PPG firewall remains strict.

## 2. Authoritative sigma semantics

For admissibility region `A`, horizon `H`, and threshold `rho`, let `c_G(A,H)` be the fraction of requests decided by `H` that satisfy `A`. Requests not yet decided by `H` are excluded from the denominator; before any decision the frozen compliance fraction is `1.0`.

`sigma_G(A,H;rho) = P(c_G(A,H) >= rho)`.

This is not a first-passage/no-violation functional. A trajectory can fall below `rho` and later recover, so sigma may be non-monotone in `H`. Historical `T_violation` semantics are not authoritative for the current v2/I1/M0 experiment.

## 3. Frozen Phase-1 reference battery

Matched physical regime: `D300000000_d0.200`, root period `0.2 s`, `H in [0,240] s`, current `Q=0.5` degenerate benchmark.

| Role | Case | L max | C max | Q min |
| --- | --- | ---: | ---: | ---: |
| latency | `V2_LATENCY` | 0.68855284199994315 | 2.60390295517990822 | 0.5 |
| cost | `V2_COST` | 0.74739413900001495 | 2.13979268099999986 | 0.5 |
| mixed | `V2_MIXED` | 0.74739413900001495 | 2.17409932499999980 | 0.5 |

Authoritative freeze: `phase1/phase1_v2_ar_freeze_manifest_v1.json`.

## 4. Frozen I1

`I1_i = ({A_i(rho_region)}, W_i, R_region, R_query, {sigma_i(A_i(rho_region),H;rho_query)})`.

Evidence is trajectory-disjoint:

- `T_i^Gamma`, seeds `6000..6099`, fits the joint model and constructs `A_i(rho_region)` only.
- `T_i^sigma`, seeds `6100..6199`, estimates the public sigma surface only after regions are fixed.

For each provider, fit a full-covariance GMM in `(log L, log C)`, choose `K=1..4` by minimum BIC, draw one deterministic `N=100000` model sample, and extract nested minimum-area origin-anchored `[0,l]x[0,c]` probability-content rectangles. Preserve current `Q=0.5` exactly.

`R_region = R_query = {0.95,0.975,0.9833333333333333,0.99,0.995}`.

`rho_region=1` is excluded because the GMM has unbounded support.

The complete Cartesian region-rho x query-rho x H surface is public. The first M0/M1 comparison uses only

`rho_region=rho_query=rho_i=rho_G`.

Authoritative freeze: `phase2/phase2_i1_rho_conditioned_freeze_manifest_v1.json`.

## 5. Frozen M0

Boundary algebra:

- Sequence: `L=sum, C=sum, Q=min`.
- ParAll: `L=max, C=sum, Q=min`.
- G0 adapter: `l_G=0.013003+max_i(l_i)`, `c_G=0.03+sum_i(c_i)`, `q_G=min_i(q_i)`.

Probability rule:

`sigma_hat_G,M0(H;rho_G)=product_i sigma_i(A_i(rho_G),H;rho_G)`.

This product is a deliberately minimal baseline prediction. Under cumulative-compliance semantics it is **not** a guaranteed lower bound or certificate because `c_i>=rho_G` for every provider does not generally imply `c_G>=rho_G`.

Evaluation retains both:

- region agreement `J_A` and whole-horizon sigma MAE against each frozen WB reference;
- same-region probability diagnostic `sigma_G^WB(A_G^M0(rho),H;rho)` versus M0, which removes global-region mismatch from the comparison.

Accepted same-region MAE values are approximately `0.494579, 0.436665, 0.427784, 0.408810, 0.418106` for increasing rho. The conservative gap is accepted as the expected behavior of the boundary-case baseline and must not trigger retuning.

Authoritative freeze: `phase3/phase3_i1_m0_freeze_manifest_v1.json`.

## 6. M1 handoff

Already frozen constraints:

- same public rho-conditioned I1 as M0;
- same-rho diagonal first;
- no private I1 evidence or white-box reconstruction targets;
- current degenerate `Q=0.5` must not be silently turned into a stochastic Q dimension;
- no tuning merely to beat M0.

The old frozen-looking three-dimensional `Omega_i(alpha)=[0,alpha]^3` LCQ closure is superseded for the current benchmark. The minimal one-parameter lifting principle remains a working direction, but M1 must be finalized against the actual rho-conditioned I1 schema.

Working first direction: normalize the nondegenerate public coordinates by `A_i(rho)` and use one scalar `alpha_i(rho)` for a minimum-structure L/C closure, preserve `Q=0.5`, realize the surrogate through native AICon/YAFS, and fit alpha only against the supplied public local sigma curve over H.

Open before M1 scientific runs:

1. exact one-parameter L/C closure geometry and deterministic mapping to native provider variables;
2. whether M1 predicts a global region or is evaluated only at exogenous frozen Phase-1 regions, which determines whether `J_A` is a meaningful M1 metric;
3. M1 fitting/evaluation seed separation;
4. final M1 Monte Carlo precision from convergence evidence.

## 7. Superseded 1 September statements

Do not use the following for the current experiment:

- first-violation `P(T_violation>H)` as authoritative sigma;
- one common mean-field local `A_MF` shared by A/B/C;
- one corpus for both region construction and sigma estimation;
- `rho=1` as a finite GMM region-content point;
- M0 product as a guaranteed global lower bound/certificate;
- the 3-D stochastic LCQ uniform M1 closure as already frozen.

## 8. Guardrail

Phase 1, I1, and M0 are closed. Reopen any of them only for a concrete scientific or implementation defect, not because M0 is conservative or because a later M1 result is inconvenient.
