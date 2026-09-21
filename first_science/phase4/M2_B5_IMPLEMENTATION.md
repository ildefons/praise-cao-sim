# M2-B5 joint ensemble graph propagation

**Status:** implementation ready, execution not yet performed.  
**Date:** 21 September 2026.

## Scientific role

M2-B5 completes the frozen M2 semantics without changing I1 or the already-confirmed M2-A4 provider portfolios.

For each provider, the frozen A4 portfolio contains exactly three independently confirmed and deliberately diverse I1-compatible surrogates. B5 enumerates the complete Cartesian product:

```
P_G = P_A x P_B x P_C
```

giving exactly 27 M2 joint graph hypotheses.

`BASE_M1` is simulated on the same graph seed bank as a paired reference, but it is **not** an M2 ensemble member.

## Frozen outputs

For every `(H,rho)`, B5 computes the 27 member predictions and reports:

```
sigma_M2_mean = (1/27) sum_m sigma_G^(m)
sigma_M2_min  = min_m sigma_G^(m)
sigma_M2_max  = max_m sigma_G^(m)
```

The mean is an equal-weight ensemble central estimate. The min-max interval is a finite-portfolio ambiguity range. It is not a confidence interval and is not claimed to be a global bound over every possible I1-compatible latent model.

Secondary descriptive quantities are population SD, median, q25, q75, and pointwise argmin/argmax member IDs.

## Frozen execution design

- M2 members: 27.
- Paired M1 reference: 1.
- Total graph variants: 28.
- Fresh graph seed bank: `29000..29099`.
- Full trajectories per variant: 100.
- M2 graph trajectories: 2700.
- M1 paired-reference trajectories: 100.
- Total full graph trajectories: 2800.
- Common random numbers are used across all 28 variants.
- Same public-I1-induced `A_G` is used for all variants at each rho.
- Same-rho diagonal is retained.
- No graph white-box data is read.
- No provider search, fitting, GP acquisition, candidate replacement, or retuning occurs.
- `D_A` / Jaccard is N/A in this same-region experiment.

Authoritative contracts:

```
config_phase4_m2_joint_ensemble_semantics_v1.json
config_phase4_m2_b5_joint_ensemble_graph_v1.json
```

Implementation:

```
m2_b5_joint_ensemble_graph.py
```

## Recommended execution order

From the repository root, first update the branch without touching unrelated local work.

### 1. Prepare-only validation

```bash
python first_science/phase4/m2_b5_joint_ensemble_graph.py --prepare-only
```

This validates the frozen contracts and candidate IDs, enumerates the complete 27-member design, and writes the design/candidate files without running graph simulation.

Expected terminal marker:

```
M2_B5_PREPARE_ONLY_COMPLETE
```

### 2. Smoke run

```bash
python first_science/phase4/m2_b5_joint_ensemble_graph.py --smoke
```

The smoke run uses the first 5 seeds and writes to a separate smoke directory. Smoke outputs are implementation checks only and are not scientific evidence.

Expected terminal marker:

```
M2_B5_JOINT_ENSEMBLE_GRAPH_COMPLETE
```

### 3. Full run

Prefer external resource accounting as well as the internal cost manifest:

```bash
/usr/bin/time -v python first_science/phase4/m2_b5_joint_ensemble_graph.py \
  2>&1 | tee m2_b5_joint_ensemble_graph_full.log
```

The runner checkpoints one ledger per variant. If interrupted, rerun the identical command. Completed variant ledgers are validated and reused.

## Full-run output directory

```
first_science/phase4/results/m2_b5_joint_ensemble_graph_v1/
```

Required outputs:

```
m2_b5_joint_variant_design.csv
m2_b5_frozen_candidate_set.csv
m2_b5_joint_graph_sigma_curves.csv
m2_b5_ensemble_curve.csv
m2_b5_request_distribution_summary.csv
m2_b5_cost_manifest_v1.json
m2_b5_manifest_v1.json
ledgers/<variant_id>.csv
```

The primary file for the new M2 prediction is:

```
m2_b5_ensemble_curve.csv
```

with the equal-weight mean, min-max ambiguity range, descriptive portfolio statistics, the paired same-seed M1 curve, and the pointwise extremal member IDs.

## Firewall / evaluation order

B5 is prediction-only. It must not open Phase-1 graph white-box evidence.

After a successful full run, inspect only internal consistency and freeze the B5 hashes. White-box comparison belongs to a separate B6 external-evaluation stage.

Because G0 white-box behavior has already been inspected during development, any later B6 comparison on G0 is retrospective diagnostic evidence. Prospective validation of the frozen M2 method requires an untouched predeclared condition.
