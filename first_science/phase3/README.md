# PRAISE first science - Phase 3 / (I1,M0)

Phase 3 contains the topology-aware analytic M0 composition kernel. Its generic structural algebra may be developed and unit-tested independently of the final numerical I1 representation. Numerical `I1 -> M0` evaluation remains locked until Phase 2 explicitly freezes the public direct-trace I1 schema.

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

This operator algebra is not an instruction to manufacture provider-local rectangular boundaries in Phase 2. It is the M0 structural kernel for such inputs when the final I1 representation legitimately provides them or an explicitly frozen adapter supplies them.

## Independent-anchor probability rule

For `rho_G = 1 - epsilon_G` and `m` required stochastic providers, the previously agreed reference allocation is

`epsilon_i = epsilon_G / m`, `rho_i = 1 - epsilon_i`.

For the first anchor, `rho_G=0.95`, `m=3`, so the reference local level is

`rho_i = 0.9833333333333333`.

If the final I1 representation exposes the corresponding local cumulative-admissibility events, and if boundary implication, request/horizon alignment, independence, and exact information availability are all established, the independent-anchor certificate is

`sigma_G,M0_lower(H;rho_G) = product_i sigma_i(H;rho_i)`.

This remains a lower-bound/certification statement, not an unbiased point estimate.

## Current hard boundary after the direct-trace correction

Phase 2 has reopened the public I1 schema because the old single-`A_i` sigma-surface schema repeatedly encouraged an unagreed provider-envelope construction. The direct-trace design harness now requires

`provider-local evidence T_i -> explicitly frozen public I1_i`

with no percentile/quantile envelope, no `A_G -> A_i`, and no method-driven construction unless the design document explicitly says otherwise.

Therefore **the M0 numerical input adapter is currently blocked**. M0 may not force Phase 2 to expose rectangular `A_i` merely because the structural kernel accepts rectangular contracts. Once the final I1 schema is frozen, we will specify the smallest explicit adapter from that schema into the already-tested M0 kernel, or revise only the adapter if the schema makes a different input form necessary.

The frozen operator algebra itself is not reopened by this Phase-2 representation correction.

## Current implementation

- `config_phase3_m0_contract_v1.json`: frozen historical/structural M0 contract.
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

These tests validate the structural kernel only. They do not authorize numerical I1 consumption before the Phase-2 public representation is reconciled and frozen.
