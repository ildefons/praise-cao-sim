# Phase 1 development white-box atlas

This development checkpoint asks a deliberately empirical question before the scientific discovery search:

> Is the two-dimensional physical family `(Dbar, delta)` already rich enough to generate useful white-box survival behaviour and admissibility regions?

The atlas is **not scientific evidence**. It validates the same native machinery that will later support scientific discovery, but it uses a development-only configuration. Scientific discovery now also uses N=10 per candidate; the distinction is governance, frozen configuration, candidate provenance and finalist selection.

## Development physical grid

`config_phase1_atlas_smoke.json` defines three central mean provider service-instruction requirements and three symmetric provider-heterogeneity magnitudes, giving 9 physical settings. Each setting uses the same 10 development seeds.

The interpretation is deliberately explicit:

- `Dbar` is the central mean number of computational instructions required by a provider service to execute one invocation.
- `delta` is provider-to-provider heterogeneity in that mean requirement: A uses `Dbar*(1-delta)`, B uses `Dbar`, and C uses `Dbar*(1+delta)`.
- `delta` is **not** request-to-request stochastic variability; that is controlled separately by the frozen gamma CV.
- `Dbar` is **not** the external/root workload. The root workload `W` is fixed separately by the periodic invocation process (period/rate and phase).

Existing implementation/configuration names such as `center_instruction_mean` are retained for compatibility, but comments and scientific interpretation use the provider service-instruction-requirement semantics above.

A/B/C are structurally identical native AICon/YAFS service modules. Every invocation samples a fresh seeded gamma realization through `Message.instructions`; that realization is the computational work required by the provider service for that invocation. AICon/YAFS then causally generates service time, queueing, L, C, and Q. Fpre and Fpost are deterministic.

## Two-stage execution

1. `whitebox_atlas.py` executes the native composed graph `Fpre -> ParAll(A,B,C) -> Fpost` and writes one top-level ledger row per logical request.
2. `atlas_analysis.py` reuses those ledgers and scans many `A={L<=l,C<=c,Q>=x}` regions offline. Threshold candidates are generated around each trajectory's critical L/C value at `H*=120`, so N=10 exposes the actually achievable 0.1-resolution survival transitions without an arbitrary dense threshold grid.

Outputs include:

- `all_top_level_request_ledgers.csv`
- `physical_settings.csv`
- `admissibility_regions.csv`
- `survival_curves.csv`
- `achievable_sigmas.csv`
- `representative_regions_by_sigma.csv`

The last table gives compact example A regions for each achievable sigma at H=120, including latency-first and cost-first violation counts.

## Primary sigma semantics

The authoritative scientific event is cumulative admissibility:

`σ_G(A,H) = P(no violation of A occurs at any time t <= H)`.

Under the declared event-driven latency/cost/quality semantics, let `T_violation,A` be the time of the first **actual violation event**, with `+inf` if none occurs. Then the computational form is exactly:

`σ_G(A,H) = P(T_violation,A > H)`.

A violation exactly at `H` counts as violated by `H`. The first-event representation is a lossless compression for this cumulative no-violation event; it is not a different scientific definition.

See `SIGMA_SEMANTICS_AUDIT.md` for the Phase-0/Phase-1 audit.

## Sigma-curve plotting post-process

`generate_sigma_plots.py` is simulator-independent. It does **not** plot by interpolating the stored 5-unit reporting grid. For every selected admissibility region it goes back to `all_top_level_request_ledgers.csv`, reconstructs one exact first-violation time per trajectory using the same frozen latency/cost/quality event semantics as `atlas_analysis.py`, and draws the exact empirical survival function over the complete configured domain `0 <= H <= 240`.

The finite-sample estimator is:

`σ_hat(H) = (1/N) * sum_j 1[T_violation,j > H]`.

Therefore the empirical curve is a staircase whose horizontal coordinate is continuous over the full horizon and whose vertical drops occur at the actual observed first-violation times. The stored `survival_curves.csv` 5-unit horizon grid is a reporting table only and does not determine the PNG geometry or an exact target-crossing time.

