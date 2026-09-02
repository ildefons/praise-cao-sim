# Phase 1 development white-box atlas

This development checkpoint asks a deliberately empirical question before any Bayesian optimization:

> Is the two-dimensional physical family `(Dbar, delta)` already rich enough to generate useful white-box survival behaviour and admissibility regions?

The atlas is **not scientific evidence** and does not replace the later N=100 coarse candidate evaluation prescribed by the design document.

## Development physical grid

`config_phase1_atlas_smoke.json` defines three central native gamma instruction means and three symmetric provider dispersions, giving 9 physical settings. Each setting uses the same 10 development seeds.

A/B/C are structurally identical native AICon/YAFS service modules. Every invocation samples a fresh seeded gamma realization through `Message.instructions`; service time, queueing, L, C, and Q are simulator consequences. Fpre and Fpost are deterministic.

## Two-stage execution

1. `whitebox_atlas.py` executes the native composed graph `Fpre -> ParAll(A,B,C) -> Fpost` and writes one top-level ledger row per logical request.
2. `atlas_analysis.py` reuses those ledgers and scans many `A={L<=l,C<=c,Q>=x}` regions offline. Threshold candidates are generated around each trajectory's critical L/C value at `H*=120`, so N=10 exposes the actually achievable 0.1-resolution survival transitions without an arbitrary dense grid.

Outputs include:

- `all_top_level_request_ledgers.csv`
- `physical_settings.csv`
- `admissibility_regions.csv`
- `survival_curves.csv`
- `achievable_sigmas.csv`
- `representative_regions_by_sigma.csv`

The last table gives compact example A regions for each achievable sigma at H=120, including latency-first and cost-first violation counts.

## Sigma-curve plotting post-process

`generate_sigma_plots.py` is a simulator-independent post-process. It reads the existing atlas CSVs and writes one PNG per physical setting into:

`results/development_atlas/sigma_plots/`

For each physical setting it selects the closest achievable anchor-sigma level at or below the target and the closest level at or above the target. With the N=10 development atlas and target `0.95`, these will normally be `0.9` and `1.0`. All representative ARs retained at those selected sigma levels are plotted, so latency-first, cost-first, and mixed representatives are not silently collapsed to one AR.

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

The PNGs and selection CSV are generated results and remain ignored by Git.

## Simulator-independent tests

```bash
python test_atlas_analysis.py
python test_whitebox_atlas_configuration.py
python test_generate_sigma_plots.py
```

Expected:

```text
PHASE1_ATLAS_ANALYSIS_TESTS_PASS
PHASE1_WHITEBOX_ATLAS_CONFIGURATION_TESTS_PASS
PHASE1_SIGMA_PLOT_TESTS_PASS
```

## Minimal native integration check

Run one physical setting and two trajectories first:

```bash
python whitebox_atlas.py --clean --max-physical-settings 1 --max-trajectories-per-setting 2
```

If that passes, execute the full development atlas (`9 x 10` trajectories):

```bash
python whitebox_atlas.py --clean
```

Then generate the PNGs without rerunning the simulator:

```bash
python generate_sigma_plots.py
```

The full run remains a development atlas. Do not use it as the N=100 scientific calibration/search result.
