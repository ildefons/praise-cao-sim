# PRAISE first science - Phase 3 / (I1,M0)

Phase 3 contains the frozen topology-aware analytic M0 baseline, the frozen Phase-1 G0 boundary adapter, and the preliminary WB-vs-M0 evaluation harness.

## M0 input firewall

Phase 3 consumes only the finished public I1 cards produced by Phase 2. It must not read provider request ledgers, acquisition seeds, hidden stochastic parameters, or otherwise reconstruct `A_i`.

The executable handoff is therefore:

`Phase 2: T_i -> hash-frozen public I1_i`

followed by

`Phase 3: (public I1, G, A_G, H, rho_G, M0) -> (A_G^M0, sigma_hat_G)`

White-box truth is consulted only after the M0 outputs are formed, for external evaluation.

## Frozen M0 baseline

M0 uses topology-aware LCQ algebra:

- Sequence: `L=sum, C=sum, Q=min`;
- ParAll: `L=max, C=sum, Q=min`.

This produces the bottom-up global admissibility region `A_G^M0` from the fixed local `A_i` and graph `G`.

At evaluation time the official M0 probability rule reads every provider card at exactly

`rho_i=rho_G`.

For the independent all-required anchor:

`sigma_hat_G,M0(H;rho_G)=product_i sigma_i(A_i,H;rho_G)`.

This is an analytic baseline predictor, not a certification lower bound. M0 intentionally does not redistribute the global violation budget.

## Full Phase-1 G0 boundary composition

`m0_phase1_benchmark_adapter.py` instantiates the frozen graph

`Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost`.

The exact frozen deterministic terms give

`L_fixed=0.013003`, `C_fixed=0.03`,

hence

`l_M0=0.013003+max_i(l_i)`,

`c_M0=0.03+sum_i(c_i)`,

`q_M0=min_i(q_i)`.

Containment of this induced boundary inside an exogenous `A_G` remains the coarse M0 applicability relation. If containment fails, the official same-rho probability product is not scored as a prediction for that query. The bottom-up `A_G^M0` itself remains a legitimate method output and is now evaluated geometrically against the frozen white-box/reference `A_G`.

## Real WB vs public-I1 M0 diagnostic

`diagnose_real_wb_vs_i1_m0.py` loads and hash-verifies the materialized public cards from

`first_science/phase2/results/i1_cards_v1/public/`.

It has no private-provider-ledger input and no `T_i -> A_i` code path. It reads the public `A_i`, H/rho support and sigma surfaces, computes M0, applies the existing containment guard, then compares applicable same-rho predictions with the independent frozen Phase-1 white-box bank.

## Evaluation extension: region agreement and rho-vector shape family

`config_phase3_m0_diagnostics_v1.json` and `m0_evaluation_diagnostics.py` add two evaluation-only axes. They do not modify the frozen I1 or M0 methods.

### 1. Global-region agreement

The two regions are kept distinct:

`A_G^WB` = frozen white-box/reference admissibility region,

`A_G^M0` = bottom-up region obtained by analytic composition of the public provider `A_i`.

They are not forced to be equal. Their primary overlap score is

`J_A = mu(A_G^WB intersection A_G^M0) / mu(A_G^WB union A_G^M0)`.

The diagnostic also reports intersection coverage of each region, the set relation, and signed L/C/Q threshold differences.

All current frozen regions use the same `Q>=0.5` threshold. Therefore the common Q factor cancels exactly from intersection-over-union and the present `J_A` is computed on the L-C projection without inventing an arbitrary Q ceiling. If future compared regions have different quality thresholds, an explicit finite quality evaluation domain must be declared first.

### 2. Rho-vector probability sensitivity

The official M0 rule remains the same-rho diagonal

`rho_A=rho_B=rho_C=rho_G`.

For diagnosis only, the complete already-public support is also evaluated over

`(rho_A,rho_B,rho_C) in R^3`,

with

`R={0.95,0.975,0.9833333333333333,0.99,1.0}`.

This gives 125 rho vectors. For each vector, the diagnostic stores the complete

`H -> product_i sigma_i(A_i,H;rho_i)`

curve and a shape summary containing normalized area and selected horizon values. The five same-rho diagonal vectors correspond to the frozen M0 probability rule. The 120 off-diagonal vectors are sensitivity diagnostics only and must not be interpreted as predictions for a common global `rho_G`.

No new simulation and no I1 rematerialization are required.

## Preliminary consolidation v2

`consolidate_preliminary_i1_m0_results.py` retains the official predeclared global sweep

`rho_G in {0.95,0.975,0.9833333333333333,0.99}`

and now additionally writes:

- `preliminary_i1_m0_region_overlap.csv`;
- `preliminary_i1_m0_rho_vector_family.csv`;
- `preliminary_i1_m0_rho_vector_shape_summary.csv`;
- `preliminary_i1_m0_manifest_v2.json`.

The previous same-rho summary and snapshot CSVs are retained. The v2 manifest records the two evaluation axes, the public I1-card manifest hash, white-box manifest hash, git commit, region-measure semantics, full public rho support, and the diagnostic-only status of off-diagonal rho vectors. This remains preliminary evidence, not the final paper evaluation.

## Validation and execution

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim

git pull origin first-science-phase1

python first_science/phase3/test_m0_analytic_composition.py
python first_science/phase3/test_m0_phase1_benchmark_adapter.py
python first_science/phase3/test_diagnose_real_wb_vs_i1_m0.py
python first_science/phase3/test_m0_evaluation_diagnostics.py
python first_science/phase3/test_preliminary_i1_m0_consolidation_contract.py

python first_science/phase3/consolidate_preliminary_i1_m0_results.py
```

Important expected markers include:

```text
PHASE3_PUBLIC_I1_ONLY_FIREWALL_PASS
PHASE3_PRIVATE_PROVIDER_TRACE_ACCESS_BLOCKED_PASS
M0_NOT_APPLICABLE_SUPPRESSION_PASS

PHASE3_M0_EVALUATION_DIAGNOSTICS_TESTS_PASS
M0_REGION_JACCARD_PASS
M0_RHO_VECTOR_CARTESIAN_FAMILY_PASS
M0_RHO_VECTOR_OFF_DIAGONAL_DIAGNOSTIC_ONLY_PASS

PHASE3_PRELIMINARY_I1_M0_CONSOLIDATION_V2_PASS
A_G_WB_VS_A_G_M0_REGION_OVERLAP_PASS
M0_RHO_VECTOR_R3_SENSITIVITY_PASS
OFF_DIAGONAL_RHO_VECTOR_DIAGNOSTIC_ONLY_PASS
PRELIMINARY_RESULT_MANIFEST_V2_WRITTEN_PASS
```
