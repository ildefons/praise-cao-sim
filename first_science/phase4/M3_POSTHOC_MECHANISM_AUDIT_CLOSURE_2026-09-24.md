# M3 post-hoc mechanism audit closure

**Date:** 24 September 2026  
**Status:** CLOSED_AFTER_FROZEN_STAGE_B  
**Branch:** `caise-posthoc-mechanism-audit`  
**Stage-A result commit:** `9369030`  
**Stage-B result commit:** `98fedd3`

## 1. Scope

This document closes the post-hoc mechanism audit of the already frozen PRAISE pilot.

The audit was opened after the final M3-v4 evaluation because the pilot showed a large predictive improvement over M1/M2, but the mechanism behind that improvement remained ambiguous. In particular, M3 combined two ideas:

1. public-I1-based plausibility weighting over a finite latent support;
2. retention and weighted integration of multiple compatible latent hypotheses.

The audit asked whether the pilot actually supports the stronger interpretation that **preserving multiple latent hypotheses is itself responsible for the M3 gain**.

This audit is post-hoc explanatory analysis. It does not alter the prospective chronology of the frozen M3-v4 evaluation.

## 2. Frozen final-evaluation context

Over the authoritative H=60..240 s window, the previously frozen final evaluation reported:

- M1 MAE: approximately 0.1852;
- M2 MAE: approximately 0.0682;
- M3 B=1400 MAE: approximately 0.03037;
- M3 B=2000 MAE: approximately 0.02755.

M3 therefore remained the strongest frozen full method in the original prospective comparison.

The present audit does not replace those results. It asks what aspect of M3 explains them.

## 3. Stage A: zero-simulation explanatory audit

Stage A was frozen before execution and used only existing artifacts.

### 3.1 No exact hidden-process tuple in the M3 candidate bank

For ProviderA, ProviderB, and ProviderC, the exact D300 hidden provider tuple was absent from the corresponding 48-candidate M3 support.

The nearest hidden-parameter candidates were not highly ranked by public-I1 fit:

- ProviderA nearest candidate: public-I1 energy rank 28/48;
- ProviderB nearest candidate: rank 25/48;
- ProviderC nearest candidate: rank 11/48.

Their Gibbs weights were negligible.

Therefore the strong M3 result is not explained by the true hidden D300 parameter tuple being explicitly present and selected from the candidate bank.

### 3.2 Composition-induced member spread tracks difficult query cells

Across the 15 frozen query cells, the plug-in MC-adjusted retained-member ambiguity variance had the following post-hoc Spearman correlations:

- with M1 MAE: **0.754**;
- with M1 minus M3(B=2000) MAE: **0.725**;
- with M2 minus M3(B=2000) MAE: **0.654**.

The raw spread diagnostics gave still larger correlations.

Interpretation: the retained latent support is more compositionally dispersed in query cells where naive point collapse performs poorly. This supports the claim that limited provider disclosure leaves operationally relevant latent ambiguity.

However, correlation of spread with error does not establish that averaging multiple hypotheses is the best estimator.

### 3.3 Existing top-1 diagnostic created a concrete alternative explanation

Using only the already simulated rank-1 retained hypothesis, with 900 graph trajectories, the Stage-A diagnostic obtained:

- whole-window MAE: **0.02537**;
- G0 MAE: **0.02067**;
- G1 MAE: **0.02632**;
- G2 MAE: **0.02911**.

Because this diagnostic was not cost matched, it was not used as a final ablation result. But it showed that the highest-public-I1-weight hypothesis alone could explain much of the apparent M3 advantage.

This triggered the frozen Stage-B cost-matched ablation.

## 4. Stage B: cost-matched mechanism ablation

Stage B was frozen before execution. It used the already frozen top-14 retained support and lambda=30 weights.

At a common total graph budget of B=1400, it compared:

