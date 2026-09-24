# CAiSE pilot post-hoc mechanism audit

**Date:** 24 September 2026  
**Status:** FROZEN_PROTOCOL_BEFORE_EXECUTION  
**Base scientific checkpoint:** `m1-v2-joint-lift@5283456c434c8316b073dee8bba1bdfd49fa7eb9`  
**Classification:** post-hoc explanatory analysis of an already closed pilot

## 1. Purpose

The closed pilot establishes that the frozen M3 predictor improves end-to-end horizon-dependent admissibility prediction relative to M1/M2, especially in the intermediate and stress query regimes. This audit asks a narrower mechanism question:

> Does the frozen experiment contain direct evidence that limited provider disclosure leaves practically compatible latent models whose composed SLA-facing probabilities differ enough to matter for decisions?

This audit does **not** develop a new method. M0, M1, M2, M3, the public I1 interface, the M3 lambda, candidate bank, top-14 retained support, graph budgets, query battery, white-box reference, and all frozen predictions remain unchanged.

## 2. Stage A: zero-simulation read-only audit

Stage A reads only already materialized artifacts. It performs no AICon/YAFS/provider simulation and generates no new white-box evidence.

It answers five questions.

### A1. Hidden-process / candidate-bank audit

After the method is closed, compare the known D300 hidden provider process against the 48-candidate M3 support for each provider.

Report:

- whether the exact hidden tuple appears in the candidate bank;
- the nearest candidate in transformed parameter space;
- its public-I1 discrepancy, Gibbs weight, discrepancy rank, and weight rank.

The hidden parameters are used only for this retrospective diagnostic. They must not alter M3, its support, weights, lambda, or any prediction.

### A2. SLA decision analysis

For beta in {0.80, 0.90, 0.95}, define

```
D_ref = 1{sigma_WB >= beta}
D_hat = 1{sigma_hat >= beta}
```

over the frozen H=60..240 s evaluation window.

For M0/M1/M2/M3-B1400/M3-B2000 report:

- decision agreement;
- false accepts;
- false rejects.

Also report the same metrics only where the N=200 white-box Wilson interval lies entirely on one side of beta. This separates disagreement with the white-box point estimate from decisions that are themselves unresolved at the available reference precision.

### A3. Empirical composition-induced ambiguity

Use the frozen M3 top-14 retained support and the B=2000 member curves. At every frozen query/horizon point compute

```
A(q,H) = sum_j alpha_j [sigma_j(q,H) - sigma_bar(q,H)]^2
```

plus the empirical member range. Aggregate these quantities over H=60..240 s for each of the 15 frozen query cells.

Relate the ambiguity proxy, exploratorily, to:

- M1 MAE;
- M1-to-M3 MAE improvement;
- M2-to-M3 MAE improvement.

These correlations are post-hoc descriptive evidence, not confirmatory inference.

### A4. Direct practical non-identifiability diagnostic

For each retained joint hypothesis, construct its public-I1 joint discrepancy as the sum of the three frozen provider mean Bernoulli-KL discrepancies.

Materialize the relation between joint public-I1 discrepancy and composed sigma for every frozen query/horizon point. Also materialize all hypothesis pairs with:

- absolute discrepancy difference;
- absolute composed-sigma difference.

This provides direct evidence for, or against, the claim that similarly plausible latent reconstructions can diverge after composition.

### A5. Existing top-1 diagnostic

Reuse the already simulated rank-1 M3 member curve and compare it with the white-box reference.

This is explicitly **not** a cost-matched Top1 ablation because the frozen M3 allocation assigns rank 1 fewer than B total trajectories. It is only a diagnostic deciding whether a separately frozen cost-matched ablation is scientifically warranted.

## 3. Stage-A stop rule

After Stage A:

- If practical model ambiguity is negligible and the existing top-1 diagnostic explains essentially all of M3's benefit, stop. Do not run an ambiguity-preservation ablation; narrow the manuscript claim.
- If retained hypotheses with similar public-I1 fit produce materially different composed sigma and/or decision outcomes, freeze a separate Stage-B ablation contract **before** any new simulation.

No numerical pass threshold is introduced post hoc. The decision to proceed must be based on the qualitative mechanism evidence plus transparent reported summaries.

## 4. Possible Stage B, not authorized by this protocol

If warranted, Stage B will compare the same frozen top-14 support under:

1. Top1 only;
2. Uniform14;
3. frozen Weighted14.

Uniform14 and Weighted14 must use identical per-hypothesis graph ledgers. Top1 must receive a separately cost-matched graph budget. The Stage-B seed bank, budgets, allocation, and analysis must be frozen in a new contract before execution.

Stage A does not authorize these simulations.

## 5. Scientific firewall

The audit must not:

- change lambda=30;
- change any provider candidate;
- change the retained 99.9% support;
- change M0/M1/M2/M3;
- change any admissibility region or rho;
- generate or replace white-box evidence;
- use hidden provider parameters for prediction or selection;
- reuse the unpublished PPG GP+DVI mechanism, readiness score, code, data, or experimental setup.

The PPG firewall remains in force.

## 6. Required Stage-A outputs

The read-only runner must write, under `results/m3_posthoc_mechanism_audit_v1/`:

- `truth_candidate_audit.csv`
- `decision_metrics.csv`
- `ambiguity_pointwise.csv`
- `ambiguity_query_summary.csv`
- `ambiguity_correlations.csv`
- `joint_energy_sigma_points.csv`
- `joint_energy_sigma_pairs.csv`
- `top1_existing_diagnostic.csv`
- `top1_existing_summary.csv`
- `posthoc_mechanism_audit_manifest.json`
- compact diagnostic figures

All outputs are explanatory/post-hoc and must be labeled as such.
