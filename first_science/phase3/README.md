# PRAISE first science - Phase 3 / (I1,M0)

Phase 3 contains the frozen topology-aware analytic M0 baseline. The public I1 schema is already frozen in Phase 2. Final numerical M0 evaluation waits for the three concrete provider-local `A_i` instances and the corresponding final hash-frozen I1 cards.

## Frozen M0 baseline

`config_phase3_m0_contract_v1.json` and `m0_analytic_composition.py` define the agreed M0 anchor:

- structure-aware analytic composition;
- recursive LCQ algebra for supported composition operators;
- explicit deterministic fixed-stage/network terms;
- exogenous global-boundary containment check;
- **same-rho policy**: `rho_i = rho_G` for every required provider;
- independent-product composition of the corresponding local sigma values;
- no local violation-budget redistribution;
- no interpretation as a guaranteed lower bound/certificate for the global rho query.

For rectangular LCQ contract inputs:

| Quantity | Sequence | ParAll / all-required parallel |
| --- | --- | --- |
| latency L | sum | maximum |
| cost C | sum | sum |
| quality Q | minimum | minimum |

The `A_i` are already part of the I1 card instances produced by Phase 2. M0 may not create or alter them.

## Frozen I1 input semantics

Each provider card has the agreed form

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`.

M0 receives the identical finished cards supplied to M1. For a global query with `rho_G`, M0 reads every provider card at exactly that same rho:

`rho_i = rho_G  for all i`.

Phase 2 therefore does not select a method-specific local rho. It exposes the frozen rho support, and M0's rule selects the already-existing `rho_G` slice at evaluation time.

## Probability baseline

For the deliberately simple independent anchor,

`sigma_hat_G,M0(H;rho_G) = product_i sigma_i(A_i,H;rho_G)`.

This product is an **analytic baseline prediction**, not a certification probability.

The distinction is deliberate. For an all-required composition,

`c_i >= rho_G` for every provider

does not in general imply

`c_G >= rho_G`.

For example, with three providers and `rho_G=0.95`, the union of three disjoint 5% local violation sets could occupy 15% of requests. M0 intentionally does not correct this by replacing 0.95 with 0.983333... or by otherwise redistributing the global violation budget. That limitation is part of the baseline being measured and creates room for richer integration methods such as M1.

## Applicability rule

M0 first composes the fixed provider boundaries forward through the public graph. The induced boundary `A_G^M0` is usable for an exogenous global region `A_G` only when

`l_M0 <= l_G`, `c_M0 <= c_G`, and `q_M0 >= q_G`.

M0 also requires the requested horizon `H` and the exact `rho_G` slice to exist in every required I1 card. If these structural inputs are unavailable, it returns `NOT_APPLICABLE`; it does not modify Phase 2, interpolate an unexposed rho, or allocate a different local rho.

## Real-trace WB vs I1-M0 diagnostic

`diagnose_real_wb_vs_i1_m0.py` provides a read-only numerical diagnostic using the actual frozen trace banks rather than illustrative curves.

It uses:

- the fresh Phase-1 v2 white-box confirmation ledger (`7000..7099`) to recompute `sigma_G^WB(A_G,H;rho_G)` for each frozen latency/cost/mixed `A_G`;
- the frozen Phase-2 provider-local acquisition ledgers (`6000..6099`) to build the provider I1 sigma surfaces;
- the frozen M0 same-rho rule to compute `product_i sigma_i(A_i,H;rho_G)`.

The diagnostic **never chooses `A_i`**. The caller must provide an explicit JSON file containing one rectangular `A_i` for ProviderA, ProviderB and ProviderC. It also rejects `rho` or `rho_i` inside that file, so the plotting utility cannot silently mix the Phase-2 `T_i -> A_i` problem with M0's same-rho rule.

Minimal input format:

```json
{
  "regions": {
    "ProviderA": {"l_max": 0.0, "c_max": 0.0, "q_min": 0.0},
    "ProviderB": {"l_max": 0.0, "c_max": 0.0, "q_min": 0.0},
    "ProviderC": {"l_max": 0.0, "c_max": 0.0, "q_min": 0.0}
  }
}
```

The zero values above document the schema only; they are not scientific defaults and must not be used as provider regions.

For example, once an explicit provider-region file exists:

```bash
cd ~/praise/praise-cao-sim
python first_science/phase3/diagnose_real_wb_vs_i1_m0.py \
  --local-regions-json /path/to/explicit_A_i.json \
  --rho 0.95
```

The script writes rho-specific output under `first_science/phase3/results/`, including:

- the real provider I1 surfaces;
- the real I1-M0 probability curve;
- aligned WB/M0 curve data;
- MAE, RMSE, bias and maximum absolute error;
- one clean WB-vs-I1-M0 PNG for each frozen latency/cost/mixed white-box case;
- a diagnostic manifest recording every input and explicitly marking the run as non-freeze evidence.

The plotted probability curve is real. However, this diagnostic intentionally does **not** claim the separate full-M0 boundary applicability condition yet. It reports the provider-only ParAll boundary for transparency, but it does not invent the deterministic Fpre/Fpost/network numerical adapter. Final M0 evaluation should assert that adapter separately once it is frozen.

Because the white-box request ledgers are retained, the same diagnostic can also be run at another rho already present in the frozen I1 support, for example `--rho 0.99`, without rerunning the simulator.

## Current implementation

- `config_phase3_m0_contract_v1.json`: frozen same-rho M0 information/composition contract.
- `m0_analytic_composition.py`: recursive Sequence/ParAll LCQ algebra, containment check, same-rho selector, independent-product predictor, and applicability guard.
- `test_m0_analytic_composition.py`: simulator-independent hand-checkable M0 regression tests.
- `diagnose_real_wb_vs_i1_m0.py`: real-trace WB versus I1-M0 probability-composition diagnostic.
- `test_diagnose_real_wb_vs_i1_m0.py`: simulator-independent guard tests for the diagnostic.

The M0 implementation contains no private provider evidence, no Phase-1 white-box sigma values, no inverse `A_G -> A_i` construction, and no equal-violation-budget allocator.

## Validation

Starting from the repository root:

```bash
cd ~/praise/praise-cao-sim
python first_science/phase3/test_m0_analytic_composition.py
python first_science/phase3/test_diagnose_real_wb_vs_i1_m0.py
```

Expected M0 markers:

```text
PHASE3_M0_ANALYTIC_COMPOSITION_TESTS_PASS
M0_FORWARD_BOUNDARY_ALGEBRA_PASS
M0_SAME_RHO_POLICY_PASS
M0_INDEPENDENT_PRODUCT_BASELINE_PASS
M0_NOT_A_CERTIFICATE_PASS
```

Expected diagnostic-test markers:

```text
PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_TESTS_PASS
DIAGNOSTIC_DOES_NOT_SELECT_A_I_OR_RHO_I_PASS
M0_REAL_CURVE_COMPOSITION_KERNEL_PASS
WB_M0_ERROR_METRICS_PASS
DIAGNOSTIC_FILENAME_RHO_TAG_PASS
```

These tests validate the frozen M0 baseline and the diagnostic harness. Producing the actual real-data plots still requires explicit concrete `A_i` values; the diagnostic will not invent them.
