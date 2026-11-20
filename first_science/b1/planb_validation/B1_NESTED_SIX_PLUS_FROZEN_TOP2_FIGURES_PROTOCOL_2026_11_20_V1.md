# B1: combine nested six-policy curves with all three frozen Top2 variants

## What changes

Figures compare nine policies on the same thirteen budget checkpoints.

- **Nested**: Random, Balanced, Informed, joint KG, two-stage adaptive KG,
  and two-stage uniform KG. Each policy/start/replicate has a single 80-step
  history; smaller-budget outcomes are prefixes.
- **Budget-specific**: joint Top2, two-stage adaptive Top2, and two-stage
  uniform Top2. Their acquisition rules depend on total B, so their existing
  per-budget episodes are reused unchanged. **These are not nested**.

This is a plotting/data-integration step only: no new policy episodes,
bootstrap runs, or white-box simulations. The code checks archived manifest
hashes, policy/budget coverage, episode counts, confidence intervals, and
the recorded B0001 source-to-export matrix provenance.

It creates two main figures (historical and fresh reference) with nine series,
95% archive-conditional bootstrap intervals, and visibly different line
styles for joint, adaptive, and uniform acquisition. The default vertical
range is 0--0.025 historically and 0--0.012 for the fresh reference; if an
upper uncertainty bound would be clipped, the range expands automatically.

## 1. Pull and test on your laptop

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/test_plot_b1_nested_with_frozen_top2_v1.py -v
```

## 2. Original Top2 summaries are already tracked

The existing repository contains the original complete nine-policy CSVs at
`first_science/b1/planb_validation/results/b1_nine_policy_13_budget_extension_v1/tables/`:

- `historical_nine_policy_13_budget_regret.csv`
- `b0001_nine_policy_13_budget_regret.csv`

The matching `plot_manifest.json` lives one directory higher, at the archive
root. Its CSV hashes match the tracked table files. The plotting script now
knows this directory layout automatically. No `rg`, `find`, extra paths,
copying, or episode reruns are needed.

## 3. Preflight (no files written)

```bash
python first_science/b1/planb_validation/plot_b1_nested_with_frozen_top2_v1.py \
  --nested-dir ~/praise/planb_b1_nested_budget_2026_11_20_v1 \
  --preflight-only
```

Expected final line:

`TOP2_OVERLAY_PREFLIGHT_PASS no outputs written`

Both archives must report 78 nested rows plus 39 Top2 rows (117 total per
archive). The B0001 frozen *input* matrix SHA begins `0354739d`, while the
baseline's exported matrix used by nested replay begins `5c81f50a`; the
original B0001 baseline manifest records this exact source-to-export link.

## 4. Render the two updated figure candidates

```bash
python first_science/b1/planb_validation/plot_b1_nested_with_frozen_top2_v1.py \
  --nested-dir ~/praise/planb_b1_nested_budget_2026_11_20_v1 \
  --out ~/praise/planb_b1_nested6_plus_top2_figures_2026_11_20_v1
```

The output directory must **not** already exist. Expect
`B1_NESTED6_FROZEN_TOP2_FIGURES_PASS`.

View the historical and fresh plots locally:

```bash
xdg-open ~/praise/planb_b1_nested6_plus_top2_figures_2026_11_20_v1/historical_nested6_plus_top2_13_budgets.png
xdg-open ~/praise/planb_b1_nested6_plus_top2_figures_2026_11_20_v1/fresh_reference_nested6_plus_top2_13_budgets.png
```

Each image also has PDF and SVG versions. The output includes
`combined_nine_policy_budget_summary.csv` (234 rows, with a `source_design`
field) and `plot_manifest.json` with input/output hashes.

## 5. Return for interpretation

Please share the two PNGs, `combined_nine_policy_budget_summary.csv`, and
`plot_manifest.json`. We will compare the curves, review the role of
budget-dependent Top2 scheduling, and only then decide whether to replace
Figures 3 and 4 in the paper. The LaTeX paper and frozen evidence remain
unchanged by this script.

The old 13-budget Top2 summary's bootstrap confidence intervals are reused
as reported. We do **not** report an inferential paired contrast between
Top2 and the new nested KG episodes merely from overlaying their marginal
curves: their random trajectories were generated under different designs.
