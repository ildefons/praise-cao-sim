# PRAISE/CAO: M3 weighted latent sampling plan

**Status:** planned next scientific target. No M3 graph prediction or M3 white-box evaluation has been run.  
**Date:** 23 September 2026.

This document extends the frozen I1-M0-M1-M2 pilot after the final fixed-graph sigma-regime evaluation. M0, M1 and M2 remain closed. M3 is a new method, not an M2 repair.

## 1. Scientific question

M2 established that preserving inverse ambiguity matters increasingly as the global admissibility query becomes harder, but its equal-weight 27-member mean remains too optimistic in the G2 regime.

M3 asks two linked questions while keeping the public information representation fixed at I1:

1. **Weighting question:** can public-I1 reconstruction quality be used to assign non-uniform plausibility to latent provider explanations without exposing any new provider information?
2. **Budget-allocation question:** at a fixed graph-simulation budget, is it better to sample **more latent hypotheses with fewer trajectories each** than fewer latent hypotheses with more trajectories each?

The primary equal-budget comparison is frozen conceptually as:

- **M3-200x10:** K=200 weighted joint latent hypotheses, N=10 graph trajectories per hypothesis;
- **M3-100x20:** K=100 weighted joint latent hypotheses, N=20 graph trajectories per hypothesis.

Both cost exactly

`B = K*N = 2000`

graph trajectories.

The first 100 latent hypotheses in M3-100x20 are the first 100 hypotheses of the same frozen ordered 200-hypothesis bank used by M3-200x10. For those first 100 hypotheses, the first 10 trajectory seeds are shared across the two allocations. The extra 10 trajectories in M3-100x20 are additional independent replications.

## 2. Why this is a distinct method from M2

M2 uses three deliberately diverse, independently confirmed representatives per provider and assigns equal weight to all 27 Cartesian combinations. The M2 representatives were selected for **coverage/diversity**, not as posterior samples. Their equal weights are therefore a convention, not relative plausibility.

M3 instead constructs a broad, proposal-controlled provider candidate bank and attaches a public-I1-only weight to each latent explanation. Joint graph hypotheses are then sampled from the resulting weighted product distribution.

Conceptually:

`M2 = preserve ambiguity with a small equal-weight representative set`

`M3 = represent relative plausibility inside the ambiguity and sample composition from that weighted distribution`.

M3 must not reweight the existing 27 M2 members directly. That would conflate M2's diversity-selection mechanism with probability mass.

## 3. Provider candidate support

Use the already-generated **non-adaptive LHS bank** from M2-A2 as the initial M3 provider support:

- 48 LHS candidates for ProviderA;
- 48 LHS candidates for ProviderB;
- 48 LHS candidates for ProviderC.

This bank is scientifically attractive for M3 because:

- it was generated before the final graph WB result;
- it is non-adaptive;
- its proposal is known and approximately uniform in normalized `(log mu, log kappa, CV)` coordinates;
- it does not inherit TPE/GP acquisition-density bias;
- it already spans the final declared M1 latent domain.

The LHS geometry is therefore treated as a finite quasi-Monte-Carlo approximation to a uniform prior over the declared transformed latent domain.

### 3.1 Fresh local rescoring before weighting

Before any M3 graph propagation, rescore all 144 LHS candidates against the frozen public I1 surface on one new provider-local simulation bank.

Frozen local target:

- `N_local=100` trajectories per candidate;
- exact seed bank `35000..35099`;
- common random numbers across candidates;
- provider-local evidence only;
- no graph simulation;
- no graph WB read;
- no hidden Phase-1 provider parameter read;
- no new candidate search.

Total local rescoring cost:

`3 * 48 * 100 = 14400`

provider-local trajectories.

Using N=100 matches the public I1 trajectory count and reduces noise before the exponential weighting step. This is a one-time construction cost and is accounted separately from graph-query cost.

## 3.2 M3-v1 concentration audit and frozen V2 tempering

The first local weighting construction used beta=100, motivated by the public-I1 trajectory count. The local-only concentration audit showed that this scaling is too sharp for the present finite LHS support:

- ProviderA ESS = 1.68;
- ProviderB ESS approximately 1;
- ProviderC ESS approximately 1;
- joint product ESS approximately 1.68;
- 200 joint draws produced only 3 unique latent combinations.

No graph simulation or graph WB had been opened, so this remains development evidence rather than a contaminated graph result.

The audit evaluated the fixed beta grid `{0,1,2,5,10,20,50,100}`. M3-v2 freezes the following local-only temperature-selection rule:

