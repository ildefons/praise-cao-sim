# PRAISE first science - Phase 3 / (I1,M0)

Phase 3 consumes the concrete public I1 cards produced by Phase 2. Phase-3A structural work may proceed before final card materialization because its rules are generic and outcome-independent, but numerical M0 evaluation remains locked until the final I1 cards are frozen.

Correct boundary:

`Phase 2 fixed provider A_i + I1 cards -> Phase 3 forward topology-aware M0 composition -> exogenous A_G certificate check`

`A_i` is part of the instantiated information object `I1`. Phase 3 must not derive, choose or alter provider-local admissibility regions. M0 receives the same frozen cards that will later be supplied unchanged to M1.

## Frozen M0 structural contract

`config_phase3_m0_contract_v1.json` restores the previously agreed M0 architecture, adapted only to the corrected direct-I1 ownership of A_i.

M0 is a topology-aware analytic certificate from fixed local joint contracts. It does not reconstruct hidden provider distributions.

For the currently supported graph operators, rectangular LCQ boundaries compose recursively as:

| Quantity | Sequence | ParAll / all-required parallel |
| --- | --- | --- |
| latency L | sum | maximum |
| cost C | sum | sum |
| quality Q | minimum | minimum |

Deterministic stages and network terms are represented explicitly as deterministic leaves in the same graph algebra.

The already-fixed local boundaries are therefore composed forward through `G` to produce a sufficient boundary `A_G^M0`. An exogenous global query `A_G` is certifiable only when

`l_M0 <= l_G`, `c_M0 <= c_G`, and `q_M0 >= q_G`.

Failure of this containment check is an I1/M0 limitation. It does not trigger a new `A_G -> A_i` allocation and does not reopen Phase 2.

## Frozen rho rule for the independent anchor

Let `rho_G = 1 - epsilon_G`. For `m` required stochastic providers, M0 uses the previously agreed equal violation-budget allocation

`epsilon_i = epsilon_G / m`, `rho_i = 1 - epsilon_i`.

For the first anchor, `rho_G=0.95` and `m=3`, hence

`rho_i = 0.9833333333333333`,

which is already present in the frozen I1 rho support.

Under aligned cumulative accounting on the same required root-request population, the union of the local violation sets has fraction at most `sum_i epsilon_i <= epsilon_G`. Therefore the conjunction of all local trajectory events is sufficient for the global cumulative rho requirement whenever the forward boundary containment also holds.

For the deliberately independent anchor, the probability certificate is

`sigma_G,M0_lower(H;rho_G) = product_i sigma_i(A_i,H;rho_i)`.

This is a lower-bound/certification probability, not an unbiased point estimate.

## Hard preconditions

A numerical M0 certificate is emitted only when all of the following are established: the forward-composed fixed local boundary is contained in the requested `A_G`; local/global request accounting is aligned at the evaluated horizon; the required local trajectory-level events are independent for the anchor; and the requested `H,rho_i` card points exist exactly in the frozen I1 cards.

If any condition is missing, M0 reports `NOT_CERTIFIED` rather than manufacturing an estimate.

## Current implementation

- `config_phase3_m0_contract_v1.json`: frozen structural/information/probability contract.
- `m0_analytic_composition.py`: recursive Sequence/ParAll LCQ algebra, global containment check, equal violation-budget rho allocation, independent-product certificate, and explicit precondition guard.
- `test_m0_analytic_composition.py`: simulator-independent hand-checkable regression tests.

The implementation deliberately contains no private provider evidence, no white-box sigma values, and no inverse `A_G -> A_i` construction.

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

Numerical card consumption and comparison against the frozen Phase-1 white-box reference remain locked until Phase 2 materializes and hash-freezes the final direct-I1 cards.
