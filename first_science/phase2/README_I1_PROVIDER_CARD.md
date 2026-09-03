# Phase-2 minimal I1 provider SLA card

Phase 2 starts Step 1. The Phase-1 Step-0 white-box benchmark remains frozen and technology-neutral; this work only consumes its frozen SLA-accounting semantics and later compares against its fixed top-level reference curves.

## Scientific role

`I1` is the first provider information representation. Every provider exposes the same kind of local SLA-compliance card, and the identical I1 cards must be consumed by both `M0` and `M1`.

The minimal public object is

`σ_i(A_i,H;ρ_i) = P(c_i(A_i,H) >= ρ_i)`

for provider-local admissibility boundaries

`A_i = {L_i <= l_i, C_i <= c_i, Q_i >= q_i}`.

The public card contains the empirical probability curve, a 95% Wilson interval, successful-trajectory count and acquisition-trajectory count. Raw observations remain private to provider-side acquisition and are not part of I1.

## The Phase-1 global ARs define the first I1 test points

The first pilot does **not** construct an arbitrary provider-local `(l_i,c_i,q_i)` grid. Phase 1 already selected three meaningful, nondegenerate top-level diagnostic problems: latency-dominant, cost-dominant and mixed L/C.

For each frozen top-level

`A_G = {L_G <= l_G, C_G <= c_G, Q_G >= q_G}`,

M0's declared topology/budget decomposition produces exactly one local boundary `A_i` for each ProviderA/B/C. These nine exact provider/cell points are the minimal I1 support required for the first comparison. The resulting cards are frozen and supplied unchanged to M0 and M1.

A broader local L/C/Q surface is deferred until a later method actually requires allocation search or interpolation. We do not manufacture extra information before it is scientifically needed.

## Why rho_i is a card dimension

The top-level Step-0 benchmark freezes `rho_G=0.95`, but M0 must not simply multiply three local probabilities evaluated at the same rho. The first structural certification method allocates the global request-violation allowance `epsilon_G=1-rho_G=0.05` equally across the three stochastic providers:

`epsilon_i = 0.05 / 3`

and

`rho_i = 1 - epsilon_i = 0.9833333333333333`.

Therefore rho is a query dimension of I1. The particular allocation remains an M0 design rule rather than hidden provider information.

## Local SLA semantics

The provider-local accounting mirrors the frozen Phase-1 semantics:

- cumulative `[0,H]` from common `t=0`;
- an in-time request is decided at local provider completion;
- a timeout is decided as a latency failure at the local latency deadline;
- cost and quality are not evaluated after timeout;
- unresolved requests at H are excluded;
- zero decided requests implies compliance fraction 1;
- `sigma_i(H)` may recover when `rho_i < 1`; monotonicity is not imposed.

The local metrics are:

- `L_i`: provider-local request arrival to provider completion;
- `C_i`: native provider execution cost for that local request;
- `Q_i`: provider-local observed quality.

## Information firewall

A public I1 card must not expose raw provider traces, acquisition seeds, hidden generator parameters, provider instruction means, hidden `(Dbar,delta)` labels, simulator state, or top-level Phase-1 white-box curves/outcomes.

The workload/context under which the card was acquired is public because local SLA behavior is load dependent.

## Current v1 query policy

V1 supports exact queried points only. Interpolation and extrapolation are forbidden so that an interpolation model is not silently bundled into the information representation.

The first pilot uses the common `H=0..240` reporting support in steps of 5. The primary local SLA requirement for M0 is `rho_i=0.9833333333333333`; nearby rho values remain available for later sensitivity but do not alter the frozen Phase-1 benchmark.

## M0-facing implication

If M0 chooses local L/C/Q boundaries such that simultaneous local request compliance implies global request admissibility, and the local violation fractions satisfy

`sum_i epsilon_i <= 0.05`,

then on an aligned common set of logical requests the all-provider local conjunction has compliance fraction at least `rho_G=0.95`.

For the deliberately independent first anchor, M0 then composes the trajectory-level I1 probabilities as

`σ_M0(H) = product_i σ_i(A_i,H;rho_i)`.

This product is an M0 rule, not part of I1. Its interpretation as a formal lower-bound certificate additionally requires the real anchor's request-set/horizon accounting and fixed-stage latency assumptions to be audited; see `README_M0.md`.

## Validation

Starting from `~/praise/praise-cao-sim/first_science/phase2`:

```bash
python test_i1_provider_card.py
python test_m0_contract_composition.py
```

Expected:

```text
PHASE2_I1_PROVIDER_CARD_TESTS_PASS
PHASE2_M0_CONTRACT_COMPOSITION_TESTS_PASS
```

After these contract tests pass, the next step is to derive the nine exact local boundaries from the full-precision frozen Phase-1 manifest and audit the real anchor conditions needed by M0 before generating the provider cards.
