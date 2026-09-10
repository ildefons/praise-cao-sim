# PRAISE first science - Phase 3 / (I1,M0)

Phase 3 contains the topology-aware analytic M0 composition kernel. The public I1 schema is already frozen in Phase 2. Numerical M0 evaluation is waiting only for the three concrete provider-local `A_i` instances and the corresponding final hash-frozen I1 cards.

## Frozen M0 structural kernel

`config_phase3_m0_contract_v1.json` and `m0_analytic_composition.py` retain the previously agreed M0 core:

- structure-aware analytic composition;
- recursive LCQ algebra for supported composition operators;
- explicit deterministic fixed-stage/network terms;
- global containment check;
- equal violation-budget rho rule for the independent all-required anchor;
- product probability certificate only when every hard precondition is established;
- `NOT_CERTIFIED` rather than inventing an estimate when a hard precondition fails.

For rectangular LCQ contract inputs, the currently supported operator algebra is:

| Quantity | Sequence | ParAll / all-required parallel |
| --- | --- | --- |
| latency L | sum | maximum |
| cost C | sum | sum |
| quality Q | minimum | minimum |

These local rectangular contracts are not chosen by M0. They are the `A_i` already contained in the frozen I1 card instances produced by Phase 2.

## Frozen I1 input semantics

Each provider card has the already-agreed form

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`.

M0 receives the identical final cards later supplied to M1. It may choose only which already-exposed `rho` slice(s) to consume according to its frozen composition rule. It may not create, alter, or rematerialize `A_i`.

## Independent-anchor probability rule

For `rho_G = 1 - epsilon_G` and `m` required stochastic providers, the reference allocation is

`epsilon_i = epsilon_G / m`, `rho_i = 1 - epsilon_i`.

For the first anchor, `rho_G=0.95`, `m=3`, hence

`rho_i = 0.9833333333333333`,

which is already present in the frozen I1 rho support.

When forward boundary containment, request/horizon alignment, independence, and exact card-point availability all hold, the independent-anchor certificate is

`sigma_G,M0_lower(H;rho_G) = product_i sigma_i(A_i,H;rho_i)`.

This is a lower-bound/certification probability, not an unbiased point estimate.

## Current boundary

Phase 2 is not redesigning I1. The only remaining Phase-2 scientific choice is the concrete provider-local mapping

`T_i -> A_i`.

The rejected percentile/p99 branch was one attempted answer to that narrow question and has been removed. Once the three `A_i` values are explicitly frozen and their I1 cards are materialized/hash-frozen, numerical M0 can begin immediately with no additional I1-schema decision.

## Current implementation

- `config_phase3_m0_contract_v1.json`: frozen M0 structural/information/probability contract.
- `m0_analytic_composition.py`: recursive Sequence/ParAll LCQ algebra, containment check, equal violation-budget rule, independent-product certificate, and hard-precondition guard.
- `test_m0_analytic_composition.py`: simulator-independent hand-checkable regression tests.

The implementation contains no private provider evidence, no white-box sigma values, and no inverse `A_G -> A_i` construction.

## Validation

Starting from the repository root:

```bash
python first_science/phase3/test_m0_analytic_composition.py
```

Expected:

```text
PHASE3_M0_ANALYTIC_COMPOSITION_TESTS_PASS
M0_FORWARD_BOUNDARY_ALGEBRA_PASS
M0_EQUAL_VIOLATION_BUDGET_PASS
M0_INDEPENDENT_CERTIFICATE_GUARD_PASS
```

These tests validate the structural kernel. Numerical execution is blocked only until the concrete Phase-2 `A_i` instances and final I1 cards are frozen.
