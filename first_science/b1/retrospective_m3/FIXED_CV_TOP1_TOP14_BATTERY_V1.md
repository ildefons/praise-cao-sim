# B1 fixed-support Top1/Top14 battery, using already-frozen public-I1 CV

This is an **additional retrospective experiment** for Section 8.1 / Table 6,
not a successful run of the original adaptive support method. The original
99.9%-mass policy, its failed feasibility tests and all its frozen files
remain unchanged.

## Scientific design

* Reuse the completed, frozen 48-candidate / 100-local-trajectory provider
  reconstructions in `phase5/results/b1_pilot_m3_policy_transfer_v1`. No
  provider-local simulations are regenerated.
* Reuse the selected public-I1 five-fold CV temperatures without retuning:
  P1 lambda=3, P3 lambda=5 and P4 lambda=5.
* Form the identical 48^3 joint product and sort by its original weights.
* **Fixed Top14:** take precisely the 14 highest-weight joint combinations,
  renormalize weights within this subset and allocate B=1400 with the pilot's
  original integer minimax variance-bound allocation. The retained mass is
  measured and reported, but is **not required** to reach 99.9%.
* **Top1:** the same highest-weight joint combination, propagated separately
  with B=1400 graph trajectories.
* Reuse the Phase-II 12 eligible world-by-graph cases and frozen Step-0 queries.
  Both methods cover 735 grid predictions per cell, including 555 evaluation
  points at horizons 60..240 seconds.
* Graph simulation, seed namespaces, curve aggregation and overall 12-cell
  scoring reuse the existing original-style / Phase-II implementation.
  Top14 and Top1 each have B1400 **per cell** (B2800 together).
* The 12-cell FULL343 V3b comparator is retrieved unchanged, and only at final
  evaluation with the existing Phase-II white-box reference.
* No white-box file is opened before all 12 cells have successfully produced
  immutable predictions and `global_prediction_freeze.json` has been frozen.

This addresses the predictive-accuracy question for a **fixed-support
variant** using the original provider reconstruction and per-world CV.
It does **not** remove the adaptive 99.9%-mass support infeasibility, and does
not make the previously inspected Phase-II battery a fresh holdout.

## Launch (can be long-running)

From the existing `(praise-cao)` environment:

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility
python -m py_compile first_science/b1/retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py

python -u first_science/b1/retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py \
  --stage preflight --workers 4

python -u first_science/b1/retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py \
  --stage prepare --workers 4
```

At this checkpoint, inspect the Top14 retained mass and allocations:

```bash
for w in P1 P3 P4; do
  echo "=== $w ==="
  grep -E 'retained_mass|omitted_mass|selected_lambda|adaptive_k_infeasible' \
    "first_science/phase5/results/b1_fixed_cv_top1_top14_b1400_v1/support/$w/support_manifest.json"
done
```

To launch **all 12 cells followed by global freeze and evaluation**, with
checkpoints and no foreground terminal dependency:

```bash
mkdir -p first_science/b1/local_audit/fixed_cv_top1_top14
LOG="first_science/b1/local_audit/fixed_cv_top1_top14/run.log"
nohup python -u first_science/b1/retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py \
  --stage all --workers 4 > "$LOG" 2>&1 < /dev/null &
echo $! > first_science/b1/local_audit/fixed_cv_top1_top14/run.pid
echo "PID: $(cat first_science/b1/local_audit/fixed_cv_top1_top14/run.pid)"
```

The `all` stage is **resumable**. Each native graph trajectory is checkpointed
with its deterministic seed. Each fully simulated cell is separately frozen.
Reissuing the `all` command reuses already frozen supports, ledgers,
predictions and validated manifests, rather than repeating completed work.
Never start two concurrent instances (an exclusive lock prevents this).

Progress:

```bash
tail -f first_science/b1/local_audit/fixed_cv_top1_top14/run.log
```

To resume after an interruption: run the same `--stage all --workers 4` command.

## Outputs

All results are isolated under:

`first_science/phase5/results/b1_fixed_cv_top1_top14_b1400_v1/`

* `support/P*/top14_support.csv`: selected models and B1400 allocations.
* `support/P*/support_manifest.json`: CV lambda, Top14 retained mass,
  infeasible original adaptive K and input hashes.
* `predictions/P*__G*/top14_predictions.csv` and
  `top1_predictions.csv`: prediction grids, plus native graph ledgers.
* `global_prediction_freeze.json`: required gate for white-box evaluation.
* `evaluation/metrics.csv`: MAE, RMSE and bias for Top14, Top1, and V3b
  FULL343, overall and broken down by cell, provider world and graph.
* `evaluation/pointwise_errors.csv`: all 19,980 aligned scored point pairs.
* `evaluation/evaluation_manifest.json`: scores and freeze hashes.

Before reviewing or copying accuracy results, the run must print:

`B1_FIXED_CV_TOP1_TOP14_STAGE_ALL_PASS`

Do not modify the original adaptive-support freeze or silently relabel
these fixed-support results as the original 99.9%-mass method.
