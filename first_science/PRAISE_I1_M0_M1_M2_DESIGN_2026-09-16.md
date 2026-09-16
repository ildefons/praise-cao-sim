# PRAISE/CAO: I1-M0-M1 frozen pilot and M2 handoff

**Status:** current execution and development source of truth. Phase 1 v2, rho-conditioned I1, M0, and the M1-v2 pilot are frozen. M2 is the next method-design stage.  
**Date:** 16 September 2026.

This note supersedes `PRAISE_I1_M0_M1_DESIGN_2026-09-10.md` where the two conflict. Historical contracts/results keep their original status strings for provenance; the freeze decision recorded here means that M1-v2 is no longer to be altered or retuned to improve the observed G0 result.

## 1. Frozen information and benchmark state

- Phase 1 v2 is the technology-neutral white-box benchmark.
- Phase 2 I1 is the rho-conditioned, independent-evidence provider card construction.
- Phase 3 M0 is the analytic/topology-aware baseline.
- Phase 3 M1-v2 is now a frozen simulator-based integration baseline.
- M0 and M1 receive exactly the same finalized public I1 cards.
- Neither M0 nor M1 may access private I1 acquisition traces, fitted GMM parameters/samples, hidden Phase-1 provider parameters, or graph-level WB outcomes during parameter selection.
- The PPG firewall remains strict.

The scientific object remains the pair `tau=(I,M)`: information representation and integration method must be separated experimentally.

## 2. Authoritative sigma semantics

For admissibility region `A`, horizon `H`, and threshold `rho`, let `c_G(A,H)` be the fraction of requests decided by `H` that satisfy `A`. Requests unresolved by `H` are excluded from the denominator; before any request is decided, the frozen compliance fraction is `1.0`.

`Sigma_G(A,H;rho) = P(c_G(A,H) >= rho)`.

This is not a first-passage/no-violation functional. A trajectory can fall below `rho` and later recover, so sigma may be non-monotone in `H`.

## 3. Frozen Phase-1 pilot benchmark

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

- region evidence seeds `6000..6099` construct `A_i(rho_region)`;
- sigma evidence seeds `6100..6199` estimate the public sigma surface only after regions are fixed.

Current pilot region construction uses a full-covariance GMM in `(log L, log C)`, BIC-selected `K=1..4`, deterministic `N=100000` model sampling, and nested minimum-area origin-anchored rectangles. `Q=0.5` is preserved exactly because quality is degenerate in this pilot.

`R_region = R_query = {0.95,0.975,0.9833333333333333,0.99,0.995}`.

The complete region-rho x query-rho x H surface is public. The first comparison uses only the same-rho diagonal:

`rho_region = rho_query = rho_i = rho_G`.

Authoritative freeze: `phase2/phase2_i1_rho_conditioned_freeze_manifest_v1.json`.

## 5. Frozen M0 baseline

Boundary algebra:

- Sequence: `L=sum, C=sum, Q=min`.
- ParAll: `L=max, C=sum, Q=min`.
- Corrected native G0 adapter: `l_G=0.014003+max_i(l_i)`, `c_G=0.03+sum_i(c_i)`, `q_G=min_i(q_i)`.

The extra `0.001 s` in the latency adapter is the native zero-byte PRAISE completion-control return hop from each provider to the colocated ParAll controller. This was a simulator-semantics defect correction, not WB tuning.

Probability rule:

`sigma_hat_G,M0(H;rho_G)=product_i sigma_i(A_i(rho_G),H;rho_G)`.

This is a deliberately minimal baseline prediction, not a certificate or guaranteed lower bound under cumulative-compliance semantics.

In the final same-region comparison under the corrected induced `A_G(rho)`, M0 MAE values are:

| rho | M0 MAE |
| ---: | ---: |
| 0.95 | 0.500497 |
| 0.975 | 0.438298 |
| 0.9833333333333333 | 0.428397 |
| 0.99 | 0.410442 |
| 0.995 | 0.421576 |

M0 is systematically pessimistic in this pilot.

## 6. Frozen M1-v2 definition

M1-v2 uses the same public I1 but replaces direct probability multiplication by a simulator-compatible inverse lift followed by native graph composition:

`(I1_i, W_i) -> theta_i^M1 = (mu_i, kappa_i, CV_i)`

followed by native AICon/YAFS composition of the lifted providers in G0.

### 6.1 Pilot closure

- provider queue: one native FCFS provider module;
- service distribution: Gamma with fitted mean service time `mu` and coefficient of variation `CV`;
- native cost: `kappa * service_time`;
- canonical IPT: `1e6` as a numerical gauge only;
- execution fraction: `x=0.5` for this degenerate-Q pilot;
- `LinearQoS(0,1)`, hence native `Q=x=0.5`;
- public workload `W_i` is fixed and not optimized;
- no trace-specific arrival phase is fitted or exposed.

### 6.2 Local inverse objective

For each provider, M1-v2 minimizes uniform MSE against the complete public local I1 surface over every public `rho_region`, all `H>0`, and all public `rho_query` values:

`L_i(theta_i) = mean[(sigma_hat_i^M1 - sigma_i^I1)^2]`.

Optimization uses Optuna TPE with common random numbers, 100 search trials, 25 calibration trajectories per candidate, top-5 confirmation on 100 disjoint trajectories, then a 100-trajectory independent replay that is diagnostic only.

No graph-level WB outcome participates in local parameter selection.

### 6.3 Selected frozen provider surrogates

| Provider | mean service time mu | cost rate kappa | service CV | note |
| --- | ---: | ---: | ---: | --- |
| A | 0.03515902181174001 | 0.5010610641116193 | 1.4559952139534043 | original v2 search, interior |
| B | 0.04788017702777221 | 2.1024570659802144 | 1.2555234974919558 | original v2 search, interior |
| C | 0.0026819926073551946 | 87.30698671847529 | 0.9941982270091521 | one declared public-I1-only bound expansion, then interior |