`choose the largest beta such that ESS_i >= 3 for every provider`.

The threshold 3 is tied to the existing M2 support size: M3 is intended to preserve and weight inverse ambiguity, so its effective provider support should not collapse below the three representative hypotheses already carried by M2.

This rule selects

`beta = 5`.

At beta=5, the observed provider ESS values are approximately:

- ProviderA: 3.15;
- ProviderB: 3.96;
- ProviderC: 3.44;
- joint product ESS: about 42.9.

M3-v2 reuses the already-computed fresh N=100 local rescoring results. No provider simulation is repeated. Only the frozen Gibbs temperature and the resulting provider/joint weights are changed.

The authoritative V2 contract is:

`phase4/config_phase4_m3_weighting_v2_tempered.json`.

The V1 beta=100 weighting and its degenerate 200-draw bank remain archived as development evidence and must not be used for graph execution.

## 3.3 M3-v3 public-I1 cross-validation and dominant-mass result

The provisional M3-v2 ESS-threshold rule was **superseded before execution** because choosing `beta=5` from an ESS target would make the concentration parameter a design heuristic rather than a predictive quantity.

M3-v3 instead selected one global Gibbs concentration parameter `lambda` by public-I1-only blocked cross-validation. Complete `(region_rho, query_rho)` horizon curves were held out in five Latin-balanced folds. For each candidate `lambda`,

`w_j(lambda) proportional to exp[-lambda E_j^train]`

was fitted on the training curves and the weighted local mixture was scored on held-out curves using mean Bernoulli KL. No ESS constraint, graph prediction, or graph WB entered selection.

The frozen grid selected

`lambda = 30`

with mean held-out Bernoulli KL `0.1260419`. The neighboring values showed a shallow optimum: approximately `0.127666` at lambda 15, `0.126375` at 20, and `0.129613` at 50.

The resulting full-surface provider ESS values were:

- ProviderA: `2.7127`;
- ProviderB: `1.0208`;
- ProviderC: `1.0697`;
- joint product ESS: `2.9621`.

Thus the concentration is not merely an artifact of the original lambda=100 choice. Public-I1 predictive cross-validation itself prefers a sharply weighted finite latent distribution.

The exact 48^3 joint-mass audit then showed:

- top 3 hypotheses retain `0.956372` mass;
- top 7 retain `0.993195`;
- top 8 retain `0.995770`;
- top 14 retain `0.999174`;
- top 23 retain `0.999913`.

Therefore the original random-draw breadth/depth experiment (`K=200,N=10` versus `K=100,N=20`) is **superseded before graph execution**. Under the frozen V3 weighting, 100 or 200 categorical draws mostly repeat the same few hypotheses and do not constitute a meaningful latent-breadth comparison.

The current graph target is deterministic **dominant-mass quadrature** over the minimal top-ranked set whose cumulative joint weight reaches at least `0.999`. In the frozen V3 distribution this selects 14 joint hypotheses and gives the deterministic truncation guarantee

`|sigma_full(q) - sigma_top14(q)| <= 0.000826`

for every query `q`, before finite-trajectory Monte Carlo error.

## 4. Public-I1-only weighting rule

The public I1 surface is estimated from a finite trajectory bank and its points are strongly correlated across horizons and rho. Therefore M3 will **not** claim an exact Bayesian posterior over latent parameters.

Instead, use a generalized-Bayes/Gibbs weight built from a proper probability discrepancy.

For provider `i`, candidate `theta`, and public surface point `q`, let

- `p_i(q)` be the frozen public I1 sigma;
- `p_theta(q)` be the candidate's freshly rescored sigma, with finite-sample smoothing.

Use Bernoulli KL divergence

`D_Bern(p || r) = p log(p/r) + (1-p) log((1-p)/(1-r))`.

Define the candidate energy as the **mean** divergence over the complete frozen public surface:

`E_i(theta) = mean_q D_Bern(p_i(q) || p_theta(q))`.

Use Jeffreys smoothing for both finite-simulation probabilities:

`p_i(q) = (s_i(q) + 1/2) / (N_I1 + 1)`

`p_theta(q) = (s_theta(q) + 1/2) / (N_local + 1)`.

The original V1 provider weight was

`w_i(theta) proportional to exp[-N_I1 * E_i(theta)]`

with `N_I1=100`. This trajectory-count scaling is retained only as development history because it produced severe concentration. The graph-execution version uses the V3 cross-validated rule

