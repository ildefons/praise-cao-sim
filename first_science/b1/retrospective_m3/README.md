# B1 retrospective original-style M3 generalization

**Status:** executable exploratory protocol; no scientific result is claimed until the user runs all stages and returns the outputs.

The Phase-4 pilot had 48 candidate provider models per provider, KL-Gibbs weights (lambda 30), a Top14 joint-model support and a budget of 1,400 graph trajectories. Phase-5 FULL343 instead used 7 fitted provider models per provider. This experiment checks the original-style **method class** on the 12 existing Phase-5 eligible cases. It is **not a bit-for-bit replay** of Phase-4 candidate parameters: the new provider configurations require new public-I1-specific candidate reconstruction, using the frozen Phase-5 V2 LHS design and search domains.

## Scientific design

1. Reconstruct 48 candidates per provider using the original declared nonadaptive LHS design, the frozen public I1 cards and independent 100-run local rescore bank. Do not use hidden provider parameters or graph white-box outcomes.
2. Use Jeffreys-smoothed Bernoulli KL and lambda=30 to calculate product weights over all 48^3 joint combinations. Choose descending Top14 and store their retained mass. Use the historical integer greedy minimax allocation at B=1400.
3. For each existing Step-0 eligible graph, reuse the same 15 SLA conditions, 49 prediction horizons (evaluation at 37 horizons H=60..240), and native Phase-5 simulator. Evaluate a B1400 Top14 estimator and a separately simulated, budget-matched B1400 Top1 estimator.
4. **Only after freezing all 12 cells**, evaluate those two predictions against the existing Phase-5 final WB and compare with frozen V3b FULL343. Preserve all previous Phase-5 files.

The output is **retrospective**. Even if the new predictions are generated without accessing white-box outcomes during the run, the design was proposed after inspection of the Phase-5 results. It must not be promoted to independent confirmation. The comparison matches graph trajectories, not total candidate-search expense. It also combines differences in candidate generation, support selection and weighting: it is not a causal isolation of a single mechanism.

## Local workflow

In the existing praise-cao Python environment from the repository root:

    cd ~/praise/praise-cao-sim
    git switch praise-identifiability-feasibility
    git pull --ff-only origin praise-identifiability-feasibility
    python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage preflight

## Performance and bounded runtime estimates

The original Phase-5 reconstruction stage used `ProcessPoolExecutor` with `--workers 3` or `4`. This runner now parallelizes independent candidate evaluations the same way, using one persistent pool per provider. Each candidate writes its own atomic CSV checkpoint, and all parallel processes use the **same frozen public I1 input, exact candidate parameters and seed bank** as sequential execution. Workers cannot access hidden graph reference data.

**First run a short, resumable benchmark** (3 candidates per provider, 9 total × 100 local simulations). This is the same scientific computation as full preparation, and every valid resulting checkpoint is reused when you continue. It does *not* freeze partial candidate weights:

    time python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage benchmark --world P1 --workers 3

The benchmark prints mean measured seconds per candidate and a rough full-provider estimate. Then execute the full P1 run (48 × 3 = 144 candidate models, each 100 local runs, 14,400 local simulations):

    time python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage prepare --world P1 --workers 3

Preparation streams progress after each 4 newly completed candidates and prints a measured remaining-time estimate. This depends on CPU scheduling and thermal behavior. 3 workers are recommended initially; 4 may improve speed if CPU and memory permit. Parallelization does not guarantee a 3× speedup. The output root is locked per world to prevent another new-style preparation process from using the same directory simultaneously; do not run older runner revisions concurrently either.

Then one graph (Top14 and budget-matched Top1, each using 1,400 native graph trajectories):

Large dominant-rank jobs and the Top1 control are **also subdivided into independent seed blocks** when `--workers 3` is provided. This avoids a single-core tail even though Top1 contains just one joint provider model. The complete canonical ledger is reassembled with original seed IDs and trajectory ordinals, checked for duplicates, and frozen exactly as in serial execution. Each block has its own resumable simulation ledger; do not launch two runners on the same cell at once. The first run performs 2,800 native graph trajectories per cell; over 12 cells that is 33,600 trajectories. **Runtime is not yet calibrated:** use the first P1/G_PAR cell and its progress messages before scheduling the other 11.



    python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage predict --cell P1__G_PAR --workers 3

After examining the smoke-like pilot execution for consistency, run the other worlds:

    python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage prepare --workers 3
    python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage predict --workers 3
    python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage evaluate

**Do not run evaluate until predict has frozen all 12 cases.** The runner checks this. All new results are placed under first_science/phase5/results/b1_pilot_m3_retrospective_v1; original Phase-4/5 results, protocols, the Overleaf report and the public I1 interface are untouched. Large stochastic stages can be resumed using per-candidate curves and per-trajectory checkpoints.

## Returned evidence

Please return the full results/b1_pilot_m3_retrospective_v1 folder as a ZIP, or at minimum:
- candidate_support/{P1,P3,P4}/support_manifest.json and top14_support.csv
- global_prediction_freeze.json
- evaluation/metrics_retrospective.csv and evaluation_manifest.json

We will audit masses, configs, trace hashes, scored populations and errors before modifying the B1 technical report. A separate fresh holdout would be required for confirmatory claims.

## Preconditions and limitations

This runner assumes the already executed Phase-5 environment, including the locally archived Phase-5 I1 public cards, Step-0 queries, M1 domain registry, native YAFS modifications and final-WB tables. These scientific archives are not stored on GitHub. The preflight checks the accessible subset. Run in the existing praise-cao environment. The runner discovers the modified YAFS runtime in the sibling `~/praise/aicon/src/yafs/src` checkout before importing simulator modules and checks for its PRAISE composition API. Alternatively, set `PRAISE_YAFS_SRC=/absolute/path/to/aicon/src/yafs/src` (the directory immediately containing the `yafs` Python package). Do **not** install ordinary upstream `yafs` as a substitute for the modified runtime. Only the source and protocol, not simulation results, were reviewed through the GitHub connector at authoring time.
