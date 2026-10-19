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

First run one provider world (resumable):

    python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage prepare --world P1

Then one graph (simulated twice, Top14 and budget-matched Top1):

    python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage predict --cell P1__G_PAR --workers 3

After examining the smoke-like pilot execution for consistency, run the other worlds:

    python first_science/b1/retrospective_m3/run_pilot_m3_generalization_v1.py --stage prepare
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
