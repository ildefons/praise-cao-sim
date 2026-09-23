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

The execution order is:

1. freeze M3 provider weights from public I1 only;
2. freeze the ordered 200 joint latent draws;
3. run M3-200x10 and M3-100x20 graph prediction;
4. materialize every predicted sigma curve and theoretical variance diagnostic;
5. hash-freeze both M3 predictions;
6. only then generate a new matched-D300 WB bank on previously unused seeds;
7. evaluate M3 against that fresh WB;
8. close the M3 weighted-sampling method regardless of outcome.

Recommended final WB size:

`N_WB=200`

because the expected difference between the two equal-budget M3 allocations may be smaller than the large M1/M2 differences previously observed.

The exact new prediction and WB seed ranges must be checked against the repository's complete historical seed ledger and frozen before any M3 scientific run.

## 10. Primary and secondary comparisons

### 10.1 Primary equal-budget comparison

Compare M3-200x10 versus M3-100x20 on identical final WB:

- MAE;
- RMSE;
- signed bias;
- maximum absolute error;
- per-regime and whole-battery summaries;
- full-horizon and H=60..240 summaries.

The primary scientific question is whether **more latent coverage** improves prediction at fixed graph cost.

### 10.2 Theory-facing comparison

For each regime, compare:

- empirical `tau^2`;
- empirical `v`;
- theory-predicted estimator variance;
- observed difference between the 200x10 and 100x20 predictions.

A particularly informative outcome would be:

- near-equivalence in G0;
- increasing 200x10 advantage in G1/G2;
- increasing estimated `tau^2` across the same regimes.

That would connect the empirical allocation result directly to the variance decomposition.

### 10.3 Comparison with frozen M2

Evaluate the already-frozen M2 prediction against the new M3 final WB as a replication baseline.

Do not rerun or retune M2.

Relevant comparison:

- M2 graph cost: 27 x 100 = 2700 trajectories;
- each M3 allocation: 2000 trajectories.

If M3 matches or improves M2 at lower graph-simulation cost, that is a meaningful accuracy-cost improvement.

M0 and M1 may also be re-evaluated against the same new WB as frozen reference baselines, with the same M0 applicability rules.

## 11. Decision outcomes

The experiment has useful outcomes in either direction.

### Outcome A: 200x10 beats 100x20 as predicted

Interpretation: latent-model sampling variance is important, so under a fixed simulation budget computation should be allocated toward broader latent coverage rather than deeper replication of fewer models.

### Outcome B: allocations are essentially equivalent

Interpretation: the weighted latent distribution has already reduced between-model variation enough that execution Monte Carlo dominates, or K=100 already captures the relevant latent mass.

### Outcome C: 100x20 is better

Interpretation: per-hypothesis execution noise is more important than the simple decomposition suggested, the weighting distribution is too concentrated, or the iid assumptions are inadequate. This is scientifically informative and should trigger analysis, not post-hoc reallocation.

### Outcome D: both M3 allocations underperform M2

Interpretation: the proposed public-I1 weighting destroys useful diversity or the finite weighted approximation is misspecified. M2 remains the stronger integration method and M3 weighting is closed as a negative result.

## 12. Computational accounting

Every M3 stage must emit a cost manifest.

At minimum record:

- provider-local rescoring trajectories;
- number of provider candidate points;
- provider ESS/entropy;
- number of joint latent draws;
- duplicate count;
- graph trajectories;
- number of processed graph requests;
- wall time;
- user/system CPU time;
- peak RSS;
- git revision;
- seed contract.

The headline comparison is explicitly an **accuracy-versus-allocation at equal graph budget** experiment.

## 13. Guardrails

- I1 is unchanged.
- The physical graph and 15 query regions are unchanged.
- M0, M1 and M2 remain frozen.
- M3 weights use public I1 only.
- Do not use graph WB to set or tune weights.
- Do not weight the existing 27 M2 representatives directly.
- Do not enumerate a large Cartesian product.
- Do not treat curve points as independent replicates.
- Do not silently change the K/N allocation after graph results.
- Do not modify the weight rule after M3 graph prediction begins.
- Preserve the PPG firewall.
- Any redesign after a failed frozen gate gets a new version.

## 14. Pilot extension target

The immediate next scientific target is therefore:

`Can a public-I1-weighted latent mixture improve graph-survival prediction, and at a fixed budget B=2000 is latent breadth (K=200,N=10) more valuable than execution depth (K=100,N=20)?`

This extends the pilot from

`M0: analytic composition`

to

`M1: one reconstructed latent process`

to

`M2: small equal-weight ambiguity-preserving ensemble`

to

`M3: public-I1-weighted latent sampling with explicit accuracy-cost allocation theory`.
