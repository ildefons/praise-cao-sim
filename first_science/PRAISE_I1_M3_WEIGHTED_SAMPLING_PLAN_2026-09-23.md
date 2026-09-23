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

The provider weight is then

`w_i(theta) proportional to exp[-N_I1 * E_i(theta)]`

with `N_I1=100`, the trajectory count used to estimate the public I1 surface.

Why this scaling:

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

Draw one **ordered bank of 200 joint latent hypotheses** from this product distribution using one frozen RNG stream.

The ordered bank is immutable once generated:

- M3-100x20 uses entries 1..100;
- M3-200x10 uses entries 1..200.

A prepare stage must report duplicate frequency and weight concentration before graph simulation. Sampling is with replacement, so duplicate joint hypotheses are valid draws from the finite weighted distribution. They are retained and reported, never silently deduplicated.

## 6. Graph simulation allocation

Let `Z_jn(q)` be the binary trajectory-level pass indicator for joint latent hypothesis `j`, graph trajectory `n`, and query `q=(A_G,H,rho)`.

For a sampled joint hypothesis,

`p_j(q) = E[Z_jn(q) | theta_j]`.

The M3 mixture target is

`sigma_M3(q) = E_theta[p_theta(q)]`

under the frozen weighted latent distribution.

The finite estimator is

`sigma_hat_KN(q) = (1/K) sum_j (1/N) sum_n Z_jn(q)`.

### 6.1 Two equal-budget allocations

**M3-200x10**

- K=200 latent draws;
- N=10 execution trajectories per latent draw;
- graph cost = 2000 trajectories.

**M3-100x20**

- K=100 latent draws;
- N=20 execution trajectories per latent draw;
- graph cost = 2000 trajectories.

Do not enumerate the full `48^3` Cartesian product.

### 6.2 Seed nesting

To preserve the variance decomposition cleanly, different latent hypotheses should use independent graph seed streams rather than one common-random-number bank across all hypotheses.

For hypothesis `j <= 100`:

- its first 10 execution seeds are identical in M3-200x10 and M3-100x20;
- M3-100x20 receives 10 additional independent seeds.

For hypotheses `101..200`:

- only the first 10 execution seeds are used.

This gives a nested comparison while keeping execution noise independent across latent hypotheses.

The exact deterministic seed-allocation function must be frozen in the execution contract before graph simulation.

## 7. Fixed-budget variance theory

For one query `q`, assume the sampled latent hypotheses are iid draws from the frozen weighted latent distribution and graph trajectories are conditionally iid within a latent hypothesis.

Then

`Var[sigma_hat_KN(q)] = Var_theta[p_theta(q)]/K + E_theta[p_theta(q)(1-p_theta(q))]/(K*N)`.

Write

`tau^2(q) = Var_theta[p_theta(q)]`

and

`v(q) = E_theta[p_theta(q)(1-p_theta(q))]`.

At fixed graph budget `B=K*N`,

`Var[sigma_hat_KN(q)] = tau^2(q)/K + v(q)/B`.

Therefore the ordinary execution Monte Carlo term `v/B` is identical for 200x10 and 100x20, while the latent-sampling term differs:

- M3-100x20: `tau^2/100`;
- M3-200x10: `tau^2/200`.

So whenever inverse ambiguity is compositionally material, `tau^2>0`, the theory predicts lower estimator variance for **200x10** at the same graph cost.

The advantage should be smallest in G0, where M2 already showed little need for ambiguity preservation, and larger in G1/G2, where the M2 ambiguity range expanded substantially.

This gives the predeclared qualitative prediction:

`G0: 200x10 approximately 100x20`

`G1/G2: 200x10 should increasingly outperform 100x20 if latent ambiguity dominates`.

### 7.1 Empirical variance decomposition

For each frozen query, estimate:

- across-latent variance `tau^2(q)`;
- mean within-latent Bernoulli variance `v(q)`;
- the predicted fixed-budget variance for 100x20 and 200x10.

The member-level N is small, so use a bias-corrected/random-effects estimate for `tau^2` rather than the raw variance of noisy per-member means.

The theory comparison is pointwise in q. The many horizons and rho queries are **not independent samples**. Their value is that one simulated ledger yields the complete sigma family essentially for free, not that 37 horizon points multiply the effective trajectory count.

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
