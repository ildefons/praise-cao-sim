# PRAISE B1, Substep 2.3c: Uncertainty mathematics audit

**Date:** 2026-10-16  
**Audit status:** **COMPLETE AT EQUATION + IMPLEMENTATION CONTRACT LEVEL.** No experiment was rerun and no historical result was modified.

**Historical document:** \`praise_caise_workshop_note_v11_45(1).pdf\` (26 pages), mainly §3.1–3.2, Eq. (5), §4 Eq. (11)–(12), §5 decision comparisons, and Appendices A–C.  
**Source authority:** frozen Phase-4 M3-v4 and Stage-B contracts/runners; Phase-5 V3b FULL343 prediction and evaluation runners; Phase-5 independent WB-reference bootstrap; canonical \`phase1/sla_compliance_analysis.py\`.

**Core rule:** distinguish (1) *numerical Monte Carlo error* conditional on a fixed model, (2) *dispersion among a finite selected model set*, (3) *computational truncation of an internally weighted finite ensemble*, (4) *finite white-box-reference uncertainty*, (5) *approximation/model selection error relative to hidden truth*, and (6) *empirical variation across scenario configurations*. No single existing band covers all six.

## Summary of mathematical verdicts

| Manuscript result | Verdict | Required B1 wording |
|---|---|---|
| Eq. (5), finite-propagated-model min/max | **Algebraically valid** for exact member probabilities | Empirical range of a *specified finite propagated set*, **not** all compatible latent models, calibrated uncertainty or reliable bounds on white-box truth. Raw extrema from estimated member curves also contain MC error. |
| Eq. (11), weighted M3 estimate | **Valid estimator definition** | Conditional on the frozen finite model bank, frozen weights and allocation. Different Phase4/Phase5 support definitions. |
| Eq. (12), retained-mass \(\vert\Sigma_{\rm full}-\Sigma_S\vert\le1-m_S\) | **Exact deterministic bound** | Applies only to renormalized truncation of the **same finite, normalized Gibbs mixture**. It is not error relative to hidden truth or a posterior credible guarantee. Phase5 FULL343 has zero *within-bank truncation error* but possibly large model approximation error. |
| Eq. (A.1), variance of correlated weighted mean | **Exact algebra** | Valid for a fixed collection of random member estimates with finite covariance. Seed CRN covariance must be retained. |
| Eq. (A.2), independent-member Bernoulli variance + 1/4 upper bound | **Correct under assumptions** | Independence across member simulation streams, per-member i.i.d. Bernoulli outcome indicators, fixed model/weights/allocation. It bounds **variance**, not 95% confidence coverage or model-to-truth error. |
| Eq. (A.3)–(A.5), model spread and MC correction | **Correct expectation decomposition with unbiased member estimators** | A plug-in diagnostic of finite-support model dispersion after subtracting MC spread inflation. Positive-part clipping is an estimator choice, not a guaranteed calibrated variance of truth error. |
| Eq. (A.6)–(A.8), subtraction of MC and WB noise from squared errors | **Expectation identity valid; estimate not exact** | \(\mathbb E[D^2]=(\text{ideal method}-\text{WB truth})^2+V_{\rm method}+V_{\rm WB}\), with independent unbiased estimators. Its nonnegative plug-in estimator and square root are noisy and biased by clipping; neither is a pointwise truth-error bound. |
| Appendix A.3 model-spread vs error calibration | **Research hypothesis only** | Correlation after the fact is not a deployed accuracy estimator. Calibration would need a separately specified, held-out/scenario-stratified test, unavailable here. |
| Appendix B.1 Wilson intervals | **Conventional approximate binomial intervals** | Pointwise conditional intervals for fixed M1/Top1 model and independent per-trajectory Bernoulli outcomes. Not simultaneous across queries and not uncertainty about hidden processes. |
| Appendix B.2 M2 paired seed bootstrap | **Appropriate dependence-aware design** | Resample complete shared-seed units, not the 27 members independently. Percentile 95% is approximate, assumes independent/exchangeable seed-index units, and is pointwise. |
| Appendix B.3 M3 normal band with worst-case variance | **Useful heuristic, not an exact 95% guarantee** | \(\hat p\pm z\sqrt{\tfrac14\sum \alpha_j^2/N_j}\) has a conservative SD proxy, **but** normal coverage still needs distributional approximation; the Phase5 343-model allocation includes members with \(N_j=1\). No universal finite-sample 95% coverage follows from variance bound alone. |
| Appendix B.4 finite N200 WB Wilson | **Appropriate conditional pointwise reference uncertainty** | WB is an estimated empirical reference; selection of 'reference-certain' points by intervals does not certify 481 simultaneously correct labels or give a population decision accuracy rate. |
| Appendix B.6 precision-budget \(B^{-1/2}\) projections | **First-order planning heuristic** | Applies while support/weights and relative allocations remain fixed, with stable variance structure. Does not predict required MAE, guarantee decision resolution, or extrapolate safely across reselected supports. |
| §3.1 and Appendix C accept/reject/unresolved | **Valid defined numerical decision convention, over-interpreted** | Band lies above/below \(\beta\) means *model-conditional numerical confidence*, not true SLA assurance. A crossing band might benefit from extra simulation, but if the true model-conditional value is at the threshold, additional fixed-confidence simulation may never resolve it; sequential rechecking needs appropriate repeated-look coverage. |
| §5 WB 'reference-certain' decision agreement | **Valid descriptive evaluation on filtered reference points** | Not deployment-certified agreement, not 481 independent samples, not a joint confidence statement and not necessarily representative of all SLA conditions. |
| M2/M3 cross-query/cross-world dependence | **Omitted in some broad interpretation** | Reuse of seed indices across methods, horizons and Phase5 cells creates dependence. Phase5 registered WB bootstrap correctly reuses one resampling multiplicity vector across all 12 eligible cells. 6,660 H-query points must not be treated as independent scenario replicates. |

## 1. Exact finite-support bounds

Let the frozen finite support be \(j=1,\ldots,J\), \(w_j\ge0\), \(\sum_j w_j=1\), \(p_j\in[0,1]\). For a nonempty retained set \(S\), define
\[
m=\sum_{j\in S}w_j,\quad p_S=\sum_{j\in S}\frac{w_j}{m}p_j,\quad
p_{\rm full}=\sum_{j=1}^J w_j p_j.
\]
For \(0<m<1\), \(p_{\rm full}=m p_S+(1-m)p_{\rm omitted}\), where \(p_{\rm omitted}\in[0,1]\). Thus
\[
\boxed{|p_{\rm full}-p_S|\le1-m}.
\]
**This result is correct and does not need a new experiment.** It does **not** say \(p_{\rm full}\) is the white-box true \(\sigma_G\); it does not bound optimization error, I1 acquisition error or physical-model error.

The Pilot Top14 mass \(\simeq0.999174197\) gives a within-bank discrepancy bound \(8.25803\times10^{-4}\). The Phase5 FULL343 mass 1 gives bound 0 **only against its own seven-per-provider candidate bank**.

If we must discuss *numerical* uncertainty of a truncated estimate \(\hat p_S\), triangle inequality gives an internal statement of the form
\[
|p_{\rm full}-\hat p_S|\le(1-m)+|p_S-\hat p_S|.
\]
A numerical interval can therefore be widened by \(1-m\) for the *full finite mixture*. It still does not cover unknown graph truth. In particular a pointwise M3 normal 95% band and a deterministic \(1-m\) truncation adjustment cannot be promoted to a guarantee for the hidden system.

**M2 exception:** M2's independently chosen portfolio is *not* a truncated subset of the M3 Gibbs mixture, so “retained mass of M2” is not well defined without constructing an explicitly separate hypothetical support; that hypothetical support is not the operational M2.

## 2. Conditional Monte Carlo variance and its uncertainty meaning

For \(\hat p=\sum_j\alpha_j\hat p_j\), \(\sum_j\alpha_j=1\), the general covariance identity is
\[
V_{\rm MC}(\hat p)=\sum_j\alpha_j^2 V_j+
2\sum_{j<k}\alpha_j\alpha_k C_{jk}.
\]

- **Phase4/Phase5 M2:** 27 member graphs can reuse the same seed-index bank (common random numbers). Their member estimates are not generally independent. A paired seed-index bootstrap, using \(Y_r=\frac1{27}\sum_j Z_{jr}\) as the independent unit, preserves the intended cross-member dependence.
- **Phase4 M3 production, Phase5 FULL343:** independent seed *streams across joint members* are declared. For Bernoulli pass indicators and \(N_j\) independent trajectory replicates,
  \[
  V_{\rm MC}(\hat p)=\sum_j\alpha_j^2 p_j(1-p_j)/N_j
  \le\frac14\sum_j\alpha_j^2/N_j.
  \]
  The bound motivates the continuous \(N_j\propto\alpha_j\) budget allocation, and the frozen greedy integer allocation. It is not a confidence bound on the hidden-system sigma.
- **Nested M3 Top1/Top3/Top14:** reuse subsets of the *same* simulated rank-specific ledgers. Hence estimates at different support sizes are **correlated with each other**, even though rank-specific member streams are independent for the production M3 model. The old phrase “common-random-number ledgers” for M3 support comparisons is ambiguous: it must not override the declared independent-stream production variance formula. Separate retrospectives may deliberately use shared seeds across rank variants; refer to each contract.
- **Across \(\rho,H\), worlds and graphs:** the same archived trajectories are evaluated at multiple SLA queries/horizons, and Phase5 reuses some seed indices across cells for CRN. Pointwise SEs do not yield simultaneous 95% coverage of a whole \(\sigma(H)\) curve or 6,660 related observations.

### Confidence coverage: conservative variance is not conservative normal coverage

The old Appendix B.3 reports
\[
[\hat p-z\sqrt{V_{\rm bd}},\ \hat p+z\sqrt{V_{\rm bd}}]\cap[0,1],\qquad z=1.95996.
\]
\(V_{\rm bd}\) is an upper bound on variance. The *Gaussian coverage* is still an approximation, possibly poor for highly concentrated weights or very small \(N_j\), including cases with \(N_j=1\) in FULL343. The clipped band is a **pointwise approximate numerical interval**. It should **not** be called an exact, distribution-free 95% bound.

If a *rigorous fixed-sample* bound is wanted within the same frozen independent-member conditional model, weighted Hoeffding gives
\[
\Pr(|\hat p-p_{\rm mixture}|\ge\epsilon)
\le2\exp\!\left[-\frac{2\epsilon^2}{\sum_j\alpha_j^2/N_j}\right].
\]
Thus a valid conservative two-sided fixed-sample half-width at error probability \(\delta\), conditional on the fixed models/weights and independent trajectories, is
\[
\epsilon_{\rm H}(\delta)=
\sqrt{\tfrac12\ln(2/\delta)\sum_j\alpha_j^2/N_j}.
\]
This is an **analytical alternative**, not an experiment already performed and not necessary for the B1 report. It can be mentioned only if its assumptions are explicit; in particular it does *not* address model misspecification or arbitrary sequential stopping.

## 3. Separation of model spread from MC and white-box reference noise

Define \(p_j=E[\hat p_j]\) with zero-mean numerical errors \(\varepsilon_j=\hat p_j-p_j\), and let \(p_\alpha=\sum_j\alpha_j p_j\). The raw weighted finite-member dispersion
\[
V_{\rm raw}=\sum_j\alpha_j(\hat p_j-\hat p)^2
\]
satisfies
\[
E[V_{\rm raw}]=
\sum_j\alpha_j(p_j-p_\alpha)^2+
\sum_j\alpha_j Var(\hat p_j)-Var(\hat p),
\]
for fixed weights and unbiased member estimators, including M2 covariance terms. This validates Eqs. (A.3)–(A.4) *as an expectation decomposition*. The \(\max(0,\cdot)\) plug-in in (A.5) is a nonnegative diagnostic, **not** a calibrated confidence interval or the variance of method error relative to true graph behavior.

For an independent fresh WB reference \(\hat p_{\rm WB}\),
\[
E[(\hat p_M-\hat p_{\rm WB})^2]
=(p_M-\sigma_G)^2+V_M^{\rm MC}+V_{\rm WB}.
\]
Eq. (A.7) follows when the two estimates are independent and unbiased for their respective targets. The plug-in (A.8), with variance estimates subtracted and zero clipping, is an **estimation procedure**, not an identity for observed samples; applying a square root adds nonlinearity and bias. It measures only an *observed reference-relative discrepancy corrected for finite-simulation noise* under these assumptions, not latent identifiability.

The \((\sqrt{\hat V_{\rm model}},\sqrt{\hat V_{\rm MC}})\) pair in Appendix A is a useful **two-coordinate diagnostic**, not a single confidence band. Correlation of model spread with later empirical errors is an exploratory calibration question, and the existing pilot does not establish general calibration.

## 4. Reference-WB precision and hypothesis/decision comparisons

The original Phase4 pilot used a fresh \(N_{\rm WB}=200\) trajectory reference and its pointwise Wilson intervals, with the \(\beta=0.90\) “reference-certain” subset comprising 481 of the 555 tested H-query points. The old pointwise decision-agreement percentages are *descriptive statistics conditional on that subset*. They should not be called an independently certified 95%-reliable operational policy, and the 481 points share WB trajectories and horizons.

Phase5 defines “reference-certain” by \(\mathrm{WB}_{\rm CI,lower}\ge\beta\) or \(\mathrm{WB}_{\rm CI,upper}<\beta\) in \`run_phase5_evaluation_v3b_fullsupport.py::_decision_table\`, comparing method point estimates against those filtered reference decisions. This does not incorporate reconstruction uncertainty into policy coverage. Its separate \`run_phase5_wb_reference_bootstrap_v3b_fullsupport.py\` holds method predictions fixed, reconstructs final-WB seed-level pass vectors, and **applies the same resampling multiplicities jointly to all 12 eligible cells** (CRN preservation). That correctly addresses finite **WB reference** variability for the reported broad metrics, **not** predictive model error, uncertain model selection, stochastic method reruns or variation over unseen topologies/worlds.

A pointwise method-side numerical interval can be used to *describe* “accept/reject/unresolved relative to the frozen fitted estimate at threshold \(\beta\).” Even if its interval lies on one side, additional random simulation **can** change later point estimates; 95% nominal coverage is not deterministic stability. If one inspects intervals repeatedly and chooses to stop only once a threshold is crossed, routine fixed-sample 95% intervals do not in general retain 95% coverage under that optional stopping rule. The current old-paper Appendix C does not present a proven sequential confidence sequence or an always-valid stopping policy.

## 5. Budget planning and robustness limits

Appendix B's empirically anchored \(\widetilde W_M(B)=c_M/\sqrt B\) and \(B_{\rm req}\simeq(c_M/w^*)^2\) are **conditional extrapolations** of mean pointwise *numerical* width for the same fixed support and allocation family. The approximation can degrade if the estimator's effective support, weights, CRN coupling or allocation rules change. They do **not** say how many simulations are needed to achieve a given MAE, to pass an SLA decision reliably in the real system, or to confirm the method on other worlds. A width target smaller than the estimate's distance to \(\beta\) is not itself a guarantee of decision resolution.

The Phase5 M3 B1400 budget is spread over 343 members, some with only one trajectory; these numerical allocation properties should be reported separately from intrinsic error against white-box truth. The \(\mathcal O(B^{-1/2})\) scaling is not an excuse to recommend more simulation when the dominant error is model misspecification/poor reconstruction.

## 6. Required manuscript edits, with severity

| Location | Priority | Concrete action |
|---|---|---|
| §3.1 “largest assurance threshold” | **P0** | Replace with “model-conditional numerical lower bound/limit under a specified pointwise interval procedure.” Avoid SLA certification language. |
| §3.2 propagated-model threshold rule | P1 | Retain its exact logical statement for *ideal model predictions*, then distinguish MC-estimated extrema, finite membership, and no WB-truth guarantee. |
| §4 Eq. (11)–(12) | P1 | Retain exactly with version tags and the short convex-combination derivation; zero truncation bound for FULL343 is not zero true error. |
| §5 “reference-certain” decision accuracy | **P0** | Report the selection rule and effective correlation; qualify agreement as descriptive on conditionally selected WB points. |
| Appendix A (A.1)–(A.4) | P1 | Retain formulas with fixed weights and estimator unbiasedness/CRN covariance assumptions. |
| Appendix A (A.5) / (A.8) | P1 | Retain as nonnegative **plug-in diagnostics**; do not present positive-part corrections as unbiased or calibrated truth uncertainty. |
| Appendix A.3 (A.9) | P1 | Label empirical error calibration an untested hypothesis; separate retrospective association from a deployed estimator. |
| Appendix B.1–B.2 | P1 | Pointwise approximate Wilson and paired CRN bootstrap, with reliance on independent trajectory or shared-seed units. |
| Appendix B.3 M3 95% bands | **P0** | Replace “conservative 95% interval” with “normal-approximation 95% interval using a conservative variance bound”; distinguish small member \(N_j\), and offer fixed-sample Hoeffding alternative **only if used**. |
| Appendix B.4 WB and M0 | P1 | WB reference is finite and pointwise; M0 has no graph-MC error but has I1 acquisition/modeling uncertainty. |
| Appendix B.6 \(\sqrt B\) projection | P1 | Call planning heuristic; fix support and allocation assumptions; no MAE/guarantee extrapolation. |
| Appendix C operating procedure | **P0** | Rewrite as **diagnostic decision process**, not an established operational SLA admission certificate; mention optional stopping and possible irreducible model bias. |
| Appendix A cross-reference | P2 | Correct “MC-width column of Table 2”: printed Table 2 has no such column (previous A038). |

## 7. Remaining limitations and sign-off

The mathematical identities above have been analytically checked against the equations in v11_45 and the cited frozen scripts. **This does not add or alter scientific simulation evidence**, and is not a fresh coverage-calibration study. No uncertainty measure was shown to predict error across unseen experimental conditions.

- Do not convert any \(\sigma_G\) in B1 into first-violation/absorbing survival: the frozen definition is cumulative decided-request SLA satisfaction.
- The historical old-paper operational language should be rewritten, but Sections 3–4 and the conceptual content of Appendices A–B can mostly be retained with scope tags.
- The next independent step is **2.4, tables/figures**, including consistency among conditional numerical intervals, model ranks, recurring versus amortized local costs and WB-denominator choices. Then 2.5 infrastructure/provenance.

**Substep 2.3c: CLOSED as a mathematical and source audit, with P0 rewrite actions recorded.**