`w_i(theta) proportional to exp[-lambda * E_i(theta)]`

with the public-I1-selected global `lambda=30`.

The original V1 motivation was:

- for one Bernoulli observation family, likelihood ratios scale asymptotically as `exp[-N*KL]`;
- using the **mean** over the correlated surface avoids pretending that every horizon/rho point is an independent experiment;
- multiplying by the actual I1 trajectory count gives the weighting scale a physical interpretation rather than introducing a free graph-tuned temperature.

This is a **trajectory-count-scaled Gibbs weight**, not a literal posterior probability. That terminology must be preserved.

### 4.1 Weight diagnostics before graph propagation

Before any graph simulation, materialize and freeze for each provider:

- normalized weights;
- effective sample size `ESS = 1 / sum_j w_j^2`;
- weight entropy and perplexity;
- maximum single-candidate weight;
- weighted moments of `log mu`, `log kappa`, and `CV`;
- weighted local I1 reconstruction curve;
- unweighted versus weighted public-I1 reconstruction error;
- joint product ESS, which factorizes as `ESS_A * ESS_B * ESS_C`.

No graph outcome may change the weighting formula, candidate support, or weights.

### 4.2 Concentration is a result, not a tuning gate

There is deliberately **no ESS-based redesign gate** after the frozen weights are observed. If the Gibbs rule concentrates strongly on a small part of the LHS support, that is itself a scientific result about this M3 construction.

Do not change the temperature, add candidates, or weaken the weighting rule simply to force a broader distribution. Numerical failures are implementation defects; statistical concentration is not.

The M3 graph stage therefore proceeds with the frozen distribution regardless of whether its ESS is high or low.

## 5. Joint weighted latent distribution

Assuming provider-local evidence independence under I1, define the finite joint latent distribution

`P(theta_Aj, theta_Bk, theta_Cl | I1) = w_Aj * w_Bk * w_Cl`.

This factorization is an M3 modeling assumption. It does not assert physical independence of provider execution; it states that the public provider-card evidence is weighted independently before the known graph mechanics are applied.

V3 first enumerates the exact finite `48^3` product weights. The graph-execution stage then retains the smallest descending-weight prefix whose cumulative mass is at least `0.999`. For the frozen V3 distribution this is the top 14 joint hypotheses with retained mass approximately `0.999174`.

The earlier ordered 100/200-draw banks remain development diagnostics only and are not used for graph execution.

### 5.1 Dominant-mass truncation bound

If the frozen weighted joint distribution becomes strongly concentrated, M3 need not approximate it by repeatedly sampling the same high-mass hypotheses. A deterministic top-mass quadrature can be used instead, with an explicit pointwise error bound.

For any graph query `q`, write the exact weighted M3 prediction as

`sigma_full(q) = sum_j w_j sigma_j(q)`,

where `w_j >= 0`, `sum_j w_j = 1`, and every member survival probability satisfies

`0 <= sigma_j(q) <= 1`.

Let `S` be a retained subset of joint latent hypotheses with total probability mass

`m = sum_{j in S} w_j`.

Define the renormalized truncated prediction

`sigma_S(q) = (1/m) sum_{j in S} w_j sigma_j(q)`.

Let the omitted mass be

`r = 1 - m`.

The full mixture can be decomposed as

`sigma_full(q) = m sigma_S(q) + r sigma_R(q)`,

where `sigma_R(q)` is the corresponding normalized prediction over the omitted hypotheses and therefore also lies in `[0,1]`.

Hence

`|sigma_full(q) - sigma_S(q)| = r |sigma_R(q) - sigma_S(q)| <= r = 1 - m`.

Therefore,

`|sigma_full(q) - sigma_S(q)| <= 1 - m`.

This bound is:

- deterministic;
- pointwise in every `(A_G,H,rho)` query;
- independent of the graph simulator details;
- independent of how different the retained and omitted latent hypotheses are;
- separate from finite-trajectory Monte Carlo error.

Examples:

- retaining 99% joint weight gives worst-case truncation error at most `0.01`;
- retaining 99.5% gives at most `0.005`;
- retaining 99.9% gives at most `0.001`.

This makes cumulative joint mass a principled computational stopping criterion. If a small number of hypotheses contains nearly all frozen M3 weight, deterministic weighted evaluation of those hypotheses can replace repeated categorical draws while providing an explicit approximation guarantee.

For the paper, this should be presented as a general property of weighted survival composition, not as an empirical feature specific to the present benchmark.

## 6. Graph simulation allocation

