# B1 read-only inference: nested adaptive KG versus frozen Top2

## Question

Does adaptive two-stage KG have lower **mean terminal simple regret** than
each of the three budget-specific Top2 policies, averaged over the 13 budget
checkpoints? We also report a budget-10-to-40 exploratory sensitivity.

The six-policy nested replay, its matrices, nine-policy figure data, and all
original Top2 episode records remain unchanged. This step only resamples
the *existing terminal episode outcomes*.

### Uncertainty design

- There are 12 fixed initial conditions and 20 random replicates per
  policy/condition/budget, all on one fixed 7x12 MAE table per archive.
- KG adaptive: a single 80-step trajectory is observed at every smaller
  budget checkpoint. **The same** bootstrap replicate draws are used across
  all 13 checkpoints of that KG trajectory.
- Top2: the terminal budget enters acquisition, so each B uses a different
  policy history. **Independent** replicate draws are used for each Top2
  policy and terminal budget. KG/Top2 replicate numbers are not artificially
  paired across different policy RNG streams.
- Mean regret differences are computed as **KG adaptive minus Top2**.
  Negative means favor KG adaptive.
- For the average over 13 budgets, compare KG adaptive against *all three*
  Top2 variants using 95% **familywise** Bonferroni intervals (three 98.33%
  two-sided intervals); ordinary 95% intervals are also reported.
- The seven-checkpoint subset B=10..40 is an **exploratory sensitivity**.
  Individual-budget intervals are descriptive nominal 95% intervals, not
  multiplicity-adjusted claims at 13 separate budgets.
- All intervals describe acquisition randomness **conditional on the fixed
  twelve-condition archive**. They do not resample white-box reference worlds.

## 1. Pull the code and run tests on the laptop

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/test_b1_nested_kg_vs_frozen_top2_inference_v1.py -v
```

The tests include a read-only check of both original B0001 five- and
eight-budget ZIPs, which are already **tracked in this repository**.

## 2. Fresh-reference preflight and inference (ready now)

```bash
python first_science/b1/planb_validation/b1_nested_kg_vs_frozen_top2_inference_v1.py \
  --archive fresh_reference \
  --preflight-only
```

Expected final line: `CROSS_DESIGN_PREFLIGHT_PASS no outputs written`.

Then:

```bash
python first_science/b1/planb_validation/b1_nested_kg_vs_frozen_top2_inference_v1.py \
  --archive fresh_reference \
  --out ~/praise/planb_b1_nested_kg_vs_top2_fresh_2026_11_20_v1
```

This reads the locally generated nested terminal episodes and the exact
frozen B0001 episode ZIPs already present in `results/`. It checks all
Top2 per-budget means against the original archived 13-budget figure table.
No policy episodes are rerun.

## 3. Historical extension (once its old control ledger is identified)

The eight additional historical budgets are already present in a tracked
ZIP. The five original historical budgeted-Top2 joint episodes are at
`~/praise/planb_b1_fixed_budget_v1/terminal_episodes.csv`.

The original historical two-stage controls need their frozen
`controlled_terminal_episodes.csv` file. Find its location:

```bash
find ~/praise -type f -name 'controlled_terminal_episodes.csv' -print
```

For the correct file, the SHA-256 must be
`e703db78a1bac4f0cd569c9c56f15f375626a1fb8208905e6018e5bf35f202c1`.
The script checks that automatically. Do not create or rerun the ledger if
the original is absent; share the `find` output and we can locate its archive.

Once identified, replace `/ACTUAL/PATH/controlled_terminal_episodes.csv`
below with the real path:

```bash
python first_science/b1/planb_validation/b1_nested_kg_vs_frozen_top2_inference_v1.py \
  --archive historical \
  --historical-five-controlled /ACTUAL/PATH/controlled_terminal_episodes.csv \
  --preflight-only

python first_science/b1/planb_validation/b1_nested_kg_vs_frozen_top2_inference_v1.py \
  --archive historical \
  --historical-five-controlled /ACTUAL/PATH/controlled_terminal_episodes.csv \
  --out ~/praise/planb_b1_nested_kg_vs_top2_historical_2026_11_20_v1
```

## 4. Outputs to share

- `cross_design_aggregate_contrasts.csv`: difference of means, 95% nominal
  and 95% familywise-adjusted intervals for all three Top2 opponents, over
  13 budgets and the exploratory 10-to-40 subset.
- `cross_design_budget_contrasts.csv`: nominal budget-specific intervals.
- `cross_design_manifest.json`: input hashes, bootstrap parameters, design
  safeguards and output hashes.

For a negative difference with its **familywise upper bound below zero**, we
can support the corresponding conditional acquisition-randomization claim.
If it crosses zero, the result supports competitiveness but not established
superiority at this precision. We will decide wording for the paper after
examining these files together. The manuscript is not edited in this step.
