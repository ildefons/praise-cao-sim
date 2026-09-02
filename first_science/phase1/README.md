# PRAISE first science — Phase 1

**Status: IN DEVELOPMENT.**

## Purpose

Construct and freeze a small technology-neutral battery of white-box reference regimes and admissibility regions before any I1, M0, or M1 implementation.

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

## Scientific discovery contract

The numerical scientific configuration remains intentionally incomplete. `config_phase1.json` contains `null` for every scientific design constant that has not yet been explicitly frozen. No scientific discovery candidate may be evaluated until `assert_phase1_discovery_configuration_is_frozen(...)` passes.

Already frozen in the scientific contract:

- scientific Step 0 remains technology-neutral;
- `H* = 120`;
- horizon domain `[0, 240]`;
- calibration target `0.95` separately for latency and cost;
- `q*=x`;
- joint survival is not forced to 0.95;
- scientific candidate/AR discovery uses `N=10` trajectories per candidate;
- the same N=10 discovery seed bank is used across physical candidates;
- at N=10, `0.9` and `1.0` are the empirical bracket around target `0.95`; N=10 is not a precision estimate of 0.95;
- native stochasticity enters through provider `Message.instructions` service-instruction requirements;
- root workload `W` remains conceptually separate and fixed;
- no direct stochastic sampling of `L`, `C`, or `Q`.

The first empirical crossing below a target must be located at an **exact first-violation event time**, not rounded to the reporting horizon grid. The grid remains appropriate for common CSV output and later M1 full-curve fitting.

## Discovery -> freeze finalists -> N=100 confirmation

Phase 1 deliberately separates cheap discovery from confirmation:

1. **Discovery (`N=10` per candidate).** Search many `(Dbar, delta)` provider settings under one common N=10 seed bank. For each physical candidate, reuse its native ledgers to scan many `A={L<=l,C<=c,Q>=x}` offline. Discovery ranks white-box candidates only by white-box properties: anchor relevance, nondegenerate sigma-curve shape, first-violation timing/cause structure, and stability diagnostics. M0/M1 are forbidden.
2. **Freeze finalists.** Retain a small diagnostic battery, for example latency-sensitive, cost-sensitive, and mixed cases. Freeze each finalist's exact physical parameters and exact `A=(l_max,c_max,q_min)` in `selected_whiteboxes.json` with status `FROZEN_FOR_CONFIRMATION`.
3. **Confirmation (`N=100` per selected white box).** Rerun only those exact finalists using 100 fresh independent trajectories. The confirmation seed bank must be disjoint from discovery. **Do not recalibrate A on the N=100 data.** Confirmation tests whether the white-box regime/AR discovered at N=10 replicates with 0.01 vertical sigma resolution.
4. **Later final precision, only if needed.** Once the benchmark cases are confirmed and frozen, increase N further only if the final reference curves need more precision for the M0/M1 comparison. Increasing N must not reopen physical parameters or A.

`assert_phase1_confirmation_configuration_is_ready(...)` enforces the fresh-seed N=100 confirmation policy and rejects an empty/unfrozen finalist manifest.

## N=10 development atlas

A separate **development-only N=10 atlas** has already validated native execution, the `(Dbar, delta)` parameterization, offline AR scanning, exact-event sigma reconstruction and curve diagnostics.

`config_phase1_atlas_smoke.json` defines an explicit 3 x 3 development grid. These numerical constants are diagnostic and the development atlas remains marked **non-scientific** even though scientific discovery now also uses N=10. The difference is governance: scientific discovery requires the frozen scientific configuration and produces candidate-selection provenance.

For each physical setting, `whitebox_atlas.py` executes the native composed graph with the same 10 development seeds and caches top-level request ledgers. `atlas_analysis.py` then scans `A={L<=l,C<=c,Q>=x}` offline without rerunning the simulator. Candidate thresholds are generated immediately below/at/above each trajectory's critical L/C threshold at `H*=120`, allowing N=10 to expose its achievable 0.1-resolution sigma levels.

The atlas writes `achievable_sigmas.csv` and `representative_regions_by_sigma.csv`, including latency-first and cost-first violation counts. `generate_sigma_plots.py` reconstructs exact-event empirical sigma staircases. `sigma_curve_diagnostics.py` measures finite-N resolution and split-half curve stability without smoothing. See `README_ATLAS.md` for commands and output details.

## Selected-whitebox manifest

`selected_whiteboxes.json` is intentionally empty until discovery selects finalists. Confirmation requires it to be edited to:

```json
{
  "status": "FROZEN_FOR_CONFIRMATION",
  "whiteboxes": [
    {
      "case_id": "...",
      "selection_role": "latency|cost|mixed|other",
      "physical_setting_id": "...",
      "center_instruction_mean": 0.0,
      "dispersion": 0.0,
      "l_max": 0.0,
      "c_max": 0.0,
      "q_min": 0.0
    }
  ]
}
```

The values above are placeholders only. The actual manifest must be generated from retained N=10 discovery results, not invented manually.

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

The native N=10 development atlas is already validated. The next gate is to freeze the remaining numerical scientific discovery constants in `config_phase1.json` (including search bounds, common N=10 discovery seeds and candidate budget), then implement/run the scientific discovery driver. N=100 is **not** used across the search space; it is reserved for fresh-seed confirmation of the exact frozen finalists.

At final precision, inspect exact-event sigma curves together with the resolution diagnostics. If the empirical staircase is still too coarse for the effect sizes being compared or split-half curves remain materially unstable, increase N without altering the frozen physical regime, admissibility region, graph or method definitions. Artificial smoothing is not a substitute for Monte Carlo convergence.
