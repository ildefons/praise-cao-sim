# PRAISE first science - Phase 3 / (I1,M0)

Phase 3 contains the topology-aware analytic M0 baseline, the frozen Phase-1 G0 boundary adapter, the historical fixed-A_i diagnostics, and the rho-conditioned I1 candidate diagnostics.

## Input firewall

Phase 3 consumes only finished public I1 cards. It must not read provider request ledgers, acquisition seeds, fitted GMM parameters, hidden stochastic parameters, or otherwise reconstruct `A_i`.

White-box truth is consulted only after the M0 boundary and probability outputs are formed, for external evaluation.

## M0 algebra - unchanged

M0 uses topology-aware LCQ algebra:

- Sequence: `L=sum, C=sum, Q=min`;
- ParAll: `L=max, C=sum, Q=min`.

For the independent all-required anchor, the probability operator remains

`sigma_hat_G,M0=product_i sigma_i`.

The deterministic Phase-1 adapter remains

`l_M0=0.013003+max_i(l_i)`,

`c_M0=0.03+sum_i(c_i)`,

`q_M0=min_i(q_i)`.

The I1 correction therefore changes the local regions and sigma surfaces supplied to M0, not the M0 boundary or probability algebra.

## Historical fixed-A_i branch

The earlier public cards under `first_science/phase2/results/i1_cards_v1/public/` contain one fixed A_i per provider. `diagnose_real_wb_vs_i1_m0.py`, `m0_evaluation_diagnostics.py`, and `consolidate_preliminary_i1_m0_results.py` preserve the resulting preliminary evidence for provenance.

In that branch A_G^M0 is independent of rho, so J_A is constant as rho changes. This behavior motivated the rho-conditioned correction in Phase 2.

## Candidate rho-conditioned I1-M0 path

`diagnose_rho_conditioned_i1_m0.py` consumes only the corrected public cards under

`first_science/phase2/results/i1_cards_v2_rho_conditioned/public/`.

For each same-rho diagonal point

`rho_region=rho_query=rho_i=rho_G`,

it performs:

`public A_i(rho_G) -> M0 boundary algebra -> A_G^M0(rho_G)`,

and

`public sigma_i(A_i(rho_G),H;rho_G) -> product -> sigma_hat_G,M0(H;rho_G)`.

Because A_i now depends on rho, the induced global region and therefore J_A are allowed to vary with rho.

## Two-axis evaluation

For each frozen Phase-1 v2 white-box region and each diagonal rho value, the candidate diagnostic reports

`x = J_A = mu(A_G^WB intersection A_G^M0) / mu(A_G^WB union A_G^M0)`

and

`y = whole-horizon MAE_sigma between sigma_hat_G,M0 and sigma_G^WB`.

Containment remains a secondary set-relation descriptor. The two-axis diagnostic intentionally does not suppress sigma discrepancy when containment fails, because region mismatch is already exposed explicitly by J_A. Consequently the reported MAE is a joint reference discrepancy when the two regions differ; it must not be described as isolated probability-composition error.

The two-axis output is written under

`first_science/phase3/results/rho_conditioned_i1_m0_two_axis_v1/`

with:

- `i1_m0_two_axis_points.csv`;
- `i1_m0_two_axis_curves.csv`;
- `i1_m0_JA_vs_sigma_MAE_scatter.png`;
- `i1_m0_two_axis_manifest_v1.json`.

## Sigma-curve diagnostics

`diagnose_rho_conditioned_i1_m0_sigma_curves.py` adds the horizon-dependent view that is hidden by the scalar MAE summary. It writes its outputs into the same rho-conditioned Phase-3 result directory.

Two complementary comparisons are produced.

### Frozen-reference curves

For each frozen latency/cost/mixed Phase-1 reference and every supported diagonal rho,

`sigma_G^WB(A_G^WB,H;rho) vs sigma_hat_G,M0(H;rho)`.

These plots visualize the same joint discrepancy summarized by the two-axis MAE. Because `A_G^WB` can differ from `A_G^M0(rho)`, the gap must not be interpreted as isolated probability-composition error.

Outputs:

- `i1_m0_reference_sigma_curves.csv`;
- `i1_m0_reference_sigma_latency.png`;
- `i1_m0_reference_sigma_cost.png`;
- `i1_m0_reference_sigma_mixed.png`.

