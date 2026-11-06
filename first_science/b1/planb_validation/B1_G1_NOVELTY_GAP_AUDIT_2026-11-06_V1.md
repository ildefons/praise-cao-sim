# G1 — Literature and theoretical novelty audit (version 1)

**Date:** 6 November 2026  
**Status:** COMPLETED INITIAL G1 AUDIT — **REDIRECT** (do not claim present two-stage KG/Top2 or adaptive conditions are new algorithms)  
**Scope:** literature and mathematical compatibility; no new simulation, no new policy tuning or benchmark run. This is an evidence-based literature screening, not a claim of exhaustive literature coverage.  
**Roadmap:** [Frozen seven-direction plan and decision gates](B1_RESEARCH_AGENDA_FREEZE_2026-11-06_V1.md).

## 1. Exact scientific problem and the novelty burden

There are K=7 predictors and C=12 eligible (provider world, composition graph) conditions. The hidden deterministic finite table has entries Y[a,c] in [0,1], each observable at most once. The full-domain target is the equally weighted mean mu[a] = (1/C) sum_c Y[a,c], and the final recommendation after B distinct acquisitions minimizes realized terminal simple regret mu[chosen] - min_a mu[a]. Episodes initially reveal all seven algorithms on one common condition, counting seven observations toward B in {10,15,20,30,40}. The actual archive contains three worlds × four graphs. The common heuristic inference model is independent per-predictor, additive world/graph Gaussian regression; archived MAEs are deterministic reveals rather than fresh independent physical replications.

**Critical distinction:** measurement actions are the KC predictor–condition pairs, whereas terminal decision objects are the K whole-domain predictor averages. The policy chooses both *which predictor* and *which eligible condition* at each step. Condition selection must respect the equal-weight target; no adaptive weighting of conditions may secretly redefine the loss.

**G1 novelty question:** Does this precise observation and target structure demand a new algorithmic principle, theoretical result, or robust method beyond known best-arm identification, active testing/model selection, and (transductive) experimental design? Merely being a new combination of constraints does not establish such a contribution.

## 2. Closest primary literature and implications

The following are relevant primary papers, selected because they subsume major aspects of the problem. Exact applicability depends on each paper's stochastic assumptions, target and measurement cost semantics.

