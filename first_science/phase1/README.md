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

## Scientific pre-search contract

The numerical scientific pre-search configuration remains intentionally incomplete. `config_phase1.json` contains `null` for every scientific design constant that has not yet been explicitly frozen. No N=100 scientific candidate search is allowed until `assert_phase1_presearch_configuration_is_frozen(...)` passes on that configuration.

Already frozen in the scientific contract:

- scientific Step 0 remains technology-neutral;
- `H* = 120`;
- horizon domain `[0, 240]`;
- calibration target `0.95` separately for latency and cost;
- `q*=x`;
- joint survival is not forced to 0.95;
- coarse candidate evaluation remains `N=100` trajectories;
- native stochasticity enters through `Message.instructions`;
- no direct stochastic sampling of `L`, `C`, or `Q`.

## N=10 development atlas

A separate **development-only N=10 atlas** is implemented to answer a narrower question before Bayesian optimization:

> Is the two-dimensional physical family `(Dbar, delta)` already capable of generating a useful range of white-box survival behaviours and L/C admissibility regions?

`config_phase1_atlas_smoke.json` defines an explicit 3 x 3 development grid of `(Dbar, delta)` settings. These numerical constants are diagnostic and are **not frozen scientific benchmark values**.

For each physical setting, `whitebox_atlas.py` executes the native composed graph with the same 10 development seeds and caches top-level request ledgers. `atlas_analysis.py` then scans `A={L<=l,C<=c,Q>=x}` offline without rerunning the simulator. Candidate thresholds are generated immediately below/at/above each trajectory's critical L/C threshold at `H*=120`, allowing N=10 to expose its achievable 0.1-resolution sigma levels.

The atlas writes `achievable_sigmas.csv` and `representative_regions_by_sigma.csv`, including latency-first and cost-first violation counts. See `README_ATLAS.md` for commands and output details.

The development atlas is not scientific evidence and does not replace the later N=100 candidate evaluation.

## Development requirement

Non-trivial functions use explicit self-explanatory snake-case names. Each non-trivial function carries a docstring describing purpose, inputs/outputs/side effects as relevant, and a maintained **Called by** provenance identifying caller functions and Python modules.

## Simulator-independent tests

```bash
python test_presearch_contract.py
python test_atlas_analysis.py
python test_whitebox_atlas_configuration.py
```

Expected:

```text
PHASE1_PRESEARCH_CONTRACT_TESTS_PASS
PHASE1_ATLAS_ANALYSIS_TESTS_PASS
PHASE1_WHITEBOX_ATLAS_CONFIGURATION_TESTS_PASS
```

## Current freeze gate

The N=10 atlas implementation must first pass native AICon/YAFS integration on the pinned AICon baseline. Only after inspecting the resulting achievable-sigma/AR landscape do we decide whether `(Dbar, delta)` is sufficiently expressive or whether a further physical dimension must be reopened. The N=100 scientific reference-regime search remains fail-closed meanwhile.
