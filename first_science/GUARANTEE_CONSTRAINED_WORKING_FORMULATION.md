# Working mathematical contract: one-sided provider guarantees

Status: proposed, conditional on semantic audit. Recorded after literature review, not a validated method or result. Do not change prior frozen I1/I2 contracts or overwrite Phase-6 evidence.

## Given information

Each provider p discloses a **lower bound** b_p(a,h) on first-violation survival under explicitly declared admission region a, horizon h, workload and operating context c_p:

S_p(a,h | c_p) >= b_p(a,h).

An estimated public curve does not become a certified bound simply by renaming it. Identify how the public I1 card was constructed and what coverage, conditioning and confidence semantics it has. The historical I1 collection was provider-local W0/ParAll, not G_SEQPAR; graph-conditioned provider metrics from the new native-trace extraction are NOT automatically compatible.

## Joint complete-graph forward model

For joint provider parameters theta=(theta_A,theta_B,theta_C), a full G run yields a native trace. Extract locally defined provider observations q_p(a,h,theta;G,c) AND composed first-violation survival g(a,h,theta;G,c). Learn or approximate a multi-output map F=(q_A,q_B,q_C,g); evaluate surrogate errors on held-out full parameter configurations. All horizons from the same trajectory are correlated.

## Feasible region and objective

Only if provider guarantees are applicable to the extracted graph-conditioned observations, define:

Theta_b = {theta in Theta: q_p(a,h,theta) >= b_p(a,h) for every applicable (p,a,h)}.

Violation v_j(theta)=max(0,b_j-q_j(theta)).
Search feasibility objective: min_theta max_j v_j(theta), optionally secondary sum_j w_j v_j(theta)^2; **neither objective identifies the true generating parameters**. Never maximize positive margins or count of satisfied guarantees as a correctness target. Partial satisfaction is not contract compatibility.

The graph-survival identified interval at target (a,h) is:
[g_minus,g_plus] = [inf_{theta in Theta_b} g(a,h,theta), sup_{theta in Theta_b} g(a,h,theta)].
For SLA threshold beta, robust admission if g_minus >= beta, robust rejection if g_plus < beta, else indeterminate. Extremum over candidates or surrogate alone is an empirical witness / approximation, not a certified bound.

## Five mandatory safeguards

1. **Context validity:** match workload, SLA region, service definition, observation-origin, graph load, censoring and whether guaranteed property is conditional on requests reaching the provider. If not matched, do not enforce the inequality; either model an explicit transfer assumption or define a newly disclosed graph-conditioned interface.
2. **Statistical uncertainty:** use joint/simultaneous one-sided confidence bands for the relevant p,a,h set. Point estimates or pointwise marginal intervals do not assure joint contractual coverage. Account for correlated horizons and trajectories. Do not confuse probability of survival with confidence in estimated survival.
3. **Empty feasible set:** explicit diagnostic for misspecification/context mismatch, sampling error or insufficient forward-model expressiveness; never silently relax away violations and assert compatibility.
4. **Search/surrogate safety:** inner minimization over a subset yields an **upper** bound on the true minimum, not a certified lower guarantee. Surrogate extrema must be independently validated; a valid robust lower certificate requires justified global and approximation bounds.
5. **Distinguish population and finite data:** structural inequality feasibility with exact q differs from finite-data compatibility with sampling bands. Maintain different results tables and claims.

## Relevant prior art (not claimed novel)

- Andrews and Soares, Econometrica 2010: moment inequality inference, https://doi.org/10.3982/ECTA7502
- Bontemps and Magnac, Annual Review of Economics 2017: identified sets under moment restrictions, https://doi.org/10.1146/annurev-economics-063016-103658
- Cerone, Piga and Regruto, Automatica 2011: feasible parameter sets with bounded observation error, https://doi.org/10.1016/j.automatica.2011.08.034
- Campi and Garatti, Journal of Optimization Theory and Applications 2011: scenario chance-constrained feasibility, https://doi.org/10.1007/s10957-010-9754-6
- Stochastic-dominance / survival-function one-sided testing: https://doi.org/10.1007/s10182-022-00446-8

The novelty hypothesis is **provider-local, context-valid, horizon-dependent first-violation guarantees -> graph-level partially identified survival and task-specific minimum incremental disclosure**. Check related probabilistic contracts and reliability bounds before publishing any novelty claim.

## Mandatory next test before building a surrogate

1. Extract native provider traces from G_SEQPAR and reconstruct correct first-violation provider survival, not latency threshold compliance.
2. Compare its event, conditioning, load, SLA region and accounting origin to public I1.
3. Determine whether the inequality is transportable to G_SEQPAR from the frozen W0/ParAll provider-local acquisition. If not, state why and redesign interface assumptions explicitly without labeling new graph-level observations 'I1'.
4. Run small matched-seed study with correct survival semantics, no full 9D optimization yet.
5. Freeze all existing local results and make a second verified backup before additional studies.