Provider C originally selected a point on the `mu` lower and `kappa` upper search boundaries. One predeclared public-I1-only expansion was therefore executed before graph WB was consulted. The expanded solution is interior. No further expansion or retuning is allowed for the frozen M1-v2 baseline.

## 7. Frozen M1 graph result on G0

The graph simulator uses the native G0 topology and the corrected native completion-control semantics. The M1 prediction was fully materialized before the Phase-1 graph WB ledger was opened for external evaluation. The firewall check passed.

Same-region whole-horizon errors:

| rho | M0 MAE | M1 MAE | M0 MAE - M1 MAE |
| ---: | ---: | ---: | ---: |
| 0.95 | 0.500497 | 0.218163 | 0.282334 |
| 0.975 | 0.438298 | 0.218776 | 0.219523 |
| 0.9833333333333333 | 0.428397 | 0.179592 | 0.248805 |
| 0.99 | 0.410442 | 0.171224 | 0.239218 |
| 0.995 | 0.421576 | 0.128367 | 0.293208 |

M1 is therefore substantially closer to WB than M0 for every tested rho, but the mechanism of the residual error is important: M0 is strongly pessimistic, while M1 is systematically optimistic and its graph sigma is nearly saturated at one after short horizons.

The observed G0 request-level distributions explain this saturation:

| quantity | WB | M1 |
| --- | ---: | ---: |
| mean graph latency | 0.256830 s | 0.084790 s |
| median graph latency | 0.236997 s | 0.063422 s |
| 99% graph latency | 0.565265 s | 0.338319 s |
| 99.9% graph latency | 0.759451 s | 0.517422 s |
| mean graph cost | 1.379616 | 0.382132 |
| median graph cost | 1.364733 | 0.315088 |
| 99% graph cost | 1.997338 | 1.288874 |
| corr(L,C) | 0.4315 | 0.4009 |
| graph Q | 0.5 | 0.5 |

Thus the current M1 lift reconstructs the public local sigma surfaces only approximately and maps them to one specific latent provider process per provider. When recomposed, that selected latent realization is much faster/cheaper and has too few tail violations compared with WB. The native graph composition itself is functioning as specified.

### Frozen interpretation

The M1 result is not to be repaired by further M1 tuning. It is retained as evidence that a single point inverse lift can improve over M0 while still failing to recover the latent process information required for accurate graph-level tails.

A concise interpretation is:

`M0 loses composition structure; M1 restores native composition structure but collapses inverse ambiguity to one latent process.`

## 8. M2 handoff

M2 is the next design stage. Its purpose is to learn from the frozen M1 failure without changing I1.

### 8.1 Core scientific question

Does the public I1 surface identify a unique-enough simulator-compatible latent provider process for graph composition?

The immediate test is:

`Do substantially different theta_i with similarly good public-I1 reconstruction loss produce materially different graph-level sigma_G after composition?`

This test uses the already-generated M1 search landscape and public-I1 reconstruction scores. It must not choose candidates by graph-WB performance.

### 8.2 Two possible outcomes

1. **Inverse non-identifiability dominates.** If multiple locally compatible `theta_i` sets yield very different graph predictions, M2 should preserve that ambiguity rather than select a single point. A natural M2 family is an uncertainty-preserving set/ensemble/posterior over compatible provider surrogates, propagated through native composition.

2. **Model-class insufficiency dominates.** If all near-equivalent Gamma/FCFS lifts produce similarly saturated graph predictions, M2 needs a richer latent process family, for example mixtures, latent states, burstiness, or another minimal native process capable of preserving the public-I1 tail structure. Any added latent structure must still be inferred only from public I1 and W_i.

Do not conflate these two cases. First test point-identifiability within the current M1 family; only then decide whether the latent process family itself must be expanded.

### 8.3 M2 information contract

M2 initially receives exactly the same frozen I1 as M0 and M1. It may use:

- public rho-conditioned I1 cards;
- public workload contracts W_i;
- public graph topology/mechanics at composition time;
- public-I1-only reconstruction diagnostics generated during M1/M2 fitting.

It may not use private Phase-2 provider traces, acquisition seeds, GMM parameters/samples, hidden Phase-1 provider parameters, or WB graph traces as fitting targets.

### 8.4 Development versus final validation

G0 WB has now been inspected and may motivate M2 architecture, so G0 can no longer serve as the sole untouched validation case for a new M2 claim. M2 should be defined and frozen using the public-I1 contract, then evaluated on at least one fresh composition/topology or other untouched WB condition. G0 can remain a development/diagnostic benchmark and a historical M0/M1 comparison.

## 9. Beyond-pilot quality and workload

The current pilot has degenerate `Q=0.5`. This must not become a general PRAISE assumption. A later benchmark should introduce non-degenerate quality through a native resource/quality trade-off, for example varying execution fraction, so that quality, latency, and cost are coupled rather than adding independent quality noise.

Likewise, a provider surrogate lifted for one public workload `W_i` is not assumed valid under an unsupported `W_i'`. Later evaluations should exercise multiple workloads and graph topologies while maintaining the provider-information firewall.

## 10. Freeze guardrail

Phase 1, I1, M0, and M1-v2 are now closed for the pilot. Reopen them only for a concrete implementation or scientific defect, not because a later result is inconvenient.

In particular:

- do not retune M1 against G0 WB;
- do not enlarge M1 until its prediction matches WB;
- do not alter I1 to make M1 easier;
- do not use hidden trace timing or provider parameters to improve the lift;
- develop M2 as a separate method with explicit new assumptions and a fresh validation target.
