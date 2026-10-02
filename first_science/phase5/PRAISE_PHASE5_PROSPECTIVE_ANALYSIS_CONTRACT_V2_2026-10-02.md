# PRAISE/CAO Phase-5 Prospective Analysis Contract V2

**Status:** FROZEN BEFORE SCIENTIFIC EXECUTION  
**Date:** 2 October 2026  
**Machine-readable authority:** `config_phase5_analysis_addendum_v2.json`

This V2 analysis contract supersedes the V1 analysis addendum before any Phase-5 scientific execution. It is subordinate only to the V2 battery protocol and does not permit any post-outcome method repair.

## 1. Directional prediction error

For every primary method report MAE, RMSE, signed bias and maximum absolute error. Signed bias is

$$
\mathrm{Bias}=\operatorname{mean}(\hat\sigma-\hat\sigma_{WB}).
$$

Report false accepts and false rejects separately at $\beta=.90$, with $.80$ and $.95$ secondary, on the predeclared WB-resolvable subset.

A 10,000-replicate final-WB trajectory-cluster bootstrap uses seed 2026100201. Method predictions remain fixed. The resampling unit is the complete WB trajectory index, kept together across all queries and horizons and jointly across physical cells where the same CRN index is reused. The resulting percentile interval quantifies only finite-$N_{WB}=1000$ reference fluctuation.

## 2. Directional topology hypothesis

For method $M$ and provider world $P$:

$$
\Delta_P^M
=
\mathrm{MAE}_M(P,G_{SEQ})
-
\mathrm{MAE}_M(P,G_{PAR}).
$$

The masking hypothesis predicts $\Delta_P^M>0$.

The second prospective contrast is

$$
\Delta_{het}^M
=
\frac{\Delta_{P2}^M+\Delta_{P4}^M}{2}
-
\frac{\Delta_{P1}^M+\Delta_{P3}^M}{2},
$$

with expected direction $\Delta_{het}^M>0$ under the masking/load-concentration explanation.

P2/P4 are not interpreted as a pure heterogeneity manipulation because they also concentrate utilization toward ProviderC.

G_SEQPAR and G_PARSEQ are mechanistic triangulation conditions, not a clean factorial decomposition of aggregation versus workload shift.

## 3. Passive mechanism diagnostics

Where available without changing execution, derive or log:

- latency/cost/quality/multiple violation flags;
- controlling child at each `parallel_all` join;
- per-provider interarrival count, mean, standard deviation, CV, p10, median and p90.

These diagnostics are never method inputs. If unavailable without changing simulator semantics, record `NOT_AVAILABLE`.

## 4. Common-bank scoring diagnostic

The secondary `LHS_MSE_TOP1_DIAG` uses the same 48-candidate LHS bank and frozen M3 $N=100$ local-rescore ledgers.

One candidate/provider is selected by minimum raw-sigma MSE. The resulting joint model is propagated for $N=100$ graph trajectories on the first 100 M3 rank-1 seeds.

Its matched comparator is the KL-ranked M3 Top1 recomputed from the first 100 production rank-1 trajectories on the identical seeds.

The paired contrast is interpreted as a scoring-rule comparison within a common candidate bank and common local evidence. M1 versus LHS-MSE is only a broader search/candidate-generation comparison.

## 5. Continuous recoverability profile

No binary recoverable/not-recoverable threshold is introduced.

For each eligible physical cell report:

- MAE;
- RMSE;
- signed bias;
- maximum absolute error;
- reference-noise-adjusted RMSE;
- false-accept rate on WB-resolvable points;
- false-reject rate on WB-resolvable points.

The reference-noise adjustment removes only the estimated finite-WB Bernoulli sampling contribution and is not a full uncertainty correction.

## 6. M3 Monte Carlo precision

Use the same plug-in estimator for Top1, Top3 and Top14:

$$
\widehat V
=
\sum_j \tilde w_j^2
\frac{\hat p_j(1-\hat p_j)}{N_j}.
$$

Also report

$$
V_{max}=\sum_j\frac{\tilde w_j^2}{4N_j}.
$$

## 7. Prospectively declared secondary analyses after primary evaluation

These are registered now but executed only after primary Phase-5 predictions and final-WB evaluation are frozen:

1. score hidden true $\theta$ on public I1 and compare its energy/rank with reconstructed candidates;
2. test whether M3 retained-support ambiguity/envelope diagnostics identify decision errors;
3. bootstrap the $N=100$ public-sigma acquisition trajectories conditional on frozen I1 region geometry, recompute public sigma surfaces and frozen-candidate energies/weights, and report Top1 identity frequency and weight variability.

None may feed back into M0-M3, query construction, support selection or graph budgets.
