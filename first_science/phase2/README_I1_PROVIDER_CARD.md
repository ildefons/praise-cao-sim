# Phase-2 minimal I1 provider SLA card

Phase 2 starts Step 1. The Phase-1 Step-0 white-box benchmark remains frozen and technology-neutral; this work only consumes its frozen SLA-accounting semantics and later compares against its fixed top-level reference curves.

## Scientific role

`I1` is the first provider information representation. Every provider exposes the same kind of local SLA-compliance card, and the identical I1 cards must be consumed by both `M0` and `M1`.

The minimal public object is

`σ_i(A_i,H;ρ_i) = P(c_i(A_i,H) >= ρ_i)`

for provider-local admissibility regions

`A_i = {L_i <= l_i, C_i <= c_i, Q_i >= q_i}`.

The public surface contains the empirical probability, a 95% Wilson interval, successful-trajectory count and acquisition-trajectory count. Raw observations remain private to provider-side acquisition and are not part of I1.

## Why rho_i is a card dimension

The top-level Step-0 benchmark freezes `rho=0.95`, but M0 must not simply multiply three local probabilities evaluated at the same rho. A structural certification method can allocate the global request-violation allowance `epsilon=1-rho=0.05` across the three stochastic providers.

For the equal-budget first pilot:

`epsilon_i = 0.05 / 3`

and

`rho_i = 1 - epsilon_i = 0.9833333333333333`.

Therefore rho is a query dimension of I1. The particular allocation is an M0 choice, not an I1 assumption.

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

The first pilot horizon grid is `0..240` in steps of 5. The rho grid includes `0.95`, the equal-M0-budget value `0.9833333333333333`, and nearby stricter values.

The local `(l_i,c_i,q_i)` region grid remains the only open acquisition-design item. It must be frozen before the real ProviderA/B/C cards are built and must use provider-local information only.

## M0-facing implication

If M0 chooses local admissibility budgets such that simultaneous local request compliance implies the global request-level admissibility condition, and local violation fractions satisfy

`sum_i epsilon_i <= 0.05`,

then simultaneous local cumulative SLA compliance implies top-level cumulative compliance at `rho=0.95`.

At the trajectory-probability level a dependence-agnostic first lower bound is

`σ_G(H) >= max(0, 1 - sum_i (1 - σ_i(A_i,H;rho_i)))`.

This is an M0 rule, not part of I1.

## Validation

From `~/praise/praise-cao-sim/first_science/phase2` run:

```bash
python test_i1_provider_card.py
```

Expected:

```text
PHASE2_I1_PROVIDER_CARD_TESTS_PASS
```

After this contract test passes, the next development step is to freeze a provider-local admissibility-region grid and generate the three real I1 cards using a new acquisition seed bank. Only then should the first real M0 composition pilot run.