- **TOP1_1400:** rank-1 hypothesis only, 1400 trajectories;
- **UNIFORM14_EQ_1400:** 14 retained hypotheses, 100 trajectories each, equal weights;
- **WEIGHTED14_EQ_1400:** the exact same 14 x 100 graph ledgers, frozen M3 weights;
- **WEIGHTED14_MINIMAX_1400:** the already frozen production M3 B=1400 result.

Uniform14 and Weighted14-EQ use exactly the same graph evidence, so their difference isolates weighting.

No provider model, candidate, lambda, support, query, or white-box reference was changed.

## 5. Stage-B results

### 5.1 Whole-window prediction accuracy

| Method | MAE | RMSE | Bias | Max abs. error |
|---|---:|---:|---:|---:|
| TOP1_1400 | **0.02878** | **0.03406** | 0.02498 | **0.09571** |
| UNIFORM14_EQ_1400 | 0.05490 | 0.06570 | 0.05362 | 0.14714 |
| WEIGHTED14_EQ_1400 | 0.04222 | 0.05016 | 0.04066 | 0.12487 |
| WEIGHTED14_MINIMAX_1400 | 0.03037 | 0.03578 | 0.02824 | 0.11409 |

The cost-matched top-1 estimator has the lowest point-estimate MAE and RMSE in this Stage-B comparison.

### 5.2 Per-regime MAE

| Regime | TOP1 | Uniform14-EQ | Weighted14-EQ | Weighted14-minimax |
|---|---:|---:|---:|---:|
| G0 / easy | **0.02297** | 0.02915 | 0.02804 | 0.02363 |
| G1 / intermediate | **0.03454** | 0.06278 | 0.05245 | 0.03553 |
| G2 / stress | **0.02885** | 0.07277 | 0.04617 | 0.03195 |

The same qualitative ordering holds in all three regimes.

### 5.3 Weighting versus uniform ambiguity preservation

The frozen shared-seed bootstrap for

```
delta = MAE(Weighted14-EQ) - MAE(Uniform14-EQ)
```

gave:

- mean delta: **-0.01001**;
- median: **-0.01039**;
- percentile 95% interval: **[-0.01376, -0.00348]**;
- fraction of replicates with delta < 0: **0.992**.

Because Uniform14-EQ and Weighted14-EQ use exactly the same 14 x 100 common-random-number ledgers, this is the cleanest mechanism result in Stage B.

**Conclusion:** public-I1 weighting improves materially over treating all retained hypotheses equally.

### 5.4 Weighted multi-hypothesis estimator versus top-1

For

```
delta = MAE(Weighted14-EQ) - MAE(Top1)
```

the graph-MC diagnostic bootstrap gave:

- mean delta: **+0.01859**;
- median: **+0.01682**;
- percentile 95% interval: **[-0.00117, +0.04707]**;
- fraction of replicates with delta < 0: **0.0364**.

This comparison is not a strict paired bootstrap because Top1 uses 1400 trajectories while the equal-support mixture uses 100 shared trajectories per member. Therefore the 3.64% value is not interpreted as a formal significance probability.

Nevertheless, the point estimate and bootstrap direction provide **no evidence that retaining multiple hypotheses improves over the highest-weight hypothesis in this pilot**.

### 5.5 Production minimax allocation

The production weighted estimator with the frozen minimax allocation improves substantially over the equal-allocation weighted estimator:

- Weighted14-EQ MAE: **0.04222**;
- Weighted14-minimax MAE: **0.03037**.

This comparison is descriptive because the two estimators use different seed banks, but it is consistent with the theoretical allocation result: concentrating simulation effort according to the retained weights strongly reduces graph Monte Carlo error.

The optimized weighted mixture reaches nearly the same accuracy as Top1, but it does not surpass Top1 in this pilot point estimate.

## 6. SLA-decision consequences

On white-box-Wilson-certain cases:

### beta = 0.80

All Stage-B estimators achieved 100% decision agreement.

### beta = 0.90

- Top1: **97.09%** agreement;
- Uniform14-EQ: 83.16%;
- Weighted14-EQ: 86.49%;
- Weighted14-minimax: 96.47%.

