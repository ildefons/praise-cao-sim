# M1 vs Top1 public-I1 fit audit

**Date:** 24 September 2026  
**Status:** FIXED_BEFORE_EXECUTION  
**Branch:** `caise-posthoc-mechanism-audit`

## Purpose

The post-hoc M3 audit showed that a cost-matched highest-weight single reconstruction (Top1) is approximately as accurate at graph level as the frozen production M3 mixture. This raises a concrete question: why is frozen M1 much worse than Top1 even though both ultimately provide one latent reconstruction per provider?

Before revising the paper further, perform one **read-only, zero-simulation audit** under the exact public-I1 discrepancy already used by M3.

## Question

For each provider, compare the frozen M1-v2 selected reconstruction with the M3-v3 highest-weight reconstruction using the same public I1 evidence and the same M3 Bernoulli-KL energy.

This distinguishes three descriptive possibilities without introducing a new method:

1. M1 is materially worse under the M3 energy, suggesting that loss/search choices explain much of the graph-level difference.
2. M1 and Top1 have similar public-I1 fit but different latent parameters and very different composed behavior, providing direct evidence of practical interface non-identifiability.
3. A mixed provider-specific picture, which should be reported as such and not collapsed into a stronger mechanism claim.

No threshold for these interpretations is fixed in advance. The audit reports the measurements; interpretation follows them.

## Frozen inputs

- Frozen M1-v2 parameter manifest:
  `first_science/phase3/phase3_i1_m1_v2_freeze_manifest_v1.json`
- Frozen M1-v2 **independent replay** comparisons, N=100, discovered under:
  `first_science/phase3/results/**/m1_v2_independent_replay_comparison.csv`
  and accepted only when the sibling `m1_v2_best.json` matches the frozen parameter tuple.
- Frozen M3-v3 provider weights:
  `first_science/phase4/results/m3_lambda_cv_v3/m3_v3_provider_weights.csv`
- Frozen M3 local N=100 candidate comparisons:
  `first_science/phase4/results/m3_local_weighting_v1/local_surfaces/<candidate>_comparison.csv`

The M3 Top1 provider reconstruction is the maximum-`weight_v3` candidate for that provider. Under the factorized product distribution, the joint Top1 is the tuple of the three provider-wise maxima.

## Common public-I1 score

For every H>0 public surface point, use the exact M3 smoothing and energy:

[
p^J = \frac{Np+0.5}{N+1},\qquad
r^J = \frac{Nr+0.5}{N+1},
]

with N=100 for both the public I1 surface and each reconstruction replay, followed by

[
E(\theta)=\frac{1}{K}\sum_k
D_{\mathrm{Bern}}\!\left(p_k^J\,\Vert\,r_k^J\right).
]

Also report raw probability MSE, RMSE, MAE, bias, and maximum absolute error, because M1 itself was selected by uniform MSE rather than Bernoulli KL.

## Parameter comparison

For each provider report both tuples

[
\theta=(\mu,\kappa,CV)
]

and the Top1/M1 ratios. These are descriptive only. Hidden D300 parameters are not used.

## Firewall

This audit:

- performs **no provider simulation**;
- performs **no graph simulation**;
- reads **no graph white-box outcome**;
- generates **no new candidate**;
- changes **no M1/M2/M3 parameter, support, weight, lambda, or query**;
- uses no hidden provider parameters.

## Outputs

- `m1_vs_top1_public_i1_fit.csv`
- `m1_vs_top1_parameters.csv`
- `m1_vs_top1_pointwise.csv`
- `m1_vs_top1_manifest.json`

## Stop rule

After this audit, interpret the frozen result as-is. Do not retune M1, Top1, M3, the scoring rule, or the candidate bank in response to the outcome.

The current single-graph manuscript should state mechanism claims as **pilot hypotheses / observations**, not general conclusions. Generalization questions are reserved for the preregistered multi-graph study.
