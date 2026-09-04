# Phase 2 — I1 provider SLA-compliance surface

Phase 2 freezes the first provider information technology. Phase 1 remains the immutable Step-0 white-box benchmark.

## Public I1 object

For one exact provider-local admissibility region

`A_i = {L_i <= l_i, C_i <= c_i, Q_i >= q_i}`

and declared workload/context `W_i`, a public card instance is

`I1_i = (A_i, W_i, R, {sigma_i(A_i,H;rho): H in H, rho in R})`

with

`sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)`.

The frozen first-experiment axes are:

- `H = 0..240` in steps of 5;
- `R = {0.95, 0.975, 0.9833333333333333, 0.99, 1.0}`.

The card also exposes a 95% Wilson interval, successful-trajectory count and acquisition-trajectory count at every surface point.

The new SLA definition does not require a different simulator run for each rho. One provider trajectory determines `c_i(A_i,H)`; the whole rho surface is obtained by thresholding the same cumulative-compliance values.

## A_i is not selected by I1

I1 does **not** optimize or choose `(l_i,c_i,q_i)`, and Phase 2 does not build an arbitrary L/C/Q grid.

`A_i` is an exact query argument supplied by a consuming composition method. The method must declare the requested local regions before inspecting I1 sigma values or the Phase-1 top-level sigma outcomes. I1 then deterministically materializes those exact card instances from the already-frozen private provider corpus.

This is important for the factorization `tau=(I,M)`: a local budget allocation belongs to `M`, not to `I`.

For a fair `(I1,M0)` versus `(I1,M1)` comparison, the exact same materialized card instances are supplied unchanged to both methods.

## Provider-local semantics

The local accounting mirrors the frozen Phase-1 SLA semantics:

- cumulative `[0,H]` from common `t=0`;
- `L_i` is provider arrival to provider completion, including provider queue wait and service;
- an in-time request is decided at provider completion;
- a local latency miss is decided at its local latency deadline;
- cost and quality are not evaluated after a timeout;
- unresolved requests at `H` are excluded;
- zero decided requests implies compliance fraction 1;
- `sigma_i(H;rho)` may be non-monotone in H when `rho<1`;
- at fixed `A_i,H`, `sigma_i(H;rho)` is non-increasing in rho.

`C_i` is native provider execution cost for the request and `Q_i` is native provider-observed quality.

## Phase 2 acquisition

The provider evidence is acquired once using the frozen matched physical regime and a fresh independent seed bank `6000..6099` (`N=100`). The full native graph is used only to preserve the actual provider arrival context. Native full-graph traces and top-level ledgers are temporary; only provider-local ledgers persist.

For each root request that completed Fpre, provider arrival is reconstructed as

`Fpre completion + native branch-link delay`

and cross-checked against native `time_reception` whenever a provider metric row exists. This retains requests that reached a provider but were still queued at the simulation stop.

The frozen private corpus contains only the local ledger columns needed by the SLA accounting:

`trajectory, request_id, emission, completion, L, C, Q`

where `emission` means **provider arrival**, not root-source emission.

All later A_i/H/rho card queries are deterministic post-processing of this same corpus. There is no rerun per A_i or rho.

## Information firewall

A public I1 card must not expose raw provider traces, private request ledgers, acquisition seeds, hidden generator parameters, provider instruction means, hidden physical `(Dbar,delta)` labels, simulator state, or top-level Phase-1 white-box curves/outcomes.

The workload/context is public because provider SLA behavior is load dependent.

## Files

- `config_phase2_i1_provider_card_v1.json`: frozen public I1 contract and H x R surface.
- `config_phase2_i1_acquisition_v1.json`: frozen private acquisition protocol.
- `i1_provider_card.py`: card builder, exact query API, confidence intervals and firewall.
- `i1_provider_acquisition.py`: fresh provider-local acquisition runner.
- `materialize_i1_cards.py`: deterministic public-card materializer for predeclared exact A_i queries.
- `test_i1_provider_card.py`: simulator-independent card/surface tests.
- `test_i1_provider_acquisition.py`: provider arrival/ledger extraction tests.

## Validation sequence

Starting from `~/praise/praise-cao-sim/first_science/phase2`:

```bash
python test_i1_provider_card.py
python test_i1_provider_acquisition.py
```

Expected:

```text
PHASE2_I1_PROVIDER_CARD_TESTS_PASS
PHASE2_I1_PROVIDER_ACQUISITION_TESTS_PASS
```

The real acquisition then requires the AICon/YAFS import path and runs `N=100` fresh trajectories. Its success marker is:

```text
PHASE2_I1_ACQUISITION_RUN_PASS
```

Once that corpus is frozen, Phase 2 is scientifically complete: later methods may request exact A_i card instances, but they cannot change the I1 evidence, H/R support, SLA semantics or public/private boundary.
