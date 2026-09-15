# PRAISE first science - Phase 3 / (I1,M1) implementation candidate

**Status: implementation candidate, not frozen.**

M1 uses exactly the frozen public rho-conditioned I1 cards already supplied to M0. The provider lift must be completed and inspected using public I1 reconstruction only before graph-level white-box evaluation is allowed.

## Files

- `config_phase3_m1_contract_v1.json`: explicit M1 information firewall, pilot closure conventions, two-stage lifting contract, optimization budgets, and beyond-pilot diversity note.
- `m1_surrogate_lift.py`: simulator-independent median-target inference, censored Stage-1 loss, full-surface Stage-2 loss, and generic grid-search wrappers.
- `m1_single_provider_simulator.py`: native AICon/YAFS single-provider FCFS surrogate used by both lift stages.
- `run_m1_provider_lift.py`: executable public-I1-to-surrogate calibration pipeline.
- `test_m1_surrogate_lift.py`: simulator-independent regression tests.
- `test_m1_single_provider_simulator.py`: native AICon/YAFS smoke test.

## Pilot surrogate

For the current Q-degenerate pilot, the lifted provider surrogate is

`theta_i^M1 = (mu_i, kappa_i, CV_i)`

with the following fixed inputs/conventions:

- `W_i` comes from the public I1 workload contract and actively drives arrivals;
- one native FCFS provider module;
- canonical `IPT0=1e6` as a numerical gauge only;
- a dedicated workload-injector node is connected to the provider by a zero-delay native link (`PR=0`, request `bytes=0`), because AICon permits only one application module per device; therefore local latency still excludes networking;
- `x=0.5` and `LinearQoS(0,1)`, because the current public cards expose only `Q=0.5`;
- nominal instructions are `mu_i * IPT0 / x`;
- local cost is native `COST(node) * service`.

The current public `W_i` exposes a period but no separate arrival-phase parameter. M1 therefore uses the canonical YAFS periodic-source convention: first local arrival one period after accounting origin, followed by integer multiples of the period.

## Stage 1: deterministic nominal lift

Set service CV to zero and fit only `(mu_i,kappa_i)`.

At fixed `A_i(rho_region)` and `H`, the public map

`rho_query -> sigma_i(A_i,H;rho_query)`

is treated as a sampled survival function of the stochastic cumulative compliance fraction. Its 0.5 crossing supplies the deterministic central target. Bracketed crossings use linear interpolation. If the crossing lies outside the exposed query-rho support, the target is retained as a one-sided censored constraint.

The Stage-1 loss is uniform mean squared point/hinge loss over all public regions and `H>0`.

## Stage 2: stochastic variability lift

Keep Stage-1 `mu_i` and `kappa_i` fixed. Introduce Gamma service demand with one free coefficient of variation `CV_i` and fit that single parameter to the complete public I1 sigma surface over all public regions, query-rho values, and `H>0`.

No joint re-optimization of `mu_i` or `kappa_i` is permitted in this M1 revision.

## Run order

From `first_science/phase3`:

```bash
python test_m1_surrogate_lift.py
python test_m1_single_provider_simulator.py
```

Then run a tiny implementation smoke test on one real public card:

```bash
python run_m1_provider_lift.py --stage stage1 --provider ProviderA --smoke
```

If that passes and the generated Stage-1 artifacts look sensible, run the full Stage-1 lift:

```bash
python run_m1_provider_lift.py --stage stage1
```

Only after Stage 1 has been inspected should Stage 2 be launched:

```bash
python run_m1_provider_lift.py --stage stage2
```

The full Stage-2 run is intentionally more expensive because every CV candidate requires a Monte Carlo local sigma surface. Use `--smoke` first when validating runtime wiring.

## Output

Default output root:

`first_science/phase3/results/m1_provider_lift_v1/`

Each provider receives:

- `median_compliance_targets.csv`;
- `stage1_search.csv`;
- `stage1_best.json`;
- `stage1_best_compliance.csv`;
- `stage1_best_loss_detail.csv`;
- after Stage 2, `stage2_search.csv`, `stage2_best.json`, `stage2_best_sigma_surface.csv`, and `stage2_best_comparison.csv`.

The root `m1_provider_lift_manifest.json` records input hashes, local fit results, the active source commit when available, and explicitly records `graph_level_whitebox_used=false`.

## Freeze gate

Do not freeze M1 merely because an optimizer returns a numerical minimum. At minimum:

1. simulator-independent tests pass;
2. native single-provider smoke test passes;
3. no final optimum is trapped on an undeclared search boundary;
4. local reconstruction is inspected for all three providers;
5. any escalation of surrogate flexibility is motivated only by public-I1 reconstruction, never by graph-level white-box error.

Only after that gate should the lifted surrogates be composed in G and compared with M0 and the frozen white-box reference.

## Beyond the pilot

The fixed `Q=0.5` adapter is intentionally pilot-specific. The next benchmark should introduce non-degenerate quality through a native quality/resource trade-off, for example a varying execution fraction `x`, so quality, executed work, latency, and cost are coupled. Then `q_i(rho_region)` may vary and M1 must lift QoS-generating parameters rather than fixing them.

Later experiments should also vary `W_i` and graph structure. A surrogate identified under one public workload contract is not automatically assumed valid under a different workload induced by another composition topology.