### beta = 0.95

- Top1: **100%** agreement;
- Uniform14-EQ: 95.14%;
- Weighted14-EQ: 97.03%;
- Weighted14-minimax: **100%**.

Thus the decision-level results agree with the prediction-error analysis. Weighting helps over uniform integration, while the pilot does not show a decision advantage from the weighted multi-hypothesis estimator over the best selected single hypothesis.

## 7. Scientific interpretation

### Supported

The pilot supports the following statements:

1. **Limited provider disclosure induces practical latent non-identifiability.** Multiple hidden reconstructions remain compatible with public I1 evidence, and their composed behavior can differ substantially.

2. **Composition-induced latent spread is associated with difficult prediction regimes.** The Stage-A ambiguity proxy rises where M1 error and M1-to-M3 improvement rise.

3. **How the latent ambiguity is resolved matters.** Public-I1 plausibility weighting is substantially better than uniform averaging over the same retained hypotheses.

4. **A public-I1-selected point reconstruction can be very strong.** The highest-weight retained hypothesis alone performs approximately as well as, and in the Stage-B point estimate slightly better than, the optimized weighted mixture.

5. **Graph-simulation allocation matters.** The minimax allocation recovers much of the accuracy lost by equal allocation in the weighted mixture.

### Not supported

The pilot does **not** support the stronger claim that:

> preserving and averaging multiple compatible latent hypotheses is what causes the M3 improvement over point reconstruction.

The cost-matched Top1 ablation contradicts that interpretation for this pilot.

The paper must not claim that ensemble retention is empirically necessary here.

## 8. Revised mechanism statement

The defensible mechanism is:

> Limited provider information creates a set-valued inverse problem. The important step is not merely to preserve more latent models, but to resolve that ambiguity using the disclosed provider evidence. In the pilot, public-I1 plausibility sharply identifies a small high-value region of latent space: weighting improves strongly over uniform ambiguity preservation, while the highest-plausibility single reconstruction already captures most of the predictive benefit. Weighted integration with optimized allocation remains competitive and provides a principled finite-mixture representation, but its empirical advantage over the best selected point reconstruction is not established by this pilot.

A compact causal chain is therefore:

```
limited disclosure
    -> practical model non-identifiability
    -> compositionally different latent explanations
    -> need for evidence-informed ambiguity resolution
    -> ranking / weighting / selective graph propagation
```

rather than:

```
limited disclosure
    -> preserve many models
    -> averaging them is necessarily better
```

## 9. Manuscript consequences

The manuscript should:

1. retain the interface-induced non-identifiability framing;
2. retain the distinction between I and M;
3. retain M1/M2/M3 as the frozen prospective method comparison;
4. report Stage A and Stage B explicitly as **post-hoc mechanism analyses**;
5. add Top1 as an explanatory ablation, not retroactively as a prospective competitor;
6. state that public-I1 weighting beats uniform integration on the same support/evidence;
7. state that the pilot does not demonstrate a benefit of multi-hypothesis retention over the highest-weight single reconstruction;
8. emphasize the practical value of the minimax graph-allocation theorem separately from any claim about ensemble superiority;
9. avoid language such as “ambiguity preservation is necessary” or “M3 succeeds because it retains multiple models”;
10. preserve the prospective M3-v4 final evaluation as the primary accuracy result and use the mechanism audit to qualify its interpretation.

## 10. Closure rule

The Stage-B contract froze the following rule:

> After Stage B, do not tune or add variants. Interpret the frozen ablation as-is and close the pilot mechanism audit.

That rule is now satisfied.

**The pilot mechanism audit is CLOSED.**

No further point-model, ensemble, weighting, allocation, seed-bank, or white-box variant should be added to this pilot.

The next scientific work should be either:

- manuscript revision using the now-closed evidence; or
- a separately preregistered prospective multi-graph study testing which graph/query conditions make latent ambiguity consequential and whether evidence-informed point selection or weighted integration generalizes better.
