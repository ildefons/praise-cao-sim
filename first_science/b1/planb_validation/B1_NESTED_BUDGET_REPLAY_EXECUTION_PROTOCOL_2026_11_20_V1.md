# B1 nested-budget replay: local execution protocol

## Purpose

For six *budget-independent* acquisition policies, the experiment now draws
**one 80-evaluation trajectory** per starting condition and replicate, then
evaluates the terminal decision using the first 10, 15, 20, 25, 30, 35, 40,
45, 55, 65, 70, 75, and 80 evaluations of that **same history**. Therefore,
the selected actions at B=20 are exactly the first 20 selected at B=80 (for
the same archive, policy, starting condition, and replicate).

The six policies are:

1. `random`
2. `balanced`
3. `informed`
4. `kg_one_step` (joint-action KG)
5. `kg_two_stage_adaptive` (KG algorithm choice, KG condition choice)
6. `kg_two_stage_uniform` (KG algorithm choice, uniform condition choice)

The three Top2 variants (`budgeted_top2`, `top2_two_stage_adaptive`,
`top2_two_stage_uniform`) **cannot** use a single cross-budget trajectory:
their coverage/exploitation scheduling depends explicitly on the committed B.
Their previously archived budget-specific curves remain valid comparators.
Do not concatenate their individual trajectories across budgets or label them
as nested. For the six budget-independent policies the acquisition functions
are imported unchanged; Balanced reuses the already documented full-catalogue
compatibility fix needed close to B=80.

Random streams are keyed by `(seed, starting condition, replicate, policy,
stream)`. Neither **budget** nor **archive label** is a seed component.
The two-stage policies retain independent arm-choice and condition-choice
random streams. No fresh physical simulations or new outcomes are generated.

## From the repository root, on the laptop

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/test_b1_nested_budget_replay_v1.py -v

python first_science/b1/planb_validation/b1_nested_budget_replay_v1.py \
  --historical-matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --fresh-reference-matrix first_science/b1/planb_validation/results/b0001_original_policies_v1/01_baseline/seven_method_matrix.csv \
  --preflight-only
```

The preflight must finish with `NESTED_PREFLIGHT_PASS no outputs written`.
If the fresh-reference CSV is stored at another location, supply that path;
both matrices must match their known archived checksums and include all 84
method/condition observations.

When the tests and preflight pass, run:

```bash
python first_science/b1/planb_validation/b1_nested_budget_replay_v1.py \
  --historical-matrix ~/praise/planb_b1_fixed_budget_v1/seven_method_matrix.csv \
  --fresh-reference-matrix first_science/b1/planb_validation/results/b0001_original_policies_v1/01_baseline/seven_method_matrix.csv \
  --out ~/praise/planb_b1_nested_budget_2026_11_20_v1
```

The output directory **must not already exist**: the replay refuses to
overwrite a prior run. Run locally; do not commit experimental data to GitHub.
The script should print `NESTED_TRAJECTORIES_OK` for each of 2 archives × 6
policies and finish with `B1_NESTED_REPLAY_PASS`.

## Expected outputs

| File | Contents |
| --- | --- |
| `nested_terminal_episodes.csv` | 37,440 rows: 2 archives × 6 policies × 12 starts × 20 repeats × 13 checkpoints. |
| `nested_action_history.csv` | 230,400 rows: one 80-step history per archive/policy/start/replicate, **not** thirteen repeated histories. |
| `nested_budget_summary.csv` | Mean regret, 95% stratified bootstrap intervals, and correct-recommendation rates for each archive/policy/budget. |
| `nested_paired_contrasts.csv` | Contrasts among the six nested policies at each budget and equal-weighted across all 13 budgets. |
| `nested_manifest.json` | Input/source hashes, policy and budget definitions, output hashes, RNG convention, run sizes. |

The bootstrap resamples the 20 stochastic replicates within each fixed
starting condition. It uses matched `(start, replicate)` indices when
comparing policies, and a *common* bootstrap draw across budgets for the
mean-over-budgets contrasts; this respects the nested trajectories.

### What to return for our paper review

Share `nested_budget_summary.csv`, `nested_paired_contrasts.csv`, and
`nested_manifest.json` first. Keep `nested_terminal_episodes.csv` and
`nested_action_history.csv` locally for reproducibility and diagnostics.

We will compare the six nested curves to the **unchanged** original Top2
budget-specific curves. These original Top2 results are not directly paired
with the new nested RNG streams, even if their starting conditions and
replicate numbers match. Their marginal budgetwise estimates can still be
compared, with appropriately stated uncertainty.

## Interpretation boundaries

- A growing budget gives a *nested information set* but does **not** guarantee
  realized simple regret decreases at every checkpoint. A posterior decision
  can change after a new observation.
- The evaluation matrices are finite frozen retrospective/reference data;
  bootstrap variability here is primarily acquisition randomness conditional
  on each fixed matrix, not uncertainty over a population of worlds.
- No policy is optimized or modified based on the outcomes of this replay.
- Do **not** revise paper figures, results, or claims before reviewing the
  new paired summaries together. The previously frozen evidence is preserved.
