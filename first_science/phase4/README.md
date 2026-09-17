# Phase 4: I1-M2 pilot

M2 starts from the frozen public I1 and frozen M1-v2 evidence. It is a new integration method, not an M1 repair.

## M2-A first step: inspect the existing inverse landscape

Do **not** rerun Optuna yet. The first diagnostic reuses all existing non-smoke M1-v2 search trials and asks whether near-equivalent public-I1 fits already occupy substantially different locations in `(mu,kappa,CV)` space.

From `first_science/phase4` run:

```bash
python m2_a_prepare_candidate_landscape.py
```

For empirical timing/memory accounting, preferred scientific invocation is:

```bash
mkdir -p results/m2_a_landscape_v1
/usr/bin/time -v python m2_a_prepare_candidate_landscape.py \
  2>&1 | tee results/m2_a_landscape_v1/run.log
```

The script reads only:

- frozen public I1 metadata;
- existing `phase3/results/**/m1_v2_search_trials.csv` tables with at least 100 completed trials;
- the base M1-v2 search contract for Providers A/B;
- the declared expanded ProviderC contract for normalization.

It does not run Optuna, does not simulate the graph, and does not read graph white-box outcomes.

Outputs:

- `m2_a_all_candidates.csv`
- `m2_a_loss_band_summary.csv`
- `m2_a_diverse_candidate_preview.csv`
- `m2_a_landscape_manifest_v1.json`

The exploratory loss bands are 1.05x, 1.10x, 1.25x, 1.50x and 2.00x the best observed local search MSE. Within each band the preview anchors on the best-loss point and then uses greedy farthest-point sampling in normalized `(log mu, log kappa, CV)` coordinates.

## M2-A second step: freeze and confirm a local compatibility rule

The inspected landscape supports a single uniform public-I1-only screening rule:

- keep candidates with search MSE <= `1.25 x` the best observed search MSE for that provider;
- include the frozen M1-v2 provider surrogate as the anchor;
- greedily add the two candidates that maximize minimum Euclidean distance in normalized `(log mu, log kappa, CV)` coordinates;
- re-evaluate those three candidates per provider on the common local confirmation bank `23000..23099`;
- call a candidate confirmation-compatible when its confirmation MSE is <= `1.25 x` the best confirmation MSE among the three screened candidates for that provider;
- require at least two compatible candidates per provider before any graph composition;
- replay the confirmed set on `24000..24099` for diagnostics only. Replay cannot alter the compatibility set.

This rule is frozen before graph composition and was chosen using only the local-I1 landscape. The uniform 1.25x screening ceiling is the first inspected predefined band containing at least three candidates for every provider.

Run:

```bash
mkdir -p results/m2_a_confirmation_v1
/usr/bin/time -v python m2_a_confirm_candidates.py \
  2>&1 | tee results/m2_a_confirmation_v1/run.log
```

Expected outputs include:

- `m2_a_screen_candidates.csv`
- `m2_a_confirmation_results.csv`
- `m2_a_confirmed_compatible_candidates.csv`
- `m2_a_replay_results.csv` when the gate passes
- `m2_a_confirmation_manifest_v1.json`
- per-candidate confirmation/replay sigma surfaces and comparisons

The confirmation stage does not run Optuna, does not simulate the graph, does not read graph predictions, and does not read graph white-box outcomes.

The first completed confirmation produced 3 compatible candidates for ProviderA, 3 for ProviderB, and 2 for ProviderC. ProviderC ALT2 failed the frozen confirmation rule and is excluded from graph composition.

## M2-B: one-at-a-time graph identifiability diagnostic

The next stage freezes the confirmed M2-A set before any new graph prediction. It first asks how much graph-level sigma changes when one provider at a time is replaced by a different locally public-I1-compatible surrogate.

The graph variants are:

- `BASE_M1`: all three frozen M1 anchors;
- one variant for each confirmed non-M1 ProviderA candidate;
- one variant for each confirmed non-M1 ProviderB candidate;
- one variant for each confirmed non-M1 ProviderC candidate.

With the current confirmed set this gives six graph variants total: one baseline plus five one-at-a-time substitutions. Every variant uses the independent common graph seed bank `26000..26099`. This bank is separate from the earlier Phase-3 `25000..25099` graph run.

No graph white-box outcome is read in this stage. The outputs quantify spread relative to `BASE_M1` using whole-surface and per-rho MAE/RMSE, signed delta, maximum absolute delta, and request-level latency/cost summaries. No binary materiality threshold is introduced after seeing the result.

Run a smoke test first:

```bash
mkdir -p results/m2_b_one_at_a_time_graph_v1_smoke
/usr/bin/time -v python m2_b_one_at_a_time_graph.py \
  --smoke \
  --output results/m2_b_one_at_a_time_graph_v1_smoke \
  2>&1 | tee results/m2_b_one_at_a_time_graph_v1_smoke/run.log
```

If the smoke test passes, run the scientific diagnostic:

```bash
mkdir -p results/m2_b_one_at_a_time_graph_v1
/usr/bin/time -v python m2_b_one_at_a_time_graph.py \
  2>&1 | tee results/m2_b_one_at_a_time_graph_v1/run.log
```

Expected outputs include:

- `m2_b_variant_design.csv`
- `m2_b_frozen_candidate_set.csv`
- `m2_b_graph_sigma_curves.csv`
- `m2_b_surface_spread_summary.csv`
- `m2_b_per_rho_spread_summary.csv`
- `m2_b_graph_sigma_deltas_vs_base.csv`
- `m2_b_request_distribution_summary.csv`
- `m2_b_graph_diagnostic_manifest_v1.json`
- one combined graph ledger per variant under `ledgers/`

Interpretation comes only after these prediction artifacts are materialized. If locally compatible one-at-a-time substitutions produce substantial graph-sigma spread, the next M2 step is an ambiguity-preserving ensemble or factorial composition design. If the graph predictions remain essentially the same and saturated, the evidence instead points toward insufficiency of the current Gamma/FCFS latent family.