After the V3 mass audit, M3 no longer samples 100 or 200 latent hypotheses with replacement. It deterministically propagates the 14 dominant joint hypotheses whose cumulative frozen weight exceeds 0.999.

For retained hypothesis `j`, let the renormalized retained weight be

`alpha_j = w_j / m`,

where `m` is the total retained mass. Let `Z_jn(q)` be the binary trajectory-level pass indicator for query `q=(A_G,H,rho)`, and let

`p_hat_j(q) = (1/N_j) sum_n Z_jn(q)`.

The finite M3 dominant-mass estimator is

`sigma_hat_S(q) = sum_j alpha_j p_hat_j(q)`.

Two graph budgets are frozen before any M3 graph WB:

- `B=1400` total graph trajectories, 48% below M2's 2700 trajectories;
- `B=2000` total graph trajectories, the original planned M3 graph budget and 26% below M2.

The `B=1400` allocation is nested inside the `B=2000` allocation so one maximum-budget simulation bank supports both blind predictions.

### 6.1 Minimax trajectory allocation

With independent trajectory seed streams across retained latent hypotheses,

`Var[sigma_hat_S(q)] = sum_j alpha_j^2 p_j(q)(1-p_j(q))/N_j`.

Since every Bernoulli variance satisfies

`p_j(q)(1-p_j(q)) <= 1/4`,

we obtain the query-independent worst-case bound

`Var[sigma_hat_S(q)] <= (1/4) sum_j alpha_j^2/N_j`.

At fixed total graph budget

`B = sum_j N_j`,

the continuous minimizer of this worst-case bound is

`N_j proportional to alpha_j`.

For the required integer allocation with `N_j>=1`, use a deterministic greedy marginal rule. Start with one trajectory for every retained hypothesis. Each additional trajectory is assigned to the hypothesis maximizing

`Delta_j = alpha_j^2 / [N_j(N_j+1)]`.

This is the exact marginal reduction in the separable worst-case objective, and generates nested integer allocations as the total budget increases.

The frozen execution contract is:

`phase4/config_phase4_m3_v4_dominant_mass_graph_v1.json`.

### 6.2 Seed independence

Each retained joint hypothesis receives its own disjoint deterministic seed block. This preserves the simple variance decomposition above and avoids covariance terms from common random numbers across latent hypotheses.

The same member ledger is reused for every `rho`, regime, and horizon query, and the `B=1400` prediction uses a prefix of each member's `B=2000` ledger according to the frozen allocation table.

## 7. Error decomposition for M3 dominant-mass quadrature

M3 now has two conceptually separate numerical errors.

First, **latent truncation error** from omitting joint hypotheses outside the retained top-mass set:

`|sigma_full(q)-sigma_S(q)| <= 1-m`.

For the frozen top-14 V3 set,

`1-m approximately 8.26e-4`.

Second, **finite graph Monte Carlo error** inside the retained set. Its pointwise variance obeys

`Var[sigma_hat_S(q)] <= (1/4) sum_j alpha_j^2/N_j`.

The execution runner reports the resulting worst-case variance and standard-error bounds for both `B=1400` and `B=2000` before any graph WB is opened.

These two errors must not be conflated:

- the truncation bound is deterministic and distribution-free once the latent weights are frozen;
- the Monte Carlo term is stochastic and comes from finite graph trajectories.

The many horizon and rho curve points are not independent replications. Their computational value is that one graph ledger supports the full sigma family.

## 8. Frozen evaluation battery

Use the already-frozen 15-query fixed-graph G0/G1/G2 battery unchanged.

M3 may not recalibrate the query regions.

This is intentionally the same battery used for M2 so the integration mechanisms are directly comparable.

Because M3 was conceived after inspecting the final M2 result on this physical condition, a new M3 WB run on the same D300 condition is a **prospective same-condition replication**, not an untouched-condition validation claim.

No M3 weighting or sampling choice may use the previously opened M2 final WB values numerically.

## 9. Prediction freeze and new final WB

The current execution order is:

1. freeze M3 provider weights from public I1 only using the V3 cross-validated `lambda=30`;
2. enumerate the exact `48^3` product weights and freeze the minimal top-mass set with cumulative weight at least `0.999`;
3. freeze the integer minimax trajectory allocations for `B=1400` and `B=2000`;
4. run blind M3 graph prediction for both budgets from one nested maximum-budget simulation bank;
5. materialize every predicted sigma curve, truncation bound, and worst-case Monte Carlo variance bound;
6. hash-freeze both M3 budget predictions;
7. only then generate a new matched-D300 WB bank on previously unused seeds;
8. evaluate both M3 budgets and all frozen earlier baselines against that fresh WB;
9. close this M3 construction regardless of outcome.

