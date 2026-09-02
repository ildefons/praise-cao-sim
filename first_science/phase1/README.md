# PRAISE first science — Phase 1

**Status: IN DEVELOPMENT.**

## Purpose

Construct and freeze one technology-neutral white-box reference regime and its admissibility-region calibration before any I1, M0, or M1 implementation.

AICon/YAFS execution of the physical graph is the sole white-box truth generator. Phase 1 must not analytically fabricate white-box outcomes and must not use M0/M1 performance to select the benchmark.

## Primary sigma semantics

The authoritative event is cumulative admissibility through the horizon:

`σ_G(A,H) = P(no violation of A occurs at any time t <= H)`.

In the event-driven simulator, `T_violation,A` denotes the time of the first actual latency/cost/quality violation event under the declared observation semantics, with `+inf` if no violation occurs. Therefore the exact computational representation is:

`σ_G(A,H) = P(T_violation,A > H)`.

A violation exactly at `H` counts as violated by `H`. The reporting horizon grid does not define sigma; it is used only for stored comparison/fitting tables. Exact white-box target-crossing times must be taken from first-violation events. See `SIGMA_SEMANTICS_AUDIT.md`.

## Physical graph and provider instruction semantics

`Fpre -> ParAll(A,B,C) -> Fpost`

A/B/C intentionally use the same or deliberately similar native service-module implementation. Their stochasticity enters through a new native per-request realization of `Message.instructions`.

For this benchmark, the interpretation of that field is frozen:

- `D_i` / `Message.instructions` is the computational instruction requirement of provider `i` for one service invocation.
- `Dbar` is the central mean provider service-instruction requirement per invocation.
- `delta` controls provider-to-provider heterogeneity in that mean requirement:
  - `A = Dbar * (1-delta)`
  - `B = Dbar`
  - `C = Dbar * (1+delta)`
- `delta` is not request-to-request stochastic variability; the latter is controlled separately by the frozen gamma CV.
- `D_i` is not the external/root workload. Workload `W` is fixed separately by the root invocation timing/pattern (period/rate and phase).

Existing code/configuration names such as `center_instruction_mean` are retained for compatibility, but their scientific meaning is the provider service-instruction requirement above.

AICon/YAFS causally generates service, queueing, latency, cost, and quality from those provider requirements together with the fixed execution/resource/environment configuration. `L`, `C`, and `Q` are never directly sampled by an auxiliary outcome model. Quality remains `Q=x`.

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
- native stochasticity enters through provider `Message.instructions` service-instruction requirements;
- root workload `W` remains conceptually separate and fixed;
- no direct stochastic sampling of `L`, `C`, or `Q`.

For the later scientific search, the first empirical crossing below the target must be located at an **exact first-violation event time**, not rounded to the reporting horizon grid. The grid remains appropriate for common CSV output and M1 full-curve fitting.

## N=10 development atlas

A separate **development-only N=10 atlas** is implemented to answer a narrower question before Bayesian optimization:

> Is the two-dimensional provider family `(Dbar, delta)` already capable of generating a useful range of white-box survival behaviours and L/C admissibility regions?

`config_phase1_atlas_smoke.json` defines an explicit 3 x 3 development grid of `(Dbar, delta)` settings. These numerical constants are diagnostic and are **not frozen scientific benchmark values**.

For each physical setting, `whitebox_atlas.py` executes the native composed graph with the same 10 development seeds and caches top-level request ledgers. `atlas_analysis.py` then scans `A={L<=l,C<=c,Q>=x}` offline without rerunning the simulator. Candidate thresholds are generated immediately below/at/above each trajectory's critical L/C threshold at `H*=120`, allowing N=10 to expose its achievable 0.1-resolution sigma levels.

The atlas writes `achievable_sigmas.csv` and `representative_regions_by_sigma.csv`, including latency-first and cost-first violation counts. `generate_sigma_plots.py` reconstructs exact-event empirical sigma staircases. `sigma_curve_diagnostics.py` measures finite-N resolution and split-half curve stability without smoothing. See `README_ATLAS.md` for commands and output details.

The development atlas is not scientific evidence and does not replace the later N=100 candidate evaluation.

## Development requirement

Non-trivial functions use explicit self-explanatory snake-case names. Each non-trivial function carries a docstring describing purpose, inputs/outputs/side effects as relevant, and a maintained **Called by** provenance identifying caller functions and Python modules.

## Simulator-independent tests

```bash
python test_presearch_contract.py
python test_atlas_analysis.py
python test_whitebox_atlas_configuration.py
python test_generate_sigma_plots.py
python test_sigma_curve_diagnostics.py
```

Expected:

```text
PHASE1_PRESEARCH_CONTRACT_TESTS_PASS
PHASE1_ATLAS_ANALYSIS_TESTS_PASS
PHASE1_WHITEBOX_ATLAS_CONFIGURATION_TESTS_PASS
PHASE1_SIGMA_PLOT_TESTS_PASS
PHASE1_SIGMA_CURVE_DIAGNOSTIC_TESTS_PASS
```

## Current freeze gate

The N=10 atlas implementation must first pass native AICon/YAFS integration on the pinned AICon baseline. Only after inspecting the resulting achievable-sigma/AR landscape do we decide whether `(Dbar, delta)` is sufficiently expressive or whether a further physical dimension must be reopened. The N=100 scientific reference-regime search remains fail-closed meanwhile.

At final high-N confirmation, inspect exact-event sigma curves together with the resolution diagnostics. If the empirical staircase is still too coarse for the effect sizes being compared or split-half curves remain materially unstable, increase N without altering the frozen physical regime, admissibility region, graph or method definitions. Artificial smoothing is not a substitute for Monte Carlo convergence.
