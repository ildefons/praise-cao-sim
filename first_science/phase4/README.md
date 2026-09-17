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

These bands are diagnostic only. After inspecting **only these local-I1 outputs**, freeze one compatibility rule and then re-evaluate the selected diverse candidates on a common 100-trajectory local confirmation bank. Only after that candidate set is frozen should M2 graph composition begin.