| Source | Already established | PRAISE difference | Implication for novelty |
|---|---|---|---|
| Frazier, Powell & Dayanik, *A Knowledge-Gradient Policy for Sequential Information Collection*, SIAM JCO (2008), [DOI](https://doi.org/10.1137/070693424); Frazier et al., *The Knowledge-Gradient Policy for Correlated Normal Beliefs* (2009), [DOI](https://doi.org/10.1287/ijoc.1080.0314) | Myopic expected improvement in the best terminal decision under Gaussian beliefs; correlated measurement alternatives. | B1 measurement is (predictor, cell), no repetition, and target is an average; however a joint action can be scored via exactly the existing posterior. | **One-step decision-aware acquisition is established**, not a novel principle. Exact one-step KG does not imply finite-horizon optimum. |
| Fiez, Jain, Jamieson & Ratliff (2019), *Sequential Experimental Design for Transductive Linear Bandits*, [NeurIPS](https://papers.neurips.cc/paper_files/paper/2019/hash/8ba6c657b03fc7c8dd4e0b2ab6-Abstract.html) | Measurement set and desired decision set can differ; information design for identifying an unmeasured target under linear assumptions. | B1's finite without-replacement matrix, fixed budget and realized simple regret differ from its noisy, fixed-confidence guarantees. | **Measurements ≠ targets is not new**; treating that distinction as our central theoretical novelty would fail. |
| Azizi et al. (2022), *Fixed-Budget Best-Arm Identification in Structured Bandits*, [IJCAI](https://ijcai.org/proceedings/2022/388) | Fixed-budget identification using structured generalization, elimination and G-optimal design; linear/GLM analyses. | B1 actions are contextual, finite without replacement and the terminal objective is average across all contexts. | Structured fixed-budget allocation already exists; a new result must isolate the important difference. |
| Kossen, Farquhar, Gal & Rainforth (2021), *Active Testing: Sample-Efficient Model Evaluation*, [ICML](https://proceedings.mlr.press/v139/kossen21a.html) | Actively select finite test points for model evaluation and correct bias from adaptive acquisition. | Standard label acquisition often reveals a reusable label for several models, whereas B1 charges each predictor–condition evaluation separately. | Adaptive test-condition selection and target-preserving debiasing are established. |
| Sawade, Landwehr & Scheffer (2012), *Active Comparison of Prediction Models*, [NeurIPS](https://papers.neurips.cc/paper_files/paper/2012/hash/92fb0c6d1758261f10d052e6e2c1123c-Abstract.html) | Choose informative test instances under fixed labeling budget to discriminate models. | Same instance label can be shared across models in usual classification setting; one B1 action only reveals one entry. | Comparing models on informative conditions is old. |
| Hara et al. (2024), *Active model selection: A variance minimization approach*, [Machine Learning](https://link.springer.com/article/10.1007/s10994-024-06603-1) | Target selection of best model by average test loss, with adaptive sampling to reduce variance of pairwise loss estimates. | Their acquisition is of a test label which can expose losses for more than one predictor; B1 has separate per-entry costs. | **Especially close decision objective:** identifying best predictor from limited tests is not new. |
| Kato & Ariu (2026), *The Role of Contextual Information in Best Arm Identification*, [JMLR vol. 27](https://www.jmlr.org/beta/papers/v27/22-0358.html) | Fixed-confidence contextual BAI: identify the best arm by mean reward *marginalized across contexts*, with lower bounds and asymptotically efficient selection. | Context may be observed/exogenous before arm selection; PRAISE chooses its finite evaluation condition with no repeats and uses fixed budget. | **Average over heterogeneous contexts is not an original problem target.** This 2026 result must be discussed prominently. |
| Cheshire & Clémençon (2026), *Best Arm Identification with Biased Contexts*, [AAAI](https://doi.org/10.1609/aaai.v40i25.39189) | BAI under mismatched source/target contextual distributions and unknown importance weights; near-optimal fixed-confidence approach under assumptions. | PRAISE's finite equally weighted target is known; its adaptive conditions change which entries are revealed, not necessarily a sampling-distribution shift. | Context-selection bias and its correction also have active existing theory. |
| Harding & Kandasamy (2025), *Balancing Performance and Costs in Best Arm Identification*, [NeurIPS](https://papers.nips.cc/paper_files/paper/2025/hash/b0dfe8236981ba84b4d98a7ed0426f0b-Abstract-Conference.html) | Explicit risk objective combining identification loss (including simple regret) and per-sample observation cost. | Per-action heterogeneous and shared computational costs for PRAISE may be more complex; B1 has fixed atomic budget. | **Cost-sensitive BAI is also established in principle**, though realistic PRAISE cost accounting remains useful applied research. |
| Xiong et al. (2024), *A/B Testing and Best-arm Identification for Linear Bandits with Robustness to Non-stationarity*, [AISTATS](https://proceedings.mlr.press/v238/xiong24a.html) | Robustness of structured BAI to departures from stationary modeling assumptions. | Our mismatch is provider–graph interaction/nonadditivity and wrong posterior uncertainty rather than temporal nonstationarity. | “Robust BAI” alone cannot be claimed as a novel direction; the robustness target must be particular and consequential. |

Additional important benchmark families already identified in [compatibility audit](B1_LITERATURE_METHOD_COMPATIBILITY_AUDIT_V0_1.md): Hoffman et al.'s BayesGap (2014), Gabillon et al.'s UGapE (2012), Russo's Top-Two posterior sampling (2016/2020), successive elimination, and linear optimal design. In particular, the B1 budget-aware Top2 heuristic is **not** Russo's TTTS: two lowest posterior means with a 50/50 coverage schedule is a separate heuristic with no transferred optimality theorem.

**Search boundary:** The absence of a paper with precisely the seven PRAISE constraints is not evidence that the formal class is unstudied. Papers listed above were checked at their primary venue/publisher pages; this is an initial close-neighbor audit, not a systematic review or a proof of absence.

## 3. Three direct mathematical checks

### 3.1 Existing one-step KG already handles a joint action

With current conditional posterior means m[a], independent parameter covariance S[a], action feature x[c], average feature v and observational standard deviation sigma, let

    s[a,c] = abs(v^T S[a] x[c]) / sqrt(sigma^2 + x[c]^T S[a] x[c])
    d[a] = abs(m[a] - min_{b != a} m[b]).

The exact Gaussian one-step KG score is

    KG(a,c) = s[a,c] * phi(d[a]/s[a,c]) - d[a] * Phi(-d[a]/s[a,c])

when s[a,c]>0, and zero otherwise. The code already implements this score on the 84-action catalogue masked by the observed entries. Enforcing without-replacement admissibility changes the feasible action set; it does not require a novel KG acquisition principle. For multiple remaining acquisitions the optimal finite-horizon policy is generally not myopic KG.

### 3.2 Without assumptions, no uniformly good sub-full-budget recommendation is possible

A simple indistinguishability counterexample is enough. Consider two predictors and C conditions. Suppose the observations made by a procedure leave one cell of predictor 1 unmeasured, and all observed entries are 1/2. Compare two completions consistent with every observation:

- World A: the unmeasured predictor-1 cell is 0, all other unobserved entries are 1/2, so predictor 1 has strictly smaller mean.
- World B: that cell is 1, all other entries are 1/2, so predictor 2 has strictly smaller mean.

The observation history is identical in both completions, so any fixed final recommendation must be wrong in at least one. For a randomized policy, its conditional recommendation distribution is identical and one of the completions yields nonzero error probability. A symmetric construction applies to any remaining unobserved cell by assigning a competing predictor's observed/remaining values suitably.

**Consequence:** The finite matrix and no-repeat rule alone offer no universal nontrivial selection guarantee for arbitrary unknown tables at B<KC. A publishable positive result needs stated structure, distributional restrictions, uncertainty calibration, margin conditions, or an explicit robust risk criterion. This is a conceptual impossibility observation, not an asserted new theorem; it is an elementary missing-data indistinguishability argument.

### 3.3 The additive surrogate excludes the very interactions that might matter

For a full 3×4 provider-by-graph table per arm, an unrestricted mean surface has 12 degrees of freedom. The additive intercept + provider + graph subspace has rank 1+(3−1)+(4−1)=6. Thus each arm has a 6-dimensional interaction component unrepresented by the mean model. The B1 8-column indicator parameterization is redundant but made Bayesian-proper by the prior. The posterior can issue precise predictions without representing interaction structure. Observed within-archive differences in allocation performance therefore do not prove calibrated uncertainty or model-independent value of adaptivity.

The broad structural formulation Y[a,w,g]=alpha[a]+beta[a,w]+gamma[a,g]+interaction[a,w,g] is not itself novel. However, **what happens to best-predictor identification when a finite no-repeat budget is allocated using a misspecified, overly confident additive surrogate** is a precise, falsifiable research question to study as G2.

## 4. Candidate novelty claims — verdict

| Proposed scientific claim | G1 verdict | Reason |
|---|---|---|
| “Adaptive validation saves evaluations compared with random/balanced tests.” | **Not an algorithmic novelty claim** | BAI and active testing already investigate adaptive sampling and model identification. |
| “Select informative conditions to distinguish predictors.” | **Already known in principle** | Active comparison/active model selection, transductive design and KG cover its essential value-of-information rationale. |
| “Separate arm selection and context selection in KG/Top2.” | **Engineering/policy architecture, not demonstrated novelty** | Standard factorization of a joint action; the new two-stage rule can differ from joint KG and has no new guarantee. |
| “Fixed, finite, nonrepeatable predictor×condition matrix with different measurement and target objects.” | **Potential niche, not yet a novel contribution** | Transductive design and active testing cover close classes; finite nonrepeatability alone is straightforward and gives no-free-lunch. |
| “Robust identification under structured model misspecification with finite, no-repeat context acquisition.” | **Most promising theoretical *question*** | Need explicit failure of strongest existing baseline, principled remedy, and nontrivial guarantee or targeted bound/counterexample relative to closest literature. Not established by current results. |
| “Operationally efficient PRAISE predictor selection under realistic graph-simulation costs.” | **Promising applied contribution** | Must show meaningful savings on fresh physical worlds and measured cost model against strong standard procedures. Novel algorithm not required. |

## 5. Falsification tests that could change this judgment

**F1 — Literature absorption test (no new simulation).** Formalize B1's action catalogue as a finite transductive design problem with an independent block vector of arm parameters, with terminal aggregate target vectors. If a standard published KG, transductive linear, or active model selection method directly instantiates the target and produces the candidate rule (plus ordinary feasible-action masking), **STOP** using that rule as a novelty claim.

**F2 — Interaction counterexample (cheap mathematical/synthetic test).** Construct two small 2×2 or 2×3 condition tables with identical available observations yet different best-average predictors; evaluate whether the proposed robustness mechanism can distinguish only with an admissible exploration guarantee. Do not overinterpret impossible identification without assumptions.

**F3 — Prior-misspecification boundary.** State exactly what distributions/tables are allowed (e.g., bounded interaction norm or bounded posterior bias), and derive either a meaningful regret guarantee or a sharp impossibility/counterexample. If the result is simply “uniform sampling is more robust when the model is wrong,” it is likely an established bias–variance tradeoff, not enough on its own.

**F4 — Applied-cost hypothesis.** A Route A claim could survive with no new algorithm, if well-designed independent worlds, strong baselines, and **measured time/compute per predictor–cell** establish a substantial practical win. If costs are unknown or new worlds infeasible, narrow or stop that route.

## 6. G1 decision and next checkpoint

**Decision: REDIRECT.**

- **STOP** the claim that current KG, Top2, their two-stage split, or the observed adaptive-vs-uniform improvement is a new best-arm algorithm.
- **CONTINUE** using PRAISE as an empirical, finite-budget evaluation platform; the results are real *conditional development evidence* and can support practical methodology.
- **CONDITIONALLY GO** toward original algorithm research only if G2 exposes a precise, nontrivial failure mode not already adequately handled by active model selection, contextual/transductive BAI or robust design, and a proposed method has a principled remedy with a falsifiable proposition.
- **NEXT:** G2 bounded misspecification assessment, beginning with the additive world×graph residual interaction and posterior calibration on the existing archive. This is a diagnosis and prospective test design, **not** permission to retrospectively optimize a new rule on the same 12 cases.
- **Parallel:** plan (but do not launch) independent-world validation and real compute-cost accounting, preserving Route A.

**Paper implication:** Route B (novel algorithm) is *not currently supported*. Route A (empirical fixed-budget adaptive validation) is more defensible, provided new-world and cost evidence can be produced, and contextual active model selection is recognized as prior art. Venue choice remains deferred.

## Source/experiment provenance

This audit extends, rather than overwrites: [prior literature positioning](B1_FIXED_BUDGET_BAI_LITERATURE_POSITIONING_2026-11-05.md), [method compatibility audit](B1_LITERATURE_METHOD_COMPATIBILITY_AUDIT_V0_1.md), [the controlled condition-selection study](B1_CONTROLLED_CONDITION_SELECTION_RESULTS_2026-11-06.md), and [the frozen project roadmap](B1_RESEARCH_AGENDA_FREEZE_2026-11-06_V1.md). No numerical results were generated or modified for G1.
