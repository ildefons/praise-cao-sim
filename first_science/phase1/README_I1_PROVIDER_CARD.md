# Phase-1 minimal I1 provider SLA card

This checkpoint starts Step 1. Step 0 remains frozen and technology-neutral. The final top-level white-box benchmark is not changed by this work.

## Scientific role

`I1` is the first provider information representation. Every provider exposes the same kind of local SLA-compliance card, and the **identical I1 cards** must be consumed by both `M0` and `M1`.

The minimal public object is a local horizon-dependent SLA-compliance probability surface:

`σ_i(A_i,H;ρ_i) = P(c_i(A_i,H) >= ρ_i)`

for provider-local admissibility regions

`A_i = {L_i <= l_i, C_i <= c_i, Q_i >= q_i}`.

The public surface contains the empirical probability, a 95% Wilson interval, the number of successful trajectories and the number of acquisition trajectories. Raw trajectories are private to the provider-side card builder and are not part of I1.

## Why rho_i is a card dimension

The top-level benchmark freezes `rho=0.95`, but M0 must not simply multiply three local probabilities evaluated at the same `rho`. For a structural certification argument, M0 can instead allocate a global request-violation allowance `epsilon=1-rho=0.05` across stochastic providers.

For an equal first pilot over three provider branches:

`epsilon_i = 0.05 / 3`

and therefore

`rho_i = 1 - epsilon_i = 0.9833333333333333`.

This is why I1 must support multiple `rho_i` values. A fixed-rho provider card would already bake an M-specific assumption into the information representation.

## Local semantics

The provider-local SLA accounting deliberately mirrors the frozen top-level accounting:

- cumulative `[0,H]` window from common `t=0`;
- a request completing within its local latency deadline is decided at completion;
- a request missing the local latency deadline is decided as a latency failure at the deadline;
- cost and quality are not evaluated after timeout;
- unresolved requests at `H` are excluded;
- zero decided requests implies compliance fraction 1;
- `sigma_i(H)` may recover for `rho_i < 1` and is not forced monotone.

The local metrics are:

- `L_i`: provider-local request arrival to provider completion;
- `C_i`: native provider execution cost for that request;
- `Q_i`: provider-local observed quality.

## Information firewall

A public I1 card must not expose:

- raw provider traces;
- acquisition seeds;
- Gamma or other hidden generator parameters;
- provider instruction means;
- the hidden physical `(Dbar, delta)` parameterization;
- simulator internal state;
- top-level white-box sigma curves or outcomes.

The card does declare the workload/context under which it was acquired because local SLA behaviour is load dependent.

## Current v1 query policy

`I1_PROVIDER_SLA_CARD_V1` intentionally supports **exact queried points only**. Interpolation and extrapolation are forbidden in this first version because either operation would add a modelling assumption to I1 itself.

The supported horizon grid is `0..240` in steps of 5 for the first pilot. The frozen rho grid includes `0.95` and the equal-M0-budget value `0.9833333333333333`, together with a small set of nearby stricter values.

The local `(l_i,c_i,q_i)` region grid is the only remaining acquisition-design item. It must be frozen before generating the real three provider cards and must be based only on provider-local information, not on top-level white-box outcomes or M0/M1 performance.

## M0-facing implication

The intended first M0 argument is structural and conservative. If local budgets are chosen so that simultaneous local request compliance guarantees the global request-level admissibility condition, and local request violation fractions satisfy

`sum_i epsilon_i <= 0.05`,

then simultaneous local cumulative SLA compliance implies top-level cumulative compliance at `rho=0.95`.

At the trajectory-probability level, an initial dependence-agnostic lower bound can therefore use a union bound:

`σ_G(H) >= max(0, 1 - sum_i (1 - σ_i(A_i,H;rho_i)))`.

This is an M0 composition rule, **not part of I1**. I1 only supplies the local probability queries and uncertainty intervals.

## Files

- `config_phase1_i1_provider_card_v1.json`: frozen minimal I1 semantics.
- `i1_provider_card.py`: simulator-independent card builder, exact query API, Wilson intervals and information-firewall validation.
- `test_i1_provider_card.py`: synthetic contract test including the M0 equal-budget rho value.

## First validation command

From `~/praise/praise-cao-sim/first_science/phase1`:

```bash
python test_i1_provider_card.py
```

Expected:

```text
PHASE1_I1_PROVIDER_CARD_TESTS_PASS
```

After this contract test passes, the next development step is to freeze a provider-local admissibility-region grid and generate real I1 cards for ProviderA/B/C using a new acquisition seed bank. Only then should the first real M0 composition experiment be run.
