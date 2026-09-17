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

Only after `M2_A_LOCAL_CONFIRMATION_PASS` should the M2 graph-identifiability experiment be specified. The graph stage should first vary locally compatible providers in a predeclared way, preferably including one-at-a-time substitutions against the frozen M1 combination before any larger factorial or sampled ensemble experiment.
