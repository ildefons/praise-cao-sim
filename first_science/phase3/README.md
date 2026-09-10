# PRAISE first science - Phase 3 / (I1,M0)

Phase 3 contains the topology-aware analytic M0 baseline, the frozen Phase-1 G0 boundary adapter, the historical fixed-A_i diagnostics, and the new rho-conditioned I1 candidate diagnostic.

## Input firewall

Phase 3 consumes only finished public I1 cards. It must not read provider request ledgers, acquisition seeds, fitted GMM parameters, hidden stochastic parameters, or otherwise reconstruct `A_i`.

White-box truth is consulted only after the M0 outputs are formed, for external evaluation.

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

The code correction therefore changes the I1 regions supplied to M0, not the M0 boundary or probability algebra.

## Historical fixed-A_i branch

The earlier public cards under `first_science/phase2/results/i1_cards_v1/public/` contain one fixed A_i per provider. `diagnose_real_wb_vs_i1_m0.py`, `m0_evaluation_diagnostics.py`, and `consolidate_preliminary_i1_m0_results.py` preserve the resulting preliminary evidence for provenance.

In that branch A_G^M0 is independent of rho, so J_A is constant as rho changes. This behavior motivated the rho-conditioned correction in Phase 2.

## Candidate rho-conditioned I1-M0 path

`diagnose_rho_conditioned_i1_m0.py` consumes only the new public cards under

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

Containment remains a secondary set-relation descriptor. The new two-axis diagnostic intentionally does not suppress sigma discrepancy when containment fails, because region mismatch is already exposed explicitly by J_A. Consequently the reported MAE is a joint reference discrepancy when the two regions differ; it must not be described as isolated probability-composition error.

The candidate output is written under

`first_science/phase3/results/rho_conditioned_i1_m0_two_axis_v1/`

with:

- `i1_m0_two_axis_points.csv`;
- `i1_m0_two_axis_curves.csv`;
- `i1_m0_JA_vs_sigma_MAE_scatter.png`;
- `i1_m0_two_axis_manifest_v1.json`.

This same `(J_A, MAE_sigma)` protocol is intended for I1-M1 after the corrected I1 candidate is validated.

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

# New rho-conditioned two-axis path
python first_science/phase3/test_diagnose_rho_conditioned_i1_m0.py
python first_science/phase3/diagnose_rho_conditioned_i1_m0.py
```

Expected new markers include:

```text
PHASE2_RHO_CONDITIONED_REGION_TESTS_PASS
JOINT_LOG_LC_GMM_BIC_PASS
MINIMUM_AREA_JOINT_MASS_BOX_PASS
NESTED_A_I_OF_RHO_PASS
PHASE2_RHO_CONDITIONED_I1_MATERIALIZATION_PASS
SAME_CORRECTED_I1_FOR_M0_M1_PASS

PHASE3_M0_ANALYTIC_COMPOSITION_TESTS_PASS
PHASE3_M0_PHASE1_BENCHMARK_ADAPTER_TESTS_PASS
PHASE3_RHO_CONDITIONED_I1_M0_TESTS_PASS
RHO_DEPENDENT_PROVIDER_BOUNDARY_SELECTION_PASS
PHASE3_RHO_CONDITIONED_I1_M0_TWO_AXIS_PASS
A_G_M0_DEPENDS_ON_RHO_REGION_PASS
JA_AND_SIGMA_MAE_REPORTED_TOGETHER_PASS
CONTAINMENT_RETAINED_NOT_USED_AS_SUPPRESSION_PASS
```

Do not start the I1-M1 numerical fit until this candidate I1 materialization and its M0 two-axis output have been inspected. If accepted, the rho-conditioned public cards become the common read-only I1 input for both M0 and M1.