Recommended final WB size:

`N_WB=200`.

The WB bank is generated only after the M3 prediction manifest is frozen. No WB result may alter lambda, retained hypotheses, weights, query regions, trajectory allocation, or budget.

### 9.1 Blind M3-v4 prediction completed

The dominant-mass graph prediction was completed and hash-frozen before any fresh M3 WB was generated.

Observed H60..H240 regime-mean predictions for `B=1400` and `B=2000` are close. Across the 15 rho-regime means, the mean absolute budget-to-budget difference is approximately `0.00377` and the maximum is approximately `0.00740`.

All 15 `B=1400` regime means are slightly above their nested `B=2000` counterparts. This is recorded as a blind finite-Monte-Carlo realization effect, not used to alter the budgets or allocation.

The frozen prediction manifest is:

`phase4/results/m3_v4_dominant_mass_graph_v1/m3_v4_prediction_manifest.json`.

The fresh final-evaluation contract is:

`phase4/config_phase4_m3_v4_final_evaluation_v1.json`.

It freezes a new matched-D300 WB bank with seeds `38000..38199`, `N_WB=200`, opened only after a prepare-only hash gate verifies the M3 predictions and the earlier frozen M0/M1/M2 prediction artifacts.

### 9.2 Fresh final WB result: M3-v4 closes positive

The fresh matched-D300 final WB evaluation was completed on seeds `38000..38199` with `N_WB=200`, after both M3 predictions and all method choices were hash-frozen.

Headline H60..H240 results:

| Method | Graph trajectories | MAE | RMSE | Bias | Max abs. error |
| --- | ---: | ---: | ---: | ---: | ---: |
| M1 | 100 per single latent model | 0.185171 | 0.230736 | +0.185171 | 0.535000 |
| M2 | 2700 | 0.068153 | 0.094141 | +0.047375 | 0.302593 |
| M3 B=1400 | 1400 | 0.030368 | 0.035783 | +0.028240 | 0.114088 |
| M3 B=2000 | 2000 | 0.027547 | 0.033064 | +0.024468 | 0.110645 |

Relative to frozen M2 on the same fresh WB:

- M3 B=1400 reduces whole-battery MAE by approximately **55.4%**, RMSE by **62.0%**, and maximum absolute error by **62.3%**, while using approximately **48% fewer graph trajectories**;
- M3 B=2000 reduces whole-battery MAE by approximately **59.6%**, RMSE by **64.9%**, and maximum absolute error by **63.4%**, while using approximately **26% fewer graph trajectories**.

The regime-specific MAE pattern is especially important:

| Regime | M2 MAE | M3 B=1400 MAE | M3 B=2000 MAE |
| --- | ---: | ---: | ---: |
| G0 | 0.023640 | 0.023632 | 0.020931 |
| G1 | 0.070548 | 0.035529 | 0.031585 |
| G2 | 0.110273 | 0.031945 | 0.030127 |

Thus M3 is essentially neutral to modestly better than M2 in G0, while the improvement becomes large as the admissibility query tightens:

- G1 MAE reduction versus M2: approximately **49.6%** at B=1400 and **55.2%** at B=2000;
- G2 MAE reduction versus M2: approximately **71.0%** at B=1400 and **72.7%** at B=2000.

This is the same qualitative regime dependence that motivated M3 after M2: preserving ambiguity was already sufficient near G0, while relative plausibility becomes increasingly important in G1/G2.

The positive bias is also reduced substantially. In G2 it falls from `+0.100882` for M2 to `+0.026067` for M3 B=1400 and `+0.023176` for M3 B=2000. M3 therefore addresses most of the M2 over-optimism in the difficult regime without changing I1.

The two M3 budgets are close. Whole-battery MAE improves from `0.030368` at B=1400 to `0.027547` at B=2000, about a 9.3% relative change in MAE for 600 additional graph trajectories. This observed difference should be described as an accuracy-cost trade-off, not as a statistically established superiority claim.

The M3-v4 construction is now **closed**. No lambda, provider weight, retained hypothesis, truncation threshold, trajectory allocation, budget, or query region may be modified against this WB.

The final evaluation manifest is:

`phase4/results/m3_v4_final_evaluation_v1/m3_v4_final_evaluation_manifest.json`.

## 10. Primary and secondary comparisons