### Same-region probability diagnostic

For every supported diagonal rho, Phase 3 first forms `A_G^M0(rho)` from public I1 only. Only then is the frozen Phase-1 white-box ledger queried at that exact global region:

`sigma_G^WB(A_G^M0(rho),H;rho) vs sigma_hat_G,M0(H;rho)`.

Holding the global region fixed removes the region-mismatch component from the comparison. The remaining discrepancy is therefore a direct diagnostic of the M0 probability-integration approximation, subject to finite-sample estimation noise in the independent I1 and white-box trajectory banks.

Outputs:

- `i1_m0_same_region_sigma_curves.csv`;
- `i1_m0_same_region_sigma_summary.csv`;
- `i1_m0_same_region_sigma.png`;
- `i1_m0_sigma_curve_manifest_v1.json`.

This diagnostic does not alter I1 or M0. It is explanatory evidence used to determine whether the main M0 error is geometric, probabilistic, or both before M1 is designed.

## Validation and execution

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim

git pull origin first-science-phase1

# Phase 2 corrected-I1 guards and materialization
python -c "import sklearn; print(sklearn.__version__)"
python first_science/phase2/test_i1_rho_conditioned_region.py
python first_science/phase2/test_materialize_rho_conditioned_i1_cards.py
python first_science/phase2/materialize_rho_conditioned_i1_cards.py

# M0 regression guards: algebra must remain unchanged
python first_science/phase3/test_m0_analytic_composition.py
python first_science/phase3/test_m0_phase1_benchmark_adapter.py

# Rho-conditioned two-axis path
python first_science/phase3/test_diagnose_rho_conditioned_i1_m0.py
python first_science/phase3/diagnose_rho_conditioned_i1_m0.py

# Horizon-dependent reference and same-region sigma diagnostics
python first_science/phase3/test_diagnose_rho_conditioned_i1_m0_sigma_curves.py
python first_science/phase3/diagnose_rho_conditioned_i1_m0_sigma_curves.py
```

Expected markers include:

```text
PHASE2_RHO_CONDITIONED_REGION_TESTS_PASS
JOINT_LOG_LC_GMM_BIC_PASS
MINIMUM_AREA_JOINT_MASS_BOX_PASS
NESTED_A_I_OF_RHO_PASS
PHASE2_RHO_CONDITIONED_I1_MATERIALIZATION_PASS
TRAJECTORY_DISJOINT_REGION_SIGMA_EVIDENCE_PASS
SAME_CORRECTED_I1_FOR_M0_M1_PASS

PHASE3_M0_ANALYTIC_COMPOSITION_TESTS_PASS
PHASE3_M0_PHASE1_BENCHMARK_ADAPTER_TESTS_PASS
PHASE3_RHO_CONDITIONED_I1_M0_TESTS_PASS
RHO_DEPENDENT_PROVIDER_BOUNDARY_SELECTION_PASS
PHASE3_RHO_CONDITIONED_I1_M0_TWO_AXIS_PASS
A_G_M0_DEPENDS_ON_RHO_REGION_PASS
JA_AND_SIGMA_MAE_REPORTED_TOGETHER_PASS
CONTAINMENT_RETAINED_NOT_USED_AS_SUPPRESSION_PASS

PHASE3_RHO_CONDITIONED_I1_M0_SIGMA_CURVE_TESTS_PASS
FROZEN_REFERENCE_CURVE_DIAGNOSTIC_PASS
SAME_M0_REGION_WHITEBOX_DIAGNOSTIC_PASS
SAME_REGION_ERROR_METRICS_PASS
PHASE3_SIGMA_CURVE_PUBLIC_I1_FIREWALL_PASS
PHASE3_RHO_CONDITIONED_I1_M0_SIGMA_CURVES_PASS
FROZEN_REFERENCE_SIGMA_CURVES_PASS
SAME_M0_REGION_WHITEBOX_SIGMA_CURVES_PASS
SAME_REGION_PROBABILITY_INTEGRATION_DIAGNOSTIC_PASS
```

Do not start the I1-M1 numerical fit until the corrected I1 materialization, the two-axis M0 output, and the same-region sigma diagnostic have been inspected together. If accepted, the rho-conditioned public cards become the common read-only I1 input for both M0 and M1.
