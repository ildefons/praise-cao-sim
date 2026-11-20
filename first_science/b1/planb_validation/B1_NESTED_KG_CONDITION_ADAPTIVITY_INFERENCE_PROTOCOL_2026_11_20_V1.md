# B1: direct check of adaptive vs uniform two-stage KG

## Scientific question

Does selecting the next operating condition by KG improve terminal method
selection compared with selecting that condition uniformly, with the same
two-stage KG first-stage rule and the same Gaussian surrogate?

The two policies use the same initial seven evaluations, posterior model,
first-stage method-selection rule and terminal recommendation. Subsequent
method choices can change when their acquisition histories diverge, so the
comparison estimates the **whole-policy consequence** of the condition rule.

## Design

- Both archives: historical reference and fresh reference, each a fixed 7x12
  condition-loss matrix.
- Both KG policies have one budget-independent, 80-evaluation trajectory
  for each of twelve starting conditions and twenty random replicates.
- Each trajectory is scored at the same thirteen budgets:
  10, 15, 20, 25, 30, 35, 40, 45, 55, 65, 70, 75, 80.
- **Separate bootstrap resampling across policies.** The policies have
  different fixed policy IDs and random streams; their replicate numbers
  are not paired policy outcomes. Starting conditions remain fixed strata.
- **Common bootstrap indices across budget checkpoints within each policy.**
  This preserves the dependence of outcomes that are prefixes of the same
  trajectory.
- The primary result is adaptive minus uniform mean terminal simple regret
  over thirteen equally weighted budget checkpoints. A negative value favors
  adaptive condition selection.
- We also report the seven-checkpoint B=10..40 exploratory sensitivity.
- Nominal two-sided 95% bootstrap intervals are provided for both aggregates
  and each budget. Bonferroni two-sided 97.5% intervals are provided for
  simultaneous 95% coverage of the two archive-specific contrasts in each
  budget set. These do **not** correct for having selected this comparison
  after inspecting earlier curves.
- The uncertainty describes acquisition randomness conditional on the
  two fixed matrices. It does not include white-box reference uncertainty
  or variation across new provider worlds and graphs.

No simulations, policy acquisitions, or new MAE observations are performed.
This is a read-only reanalysis of the existing nested episodes.

## 1. Pull and run tests locally

```bash
cd ~/praise/praise-cao-sim
git pull --ff-only origin praise-identifiability-feasibility

python first_science/b1/planb_validation/test_b1_nested_kg_adaptivity_inference_v1.py -v
```

All six unit tests use synthetic episode records. No original policy replay
is performed in the test suite.

## 2. Input preflight

```bash
python first_science/b1/planb_validation/b1_nested_kg_adaptivity_inference_v1.py \
  --preflight-only
```

Expected final line: `KG_ADAPTIVITY_PREFLIGHT_PASS no outputs written`.

It checks the complete nested episode file, nested summary and their
manifest hashes, both archive identities, the fixed budget design, and
the per-policy means against the original nested summary.

## 3. Bootstrap inference

```bash
python first_science/b1/planb_validation/b1_nested_kg_adaptivity_inference_v1.py \
  --out ~/praise/planb_b1_kg_adaptive_vs_uniform_2026_11_20_v1
```

Expected final line: `KG_ADAPTIVITY_INFERENCE_PASS ...`.
The output directory must not already exist. The default is 10,000
stratified bootstrap draws per archive.

## 4. Files to share

The output directory contains:

1. `kg_condition_adaptivity_aggregate_contrasts.csv` — four rows (two
   archives, primary thirteen-budget average and exploratory B10..40),
   mean regrets for both policies, difference, nominal and familywise 95%
   intervals.
2. `kg_condition_adaptivity_budget_contrasts.csv` — 26 per-budget results
   with nominal intervals.
3. `kg_condition_adaptivity_manifest.json` — checked source hashes,
   resampling assumptions, parameters and output hashes.

Share these three files. We will review the inference before updating
Section 5 (adaptive condition choice), Figure 3/4 interpretation, the
Discussion and Conclusion. Manuscript source and archived trajectories
are unchanged by this step.