### 10.1 Primary M3 accuracy-cost comparison

Evaluate the two predeclared M3 graph budgets on the same fresh WB:

- `B=1400`;
- `B=2000`.

Report:

- MAE;
- RMSE;
- signed bias;
- maximum absolute error;
- per-regime and whole-battery summaries;
- full-horizon and H=60..240 summaries.

The scientific question is now:

`How much graph-simulation budget is required once the public-I1-weighted latent distribution is compressed to a dominant-mass quadrature with a certified truncation bound?`

### 10.2 Theory-facing comparison

For each M3 budget report:

- retained mass `m`;
- deterministic truncation bound `1-m`;
- integer allocation `N_j`;
- worst-case Monte Carlo variance bound `(1/4) sum_j alpha_j^2/N_j`;
- worst-case Monte Carlo standard-error bound;
- weighted member dispersion across the 14 retained hypotheses.

The empirical WB error should be interpreted against both numerical components: deterministic latent truncation and finite graph Monte Carlo noise.

### 10.3 Comparison with frozen M2

Evaluate the already-frozen M2 prediction against the new M3 final WB as a replication baseline.

Do not rerun or retune M2.

Relevant graph-simulation costs are:

- M2: `27 x 100 = 2700` trajectories;
- M3 dominant quadrature, lower budget: `1400` trajectories;
- M3 dominant quadrature, higher budget: `2000` trajectories.

Thus M3 uses approximately 48% or 26% fewer graph trajectories than M2, respectively.

If M3 matches or improves M2 at either lower cost, that is an accuracy-cost improvement. If M3 is worse, the weighting/compression mechanism remains informative as a negative result.

M0 and M1 may also be re-evaluated against the same fresh WB as frozen reference baselines, with the same M0 applicability rules.

## 11. Decision outcomes

The experiment has useful outcomes in either direction.

### Outcome A: B=1400 is already stable and competitive

Interpretation: once public-I1 plausibility is concentrated and dominant mass is propagated explicitly, M3 can reduce graph cost substantially without losing predictive quality.

### Outcome B: B=2000 materially improves on B=1400

Interpretation: latent truncation is already negligible, but graph Monte Carlo precision still matters. The weighted allocation theory correctly separates this execution-noise requirement from latent-support coverage.

### Outcome C: both M3 budgets outperform or match M2

Interpretation: non-uniform public-I1 weighting plus dominant-mass quadrature provides a more efficient integration mechanism than M2's equal-weight 27-member portfolio on this benchmark.

### Outcome D: both M3 budgets underperform M2

Interpretation: local public-I1 predictive weighting does not preserve the graph-relevant ambiguity needed for accurate composition. M2 remains the stronger method and M3 closes as a negative result.

## 12. Computational accounting

Every M3 stage must emit a cost manifest.

At minimum record:

- provider-local rescoring trajectories;
- number of provider candidate points;
- selected lambda and CV score;
- provider and joint ESS/entropy;
- retained joint-hypothesis count and mass;
- deterministic truncation bound;
- per-hypothesis graph trajectory allocation;
- total graph trajectories;
- worst-case Monte Carlo variance/SE bound;
- number of processed graph requests;
- wall time;
- user/system CPU time;
- peak RSS;
- git revision;
- seed contract.

The headline comparison is an **accuracy-versus-computation** experiment under a certified latent truncation tolerance.

## 13. Guardrails

- I1 is unchanged.
- The physical graph and 15 query regions are unchanged.
- M0, M1 and M2 remain frozen.
- M3 weights use public I1 only.
- Do not use graph WB to set or tune lambda, weights, retained mass, or trajectory allocation.
- Do not weight the existing 27 M2 representatives directly.
- The top-mass threshold is frozen at `0.999` before graph execution.
- Do not treat curve points as independent replicates.
- Do not alter `B=1400` or `B=2000` after graph results.
- Do not modify the weight rule after M3 graph prediction begins.
- Preserve the PPG firewall.
- Any redesign after a failed frozen gate gets a new version.

## 14. Pilot extension target

The immediate next scientific target is therefore:

`Can public-I1-weighted dominant-mass quadrature predict graph survival at lower simulation cost than M2 while keeping latent truncation below 10^-3?`

This extends the pilot from

`M0: analytic composition`

to

`M1: one reconstructed latent process`

to

`M2: small equal-weight ambiguity-preserving ensemble`

to

`M3: cross-validated public-I1 weighting + certified dominant-mass quadrature + minimax graph-budget allocation`.