With N=10 the vertical probability resolution is 0.1; with N=100 it is 0.01. No artificial smoothing is applied.

The PNGs are written into:

`results/development_atlas/sigma_plots/`

For each physical setting the post-process selects the closest achievable anchor-sigma level at or below the target and the closest level at or above the target. With N=10 and target `0.95`, these will normally be `0.9` and `1.0`. This bracket is appropriate for discovery/diagnostics; it is not a claim that N=10 estimates 0.95 precisely. All representative ARs retained at those selected sigma levels are plotted, so latency-first, cost-first, and mixed representatives are not silently collapsed to one AR.

Run after the atlas:

```bash
python generate_sigma_plots.py
```

Expected marker:

```text
PHASE1_SIGMA_PLOTS_PASS
```

Generated plot metadata are also recorded in:

`results/development_atlas/sigma_plots/best_sigma_plot_selection.csv`

## Curve-resolution / convergence diagnostics

`sigma_curve_diagnostics.py` evaluates the same best/bracketing ARs without smoothing the empirical curve. It records finite-N resolution and a deterministic split-half stability check:

- vertical probability resolution `1/N`;
- exact sigma at `H*`;
- failures by `H*` and by simulator stop;
- number of unique first-violation event times;
- maximum empirical jump;
- longest plateau and fraction of the domain;
- exact first crossing below the target, using event times rather than the reporting grid;
- split-half absolute difference at `H*`;
- split-half full-curve supremum difference.

Run:

```bash
python sigma_curve_diagnostics.py
```

Expected marker:

```text
PHASE1_SIGMA_CURVE_DIAGNOSTICS_PASS
```

Output:

`results/development_atlas/sigma_plots/sigma_curve_resolution_diagnostics.csv`

These quantities diagnose whether the Monte Carlo staircase is sufficiently resolved for discovery or later confirmation. They must not be used to smooth the white-box curve.

The PNGs and diagnostic CSVs are generated results and remain ignored by Git.

## Relation to scientific discovery and confirmation

The development atlas remains non-scientific. The scientific workflow uses the same semantics but a separately frozen configuration:

- **N=10 discovery:** search physical candidates and many offline A regions; retain promising white boxes.
- **Freeze finalists:** write exact `(Dbar, delta, l_max, c_max, q_min)` cases to `selected_whiteboxes.json` with status `FROZEN_FOR_CONFIRMATION`.
- **N=100 confirmation:** rerun only those exact cases with fresh seeds, disjoint from the discovery seed bank, and evaluate the same frozen A. Do **not** recalibrate A on the N=100 confirmation data.
- **Later precision:** increase N only if required after confirmation; do not reopen the selected physical parameters or A.

## Simulator-independent tests

```bash
python test_atlas_analysis.py
python test_whitebox_atlas_configuration.py
python test_generate_sigma_plots.py
python test_sigma_curve_diagnostics.py
```

Expected:

```text
PHASE1_ATLAS_ANALYSIS_TESTS_PASS
PHASE1_WHITEBOX_ATLAS_CONFIGURATION_TESTS_PASS
PHASE1_SIGMA_PLOT_TESTS_PASS
PHASE1_SIGMA_CURVE_DIAGNOSTIC_TESTS_PASS
```

`test_generate_sigma_plots.py` requires an empirical sigma drop at the exact synthetic violation time, rather than at a reporting-grid boundary. `test_sigma_curve_diagnostics.py` additionally checks the primary cumulative no-violation semantics, exact target crossing and finite-N jump resolution.

## Minimal native integration check

Run one physical setting and two trajectories first:

```bash
python whitebox_atlas.py --clean --max-physical-settings 1 --max-trajectories-per-setting 2
```

If that passes, execute the full development atlas (`9 x 10` trajectories):

```bash
python whitebox_atlas.py --clean
```

Then generate the exact-event PNGs and resolution diagnostics without rerunning the simulator:

```bash
python generate_sigma_plots.py
python sigma_curve_diagnostics.py
```

The full run remains a development atlas. Do not treat it as the final selected-whitebox confirmation run.
