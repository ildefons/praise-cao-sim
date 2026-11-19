# B0001 — exact original B1 selection-policy replay

**Frozen evidence, 19 November 2026.** This archive holds the results of running
the *original* four-policy, one-step-KG, controlled-two-stage, and plotting code
against the independently audited B0001 seven-method accuracy matrix.

## Strict distinction from the historical B1 archive

- B0001 inputs: 7 methods × 12 conditions, derived from the independent final
  white-box reference. Seven predictions, physical reference, and scoring remain
  frozen. The original B0001 matrix SHA-256 is
  `0354739d64038da538485b5364b37ad8a69181ca5957dbff92aaec349be2523b`.
- The original B1 policy scripts and plotting script were run *unchanged*. Only
  old expected-input SHA-256 constants were rebound **in memory** to the B0001
  files. The source files in the repository were not changed.
- The original scripts' manifests and figure footnotes retain certain historic
  wording (such as "original archive", "development" and "historical"). Those
  strings are inherited from the unchanged original code and do not mean that
  the numerical results come from the old B1 matrix.
- This is an independent **reference evaluation of the same twelve physical
  conditions**, not validation on new provider-world configurations.

## Original scripts and SHA-256

| Relative path under `first_science/b1/planb_validation/` | Source SHA-256 |
|---|---|
| `b1_budget_comparison_v1.py` | `11c36f80a6fb0faf2a325a590f29ff48b3f08dc80a34a4ba606e0bc268aac2ac` |
| `b1_kg_one_step_v1.py` | `cd79f4b3c87445cdd020d8b8bbd441432f9ccba5960de34ec5bbf4464d68fb94` |
| `b1_condition_selection_controlled_v1.py` | `78633ab2ff993f967446add90b3efa0d836adf908c5c278d5c82e1efb1dbe39d` |
| `plot_b1_condition_selection_controlled_v1.py` | `523b6f11ca5666cc5ede333ca7a0ed1ede073748b771772d1c898c04a1dc0843` |

Budgets: 10, 15, 20, 30, 40. Each policy/budget: 12 starting cells × 20
repetitions = 240 episodes. Across all nine policies: 10,800 terminal
decisions, 248,400 distinct observation actions. Original stratified episode
bootstrap: 2,000 repetitions per comparison. Seed 20261105.

## Archive structure

- `01_baseline/`: original Random, Balanced, Informed, Budgeted Top-2; all
  terminal decisions and action histories; paired contrasts; output hashes.
- `02_kg/`: original joint-action one-step Knowledge Gradient; decisions,
  histories, and paired contrasts; output hashes.
- `03_controlled/`: the original matched adaptive/uniform two-stage KG and
  Top-2 policies; decisions, histories, and paired contrasts; output hashes.
- `04_figures/`: original renderer's seven-policy and nine-policy plots in
  PNG/SVG, plotted curve CSVs, and hash manifest.

Each component manifest records SHA-256 for its own outputs. The baseline
manifest ties the replay back to B0001's original input matrix SHA-256.

## Scientific scope

This freezes the primary **conditional-on-B0001** policy replay. Its CIs
resample selection episodes, not white-box trajectories or provider-world
parameters. The independent 10,000-draw white-box trajectory bootstrap is
separate evidence. Any reference-sensitivity or leave-one-condition-out study
must be labeled *diagnostic* and cannot silently replace this 12-condition
selection-policy evaluation.
