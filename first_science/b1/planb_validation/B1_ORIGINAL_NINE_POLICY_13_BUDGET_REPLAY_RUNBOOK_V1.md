# B1: extend the original nine validation-policy curves through budget 80

## Scope

The *same* B1 nine policies, Gaussian posterior, recommendation rule, initial
observations, seed (20261105), 20 replicates per initial cell, and 2,000-draw
stratified bootstrap are used for both accuracy matrices. All physical
reference data and predictors are already frozen. **No new simulations**.

Full budget grid: `10,15,20,25,30,35,40,45,55,65,70,75,80`.

- The original `10,15,20,30,40` policy summaries are read directly from their
  archived CSVs and are never rerun or overwritten.
- Only `25,35,45,55,65,70,75,80` episodes are generated, using the original
  episode/selector implementations from:
  `b1_budget_comparison_v1.py`, `b1_kg_one_step_v1.py`, and
  `b1_condition_selection_controlled_v1.py`.
- One necessary edge-case compatibility fix applies to **balanced** at budget
  80: the original function sizes its scratch array by the largest algorithm
  index still *available*, although it then indexes algorithms already
  *observed*. When the seventh algorithm's 12 observations are exhausted,
  this would raise `IndexError`. The extension allocates the correct seven
  rows and keeps **identical original balance weights and tie-breaking**.
  In states where all seven algorithms still have available observations,
  the original function is called verbatim.
- The original KG bootstrap hardcodes 1,200 episodes (five budgets). The
  extension generalizes the budget count while retaining identical RNG,
  bootstrapping and paired-contrast formulas; the five-budget case has been
  regression-tested against its previously frozen outputs.
- The B0001 matrix represents an independently simulated reference; the
  historical matrix is development evidence. Bootstrap intervals here are
  conditional on each frozen seven-by-twelve accuracy matrix, **not** a new
  physical-reference uncertainty interval.

## Matrix identity

| Archive | `seven_method_matrix.csv` SHA-256 |
| --- | --- |
| Historical | `0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d` |
| B0001 | `0354739d64038da538485b5364b37ad8a69181ca5957dbff92aaec349be2523b` |

Both commands refuse to run against any other matrix. Set the two `--matrix`
paths to where those exact files live on your machine.

## Replay commands (from repository root)

```bash
python first_science/b1/planb_validation/test_extend_b1_original_nine_policy_budgets_v1.py -v

python first_science/b1/planb_validation/extend_b1_original_nine_policy_budgets_v1.py \
  --dataset historical \
  --matrix /path/to/historical/seven_method_matrix.csv \
  --out /path/to/output/13_budget_historical_extra

python first_science/b1/planb_validation/extend_b1_original_nine_policy_budgets_v1.py \
  --dataset b0001 \
  --matrix /path/to/b0001/seven_method_matrix.csv \
  --out /path/to/output/13_budget_b0001_extra
```

Each extension creates three policy-family subdirectories, with terminal
episode files, full per-action histories, per-budget regret / accuracy
summaries, paired contrasts, and a SHA-256 manifest. Each output path must not
exist before the run. Expect 17,280 *new* episodes (eight budgets × nine
policies × 12 initial cells × 20 replicates) per archive.

## Two plots with exactly the same vertical axis

```bash
python first_science/b1/planb_validation/plot_b1_nine_policies_shared_axis_13budgets_v1.py \
  --historical-frozen first_science/b1/planb_validation/results/controlled_condition_ablation_v1/b1_nine_policy_with_historical_refs_ci_v1.csv \
  --b0001-frozen first_science/b1/planb_validation/results/b0001_original_policies_v1/04_figures/b1_nine_policy_with_historical_refs_ci_v1.csv \
  --historical-extra /path/to/output/13_budget_historical_extra \
  --b0001-extra /path/to/output/13_budget_b0001_extra \
  --out /path/to/output/13_budget_figures
```

Creates historical and B0001 nine-curve plots (PNG, SVG, PDF), a side-by-side
comparison with `sharey=True`, full 13-budget nine-policy CSVs, and an
integrity manifest recording the **identical y-axis minima and maxima**.
The original color/marker/line-style assignments are reused.

## Interpretation guard

Budget 80 observes **80 of the 84** distinct predictor–condition combinations.
Near that budget, many policies may converge as almost the entire matrix is
observed; this is not evidence that their early-budget acquisition decisions
were equally effective. Only the B0001 outcomes can be called independent
replication; the historical outcomes are development evidence.
