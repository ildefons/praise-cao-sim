# M1 vs Top1 public-I1 audit closure

**Date:** 24 September 2026  
**Status:** CLOSED_AFTER_READ_ONLY_AUDIT  
**Branch:** `caise-posthoc-mechanism-audit`  
**Result commit:** `f569e5e`

## Purpose

This read-only audit was opened after the Stage-B mechanism ablation showed that a cost-matched Top1 reconstruction performed approximately as well as the frozen production M3 mixture at graph level. The concrete question was why frozen M1 was much worse than Top1 even though both ultimately provide one latent reconstruction per provider.

The audit compared the frozen M1-v2 independent replay with the maximum-weight M3-v3 reconstruction under the **same public-I1 discrepancy**, using the exact Jeffreys-smoothed Bernoulli-KL energy already used by M3. No new simulation, candidate generation, graph evaluation, or white-box read was performed.

## Main result

The result is **mixed by provider**.

### Provider A

- M1 Bernoulli-KL: 0.200133
- Top1 Bernoulli-KL: 0.259181
- M1 MSE: 0.055136
- Top1 MSE: 0.065032

M1 reconstructs the public I1 surface better than Top1 under both KL and MSE, despite substantially different latent parameters. In particular, Top1 cost rate is approximately 9.85x the M1 cost rate.

### Provider B

- M1 Bernoulli-KL: 0.140105
- Top1 Bernoulli-KL: 0.110514
- M1 MSE: 0.044898
- Top1 MSE: 0.035301

Top1 gives a moderate improvement in local public-I1 reconstruction.

### Provider C

- M1 Bernoulli-KL: 0.273175
- Top1 Bernoulli-KL: 0.087948
- M1 MSE: 0.060790
- Top1 MSE: 0.029589

Top1 is substantially better. The selected latent parameters are also radically different:

- M1 mean service time: 0.002682 s
- Top1 mean service time: 0.173967 s
- M1 cost rate: 87.307
- Top1 cost rate: 0.551638
- M1 service CV: 0.994198
- Top1 service CV: 0.341104

Thus a large part of the M1-vs-Top1 graph-level difference may arise from reconstruction quality, particularly for Provider C, rather than from point collapse itself.

### Equal-provider aggregate

- M1 mean Bernoulli-KL: 0.204471
- Top1 mean Bernoulli-KL: 0.152548
- M1 mean MSE: 0.053608
- Top1 mean MSE: 0.043307
- M1 mean MAE: 0.148192
- Top1 mean MAE: 0.131558

Top1 is better in aggregate, but not uniformly provider by provider.

## Interpretation for the single-graph pilot

The audit does **not** support treating M1 failure as evidence that all single-point reconstructions are intrinsically inadequate.

The defensible pilot observations are narrower:

1. Limited public provider evidence admits materially different latent reconstructions.
2. Different public-only reconstruction procedures can select materially different latent processes.
3. Reconstruction choice can materially change end-to-end composition predictions.
4. Public-I1 weighting improves over uniform propagation on the frozen support.
5. The current pilot does not establish an accuracy advantage of retaining multiple hypotheses over the highest-plausibility single reconstruction.

Provider A is consistent with practical non-identifiability because substantially different latent parameterizations coexist with similar, and even reversed, local-fit ordering. Provider C simultaneously shows that search / reconstruction quality can dominate. The present single graph cannot disentangle these mechanisms generally.

## Manuscript rule

The current paper should present these as **pilot observations and hypotheses**, not as general conclusions about all compositions.

In particular, avoid statements equivalent to:

- point collapse is intrinsically inadequate;
- ambiguity preservation is necessary for accurate composition;
- retained spread generally predicts point-reconstruction failure.

A safer formulation is:

> The pilot indicates that the inverse mapping from limited provider evidence to a compositional surrogate is consequential: different public-only reconstructions can fit the disclosed interface differently and produce materially different end-to-end predictions. Whether this sensitivity generalizes across graph structures, workloads, and evidence regimes remains a hypothesis for multi-graph evaluation.

## Consequence for the multi-graph study

The prospective multi-graph study should include budget-matched M1, Top1, and weighted-M3 arms and test when point selection becomes fragile. It should also separate reconstruction-loss/search effects from ambiguity-retention effects and analyze these mechanisms across graphs rather than over pooled cells from one graph.

## Closure rule

This audit is now closed.

Do not retune M1, Top1, M3, the scoring rule, or the candidate support in response to this outcome.

The next step is manuscript revision and then a separately frozen multi-graph protocol.
