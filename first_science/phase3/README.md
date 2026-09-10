# PRAISE first science - Phase 3 / (I1,M0)

Phase 3 contains the frozen topology-aware analytic M0 baseline, the frozen Phase-1 G0 boundary adapter, and the preliminary WB-vs-M0 evaluation harness.

## M0 input firewall

Phase 3 consumes only the finished public I1 cards produced by Phase 2. It must not read provider request ledgers, acquisition seeds, hidden stochastic parameters, or otherwise reconstruct `A_i`.

The executable handoff is therefore:

`Phase 2: T_i -> hash-frozen public I1_i`

followed by

`Phase 3: (public I1, G, A_G, H, rho_G, M0) -> sigma_hat_G`

White-box truth is consulted only after the M0 prediction is formed, for external evaluation.

## Frozen M0 baseline

M0 uses topology-aware LCQ algebra:

- Sequence: `L=sum, C=sum, Q=min`;
- ParAll: `L=max, C=sum, Q=min`.

At evaluation time it reads every provider card at exactly

`rho_i=rho_G`.

For the independent anchor:

`sigma_hat_G,M0(H;rho_G)=product_i sigma_i(A_i,H;rho_G)`.

This is an analytic baseline predictor, not a certification lower bound. M0 intentionally does not redistribute the global violation budget.

## Full Phase-1 G0 applicability

`m0_phase1_benchmark_adapter.py` instantiates the frozen graph

`Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost`.

The exact frozen deterministic terms give

`L_fixed=0.013003`, `C_fixed=0.03`,

hence

`l_M0=0.013003+max_i(l_i)`,

`c_M0=0.03+sum_i(c_i)`,

`q_M0=min_i(q_i)`.

M0 produces a prediction only if this induced boundary is contained in the exogenous `A_G`. Otherwise the case is `NOT_APPLICABLE`. A raw provider-probability product may be retained for diagnostics but is not an M0 prediction and is not scored.

## Real WB vs public-I1 M0 diagnostic

`diagnose_real_wb_vs_i1_m0.py` now loads and hash-verifies the materialized public cards from

`first_science/phase2/results/i1_cards_v1/public/`.

It has no private-provider-ledger input and no `T_i -> A_i` code path. It reads the public `A_i`, H/rho support and sigma surfaces, computes M0, applies full boundary containment, then compares applicable predictions with the independent frozen Phase-1 white-box bank.

## Preliminary four-rho consolidation

`consolidate_preliminary_i1_m0_results.py` runs the predeclared diagnostic sweep

`rho_G in {0.95,0.975,0.9833333333333333,0.99}`

from the same hash-frozen I1 cards. It writes:

- `preliminary_i1_m0_summary.csv`;
- `preliminary_i1_m0_sigma_snapshot.csv`;
- `preliminary_i1_m0_manifest_v1.json`.

The manifest records the I1-card manifest hash, white-box manifest hash, git commit, applicability counts and case identities. Its status is explicitly `PRELIMINARY_I1_M0_DIAGNOSTIC_V1`; it is not the final paper evaluation.

## Validation and execution

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim

python first_science/phase2/test_phase2_direct_i1_contract.py
python first_science/phase2/test_materialize_frozen_i1_cards.py
python first_science/phase2/materialize_frozen_i1_cards.py

python first_science/phase3/test_m0_analytic_composition.py
python first_science/phase3/test_m0_phase1_benchmark_adapter.py
python first_science/phase3/test_diagnose_real_wb_vs_i1_m0.py
python first_science/phase3/test_preliminary_i1_m0_consolidation_contract.py

python first_science/phase3/consolidate_preliminary_i1_m0_results.py
```

Important expected markers include:

```text
PHASE2_I1_CARD_MATERIALIZATION_PASS
PUBLIC_I1_CARD_HASH_FREEZE_PASS
SAME_I1_FOR_M0_M1_PASS

PHASE3_PUBLIC_I1_ONLY_FIREWALL_PASS
PHASE3_PRIVATE_PROVIDER_TRACE_ACCESS_BLOCKED_PASS
M0_NOT_APPLICABLE_SUPPRESSION_PASS

PHASE3_PRELIMINARY_I1_M0_CONSOLIDATION_PASS
PUBLIC_HASH_FROZEN_I1_INPUT_PASS
FOUR_RHO_PRELIMINARY_SWEEP_PASS
PRELIMINARY_RESULT_MANIFEST_WRITTEN_PASS
```
