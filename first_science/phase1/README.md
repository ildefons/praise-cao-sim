# PRAISE first science — Phase 1

**Status: IN DEVELOPMENT.**

## Purpose

Construct and freeze one technology-neutral white-box reference regime and its admissibility-region calibration before any I1, M0, or M1 implementation.

AICon/YAFS execution of the physical graph is the sole white-box truth generator. Phase 1 must not analytically fabricate white-box outcomes and must not use M0/M1 performance to select the benchmark.

## Physical graph

`Fpre -> ParAll(A,B,C) -> Fpost`

A/B/C intentionally use the same or deliberately similar native service-module implementation. Their stochasticity enters through a new native per-request realization of `Message.instructions`. The default white-box instruction family is gamma, with a fixed shared CV and provider-specific means determined by the center/dispersion parameterization:

- `A = center * (1-delta)`
- `B = center`
- `C = center * (1+delta)`

AICon/YAFS causally generates service, queueing, latency, cost, and quality. `L`, `C`, and `Q` are never directly sampled by an auxiliary outcome model. Quality remains `Q=x`.

## Current checkpoint boundary

The numerical pre-search configuration is intentionally incomplete. `config_phase1.json` contains `null` for every design constant that remains to be explicitly frozen in discussion. No scientific candidate run is allowed until `assert_phase1_presearch_configuration_is_frozen(...)` passes on the actual configuration.

Already frozen in the contract:

- scientific Step 0 remains technology-neutral;
- `H* = 120`;
- horizon domain `[0, 240]`;
- calibration target `0.95` separately for latency and cost;
- `q*=x`;
- joint survival is not forced to 0.95;
- coarse candidate evaluation uses `N=100` trajectories;
- native stochasticity enters through `Message.instructions`;
- no direct stochastic sampling of `L`, `C`, or `Q`.

## Development requirement

Non-trivial functions use explicit self-explanatory snake-case names. Each non-trivial function carries a docstring describing purpose, inputs/outputs/side effects as relevant, and a maintained **Called by** provenance identifying caller functions and Python modules.

## Simulator-independent test

```bash
python test_presearch_contract.py
```

Expected:

```text
PHASE1_PRESEARCH_CONTRACT_TESTS_PASS
```

This test does not run AICon/YAFS and does not constitute Phase-1 scientific validation.

## Next step

Continue the design-document pre-search freeze discussion. Only after every required `null` value is explicitly resolved should the native `G0` runner and reference-regime search be implemented.
