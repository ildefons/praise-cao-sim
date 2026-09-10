# PRAISE first science - Phase 3 / (I1,M0)

**Status: FROZEN for the first controlled comparison. M1 may now proceed.**

Phase 3 contains the topology-aware analytic M0 boundary-case baseline, the frozen Phase-1 G0 boundary adapter, historical fixed-A_i provenance, and the accepted rho-conditioned I1-M0 diagnostics.

## Input firewall

Phase 3 consumes only finished public I1 cards. It must not read provider request ledgers, acquisition seeds, fitted GMM parameters, hidden stochastic parameters, or otherwise reconstruct `A_i`.

White-box truth is consulted only after M0 has formed its boundary and probability outputs, for external evaluation.

## Frozen M0 algebra

M0 uses topology-aware LCQ boundary algebra:

- Sequence: `L=sum, C=sum, Q=min`;
- ParAll: `L=max, C=sum, Q=min`.

For G0 the deterministic adapter is

`l_M0=0.013003+max_i(l_i)`,

`c_M0=0.03+sum_i(c_i)`,

`q_M0=min_i(q_i)`.

For the first same-rho diagonal, the probability operator is

`sigma_hat_G,M0(H;rho_G)=product_i sigma_i(A_i(rho_G),H;rho_G)`.

This is intentionally the simplest boundary-case probability integration rule. Under the current cumulative-compliance query `P(c_G(A,H)>=rho_G)`, it is **not a guaranteed lower bound or certificate**: `c_i>=rho_G` for every provider does not generally imply `c_G>=rho_G`. M0 is therefore interpreted as a baseline prediction whose error/conservatism is measured empirically.

The corrected I1 changes the local regions and sigma surfaces supplied to M0; it does not change M0 algebra.

## Historical fixed-A_i branch

The earlier public cards under `first_science/phase2/results/i1_cards_v1/public/` contain one fixed A_i per provider. Their diagnostic code/results are retained for provenance only. In that branch `A_G^M0` was independent of rho, which motivated the rho-conditioned Phase-2 correction.

## Frozen rho-conditioned I1-M0 path

`diagnose_rho_conditioned_i1_m0.py` consumes only

`first_science/phase2/results/i1_cards_v2_rho_conditioned/public/`.

For each same-rho diagonal point

`rho_region=rho_query=rho_i=rho_G`,

it performs

`public A_i(rho_G) -> M0 boundary algebra -> A_G^M0(rho_G)`

and

`public sigma_i(A_i(rho_G),H;rho_G) -> product -> sigma_hat_G,M0(H;rho_G)`.

## Frozen two-axis evaluation

For each frozen Phase-1 v2 white-box region and each diagonal rho value, report

`J_A = mu(A_G^WB intersection A_G^M0) / mu(A_G^WB union A_G^M0)`

and the whole-horizon arithmetic sigma MAE.

Containment is a secondary set-relation descriptor. Sigma discrepancy is not suppressed when containment fails because region mismatch is exposed separately by `J_A`. The MAE against a frozen WB reference is therefore a **joint reference discrepancy**, not isolated probability-composition error.

Outputs:

- `i1_m0_two_axis_points.csv`;
- `i1_m0_two_axis_curves.csv`;
- `i1_m0_JA_vs_sigma_MAE_scatter.png`;
- `i1_m0_two_axis_manifest_v1.json`.

## Frozen sigma-curve diagnostics

`diagnose_rho_conditioned_i1_m0_sigma_curves.py` adds the horizon-dependent view.

### Frozen-reference curves

For each latency/cost/mixed Phase-1 reference and every supported diagonal rho:

`sigma_G^WB(A_G^WB,H;rho) vs sigma_hat_G,M0(H;rho)`.

These remain joint discrepancies because the global regions can differ.

### Same-region probability diagnostic

For every supported rho, first form `A_G^M0(rho)` from public I1 only, then query the frozen white-box bank at that exact region:

`sigma_G^WB(A_G^M0(rho),H;rho) vs sigma_hat_G,M0(H;rho)`.

Holding the region fixed removes the region-mismatch component. The remaining discrepancy diagnoses M0 probability integration up to finite-sample estimation noise.

The accepted same-region whole-horizon MAEs are approximately:

| rho | MAE |
| ---: | ---: |
| 0.95 | 0.494579 |
| 0.975 | 0.436665 |
| 0.9833333333333333 | 0.427784 |
| 0.99 | 0.408810 |
| 0.995 | 0.418106 |

The observed M0 bias is negative throughout these summaries. This conservative behavior is accepted as part of the deliberately minimal boundary-case baseline and must not trigger retuning of I1 or M0.

Outputs:

- `i1_m0_reference_sigma_curves.csv`;
- `i1_m0_reference_sigma_latency.png`;
- `i1_m0_reference_sigma_cost.png`;
- `i1_m0_reference_sigma_mixed.png`;
- `i1_m0_same_region_sigma_curves.csv`;
- `i1_m0_same_region_sigma_summary.csv`;
- `i1_m0_same_region_sigma.png`;
- `i1_m0_sigma_curve_manifest_v1.json`.

## Frozen provenance

The formal freeze record is

`phase3_i1_m0_freeze_manifest_v1.json`.

It records the exact public-I1 and white-box input hashes, the final diagnostic source commit, accepted same-region metrics, result-artifact hashes, and the rule that M0 must not be changed merely to reduce its gap to white box.

The final diagnostics were generated from source commit

`7039db9e631439cc5aab845a05610458170b83c8`

before the subsequent freeze/documentation commits.

## Handoff to M1

The Phase-2 rho-conditioned I1 cards and Phase-3 M0 baseline are now frozen. M1 must use exactly the same public I1 handoff and the same-rho diagonal for its first comparison. M1 design may now proceed, but no M1 decision may retroactively alter Phase 1, I1, or M0 without a concrete defect.
