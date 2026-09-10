# PRAISE first science - Phase 3 / (I1,M0)

Phase 3 contains the frozen topology-aware analytic M0 baseline and its concrete adapter for the frozen Phase-1 G0 benchmark.

## Frozen M0 baseline

`config_phase3_m0_contract_v1.json` and `m0_analytic_composition.py` define the agreed M0 anchor:

- recursive topology-aware LCQ composition;
- Sequence: `L=sum, C=sum, Q=min`;
- ParAll: `L=max, C=sum, Q=min`;
- same-rho policy: `rho_i=rho_G` for every required provider;
- independent product `sigma_hat_G,M0=product_i sigma_i(A_i,H;rho_G)`;
- no violation-budget redistribution;
- analytic predictor/baseline, not a global-rho certificate.

M0 consumes the finished Phase-2 I1 cards unchanged and may not create or alter `A_i`.

## I1 input

Each provider card has the frozen form

`I1_i=(A_i,W_i,R,{sigma_i(A_i,H;rho): H in H, rho in R})`.

Phase 2 calibrates each fixed `A_i` from provider-local evidence using the frozen coordinate-wise first-crossing rule at `rho_anchor=0.95`, `H*=120 s`, `sigma_target=0.95`. The same `A_i` is used for every later rho slice. M0 simply reads the already-exposed slice with `rho_i=rho_G`.

## Full Phase-1 G0 applicability adapter

`m0_phase1_benchmark_adapter.py` instantiates the generic M0 algebra for the frozen benchmark

`Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost`.

The adapter reads deterministic numerical terms from `../phase1/config_phase1_discovery_v1.json` and uses the exact AICon/YAFS network law employed by Phase 1:

`latency_hop = message_bytes/(BW_mbps*1e6) + PR`.

For the frozen benchmark, each 1000-byte hop at 1000 Mbps and `PR=0.001` contributes `0.001001 s`. Fpre and Fpost each execute 5M instructions at `IPT=1e9`, hence each contributes `0.005 s` latency and `0.015` cost at `COST=3`.

Therefore the deterministic terms outside the provider boundaries are

`L_fixed=0.013003`, `C_fixed=0.03`,

and the full induced M0 boundary is

`l_M0 = 0.013003 + max_i(l_i)`,

`c_M0 = 0.03 + sum_i(c_i)`,

`q_M0 = min_i(q_i)`.

M0 is applicable to an exogenous `A_G` only when

`l_M0<=l_G`, `c_M0<=c_G`, `q_M0>=q_G`.

If containment fails, M0 reports `NOT_APPLICABLE`. The raw provider-probability product may still be retained as a diagnostic quantity, but it is not an M0 prediction and is not scored against white-box truth.

With the current trace-derived provider boundaries, the full induced boundary is expected to be approximately

`A_G^M0=(L<=0.587611774, C<=2.400071385, Q>=0.5)`.

Against the frozen Phase-1 v2 query battery this makes the latency case applicable, while the cost and mixed cases fail the cost-containment precondition.

## Real-trace WB vs I1-M0 diagnostic

`diagnose_real_wb_vs_i1_m0.py` uses only real frozen scientific data:

- Phase-1 v2 fresh-confirmation top-level ledgers, seeds `7000..7099`, for `sigma_G^WB`;
- Phase-2 provider-local ledgers, seeds `6000..6099`, for I1;
- the frozen Phase-2 A_i calibration;
- the frozen same-rho M0 probability rule;
- the full G0 deterministic boundary adapter above.

For every frozen white-box query the diagnostic now reports `PREDICTED` or `NOT_APPLICABLE`. For applicable cases it reports and plots the M0 estimate. For non-applicable cases it suppresses the estimate and its error metrics while retaining `sigma_i1_m0_raw_probability_component` explicitly as diagnostic-only information.

Because the provider cards expose multiple rho slices, the same fixed I1 can be evaluated without simulator reruns at

`rho in {0.95,0.975,0.9833333333333333,0.99,1.0}`.

## Current implementation

- `config_phase3_m0_contract_v1.json`: frozen M0 contract and frozen G0 numeric adapter contract.
- `m0_analytic_composition.py`: generic topology-aware M0 kernel.
- `m0_phase1_benchmark_adapter.py`: frozen Phase-1 G0 deterministic adapter.
- `test_m0_analytic_composition.py`: generic M0 regression tests.
- `test_m0_phase1_benchmark_adapter.py`: hand-checkable G0 adapter tests.
- `diagnose_real_wb_vs_i1_m0.py`: real-trace white-box versus applicable I1-M0 diagnostic.
- `test_diagnose_real_wb_vs_i1_m0.py`: diagnostic contract tests, including NOT_APPLICABLE suppression.

## Validation

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim
python first_science/phase3/test_m0_analytic_composition.py
python first_science/phase3/test_m0_phase1_benchmark_adapter.py
python first_science/phase3/test_diagnose_real_wb_vs_i1_m0.py
```

Expected adapter markers include:

```text
PHASE3_M0_PHASE1_BENCHMARK_ADAPTER_TESTS_PASS
M0_FIXED_NETWORK_LAW_PASS
M0_FIXED_PRE_POST_SERVICE_PASS
M0_FULL_G0_BOUNDARY_PASS
M0_V2_APPLICABILITY_LATENCY_ONLY_PASS
```

Expected diagnostic markers include:

```text
PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_TESTS_PASS
A_I_COORDINATE_FIRST_CROSSING_H120_RULE_PASS
CUMULATIVE_COORDINATE_ACCOUNTING_PASS
CONSTANT_QUALITY_NO_ARTIFICIAL_THRESHOLD_PASS
NO_EXTERNAL_A_I_INPUT_PASS
FULL_M0_APPLICABILITY_INPUT_PASS
M0_REAL_CURVE_COMPOSITION_KERNEL_PASS
M0_NOT_APPLICABLE_SUPPRESSION_PASS
RAW_PRODUCT_RETAINED_AS_DIAGNOSTIC_ONLY_PASS
WB_M0_ERROR_METRICS_PASS
```

After validation, run the real diagnostic on the informative rho slices:

```bash
cd ~/praise/praise-cao-sim
for rho in 0.95 0.975 0.9833333333333333 0.99; do
  python first_science/phase3/diagnose_real_wb_vs_i1_m0.py --rho "$rho"
done
```
