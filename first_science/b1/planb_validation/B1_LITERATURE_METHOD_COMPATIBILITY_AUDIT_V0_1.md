# B1 — Literature-method compatibility audit: fixed-budget final selection (v0.1)

**Date:** 2026-11-05  
**Status:** literature and mathematical compatibility analysis only. **NO NEW POLICY IMPLEMENTATION, NO B1 RERUN, NO EXPERIMENTAL RESULT.**

## 1. Preserve exactly what B1 is

**Decision:** identify the best *whole-domain predictor* $a\in\{1,\dots,7\}$ with as few evaluations as possible, minimizing terminal **simple regret**, not cumulative rewards. Each of **84 unique** actions $(a,c)$ reveals one fixed archived cell MAE, $Y_{ac}$, where $c$ indexes 3 world roles × 4 graph types. Each action can be used at most once. The target is $\mu_a=\frac1{12}\sum_cY_{ac}$. The common evaluation initialization reveals all 7 algorithms on a single cell and **counts** those 7 observations in the known total budget $B=10,15,20,30,40$.

**Current frozen terminal model:** per-algorithm independent Gaussian regression on intercept + 3 world indicators + 4 graph indicators. The observation-noise standard deviation 0.055 and prior parameters are development heuristics; an archived cell MAE is deterministic when revealed, not a fresh draw of the simulator. All four current B1 policies use the **same posterior-mean-minimizing final decision**, and their identical 12 starting cells ×20 seeded repetitions and 2,000-replicate stratified within-archive bootstrap must remain unchanged.

**Big mismatch with textbook bandits:** measurement action = (algorithm, *which condition*), but terminal decision = algorithm alone. Arms are not repeatedly sampled iid; instead the 12 cells are a finite nonrepeatable design. An algorithm that chooses an **arm** does not automatically specify **which unobserved cell** to evaluate. Any adaptation that fills that gap is a new, explicitly versioned *B1-compatible implementation*, not an untouched canonical algorithm or inherited theory guarantee.

## 2. Sources checked and their actual theoretical claims

| Primary source | Target / central result | Transfer limitations |
|---|---|---|
| [Frazier, Powell & Dayanik (2008), **A Knowledge-Gradient Policy for Sequential Information Collection**](https://doi.org/10.1137/070693424); [Frazier et al. (2009), **Correlated Normal Beliefs**](https://doi.org/10.1287/ijoc.1080.0314) | Bayesian ranking and selection. One-step KG maximizes expected value of information under a terminal-utility model; 2008 result is optimal at **one** remaining measurement, in the infinite-horizon limit and special other cases, **not universally optimal at arbitrary finite horizons**. Correlated normal beliefs extend the class. | Closest **one-step terminal decision** objective, but a model-conditional calculation; B1 uses a misspecifiable independent-per-algorithm Gaussian surrogate over finite context cells. |
| [Hoffman, Shahriari & de Freitas (2014), **On correlation and budget constraints in model-based bandit optimization**](https://proceedings.mlr.press/v33/hoffman14.html) | **BayesGap** / Bayesian gap-bound exploration for finite evaluation budgets with correlated arms. | B1 has nonrepeatable context-specific observations, not simply repeated noisy estimates of each arm mean. Gap/confidence indices and cell-choice policy need a distinct frozen adaptation. |
| [Gabillon, Ghavamzadeh & Lazaric (2012), **UGapE**](https://papers.neurips.cc/paper_files/paper/2012/hash/8b0d268963dd0cfb808aac48a549829f-Abstract.html) | Unified gap-based exploration in fixed-budget and fixed-confidence stochastic best-arm identification, with variance extensions. | A principled challenger to top-two-mean targeting; confidence thresholds for **aggregate** algorithm performance and a feasible cell-selection rule must be defined. |
| [Russo (2016), **Simple Bayesian Algorithms for Best Arm Identification**](https://proceedings.mlr.press/v49/russo16.html) | Top-two posterior probability and posterior sampling methods; exponential posterior concentration rate can be asymptotically optimal under specified noisy repeatable measurement models. | **Not** B1's deterministic two-lowest-posterior-*means* + variance-reduction heuristic. Drawing a posterior-optimal *algorithm* does not choose a B1 cell. Asymptotic result does not imply finite B1 regret optimality. |
| [Audibert, Bubeck & Munos (2010), **Successive Rejects**](https://chercheurs.lille.inria.fr/~munos/papers/files/ABM10.pdf); [Karnin, Koren & Somekh (2013), **Sequential Halving**](https://proceedings.mlr.press/v28/karnin13.html) | Phase-wise progressive elimination with fixed-budget stochastic arm pulls and misidentification guarantees. | Clear non-Bayesian elimination controls, but B1's $B-7=3$ remaining evaluations at B10 cannot implement conventional multi-round sampling of all 7 arms. Once-only cells and non-iid context loss invalidate direct guarantees. |
| [Fiez, Jain, Jamieson & Ratliff (2019), **Transductive Linear Bandits**](https://papers.neurips.cc/paper_files/paper/2019/hash/8ba6c657b03fc7c8dd4dff8e45defcd2-Abstract.html) | Distinct sets of measurement actions and decision targets; fixed-confidence sample efficiency under linear rewards. | **Strongest formulation match**: 84 measurements, 7 target algorithm means. Theory is fixed-confidence and has different sampling assumptions from B1's known budgets and finite nonrepetition. |
| [Yang & Tan (2022), **OD-LinBAI**](https://proceedings.neurips.cc/paper_files/paper/2022/hash/4f9342b74c3bb63f6e030d8263082ab6-Abstract-Conference.html) | Minimax-optimal (within its formal assumptions) fixed-budget linear best-arm identification based on optimal design. | Relevant for exploiting design matrix $x_c$, but the theorem is not an automatic guarantee for B1's deterministic finite archive and without-replacement cell constraints. |
| [Chen, Xu & Yücesan (2025), **OCBA review**](https://www.informs-sim.org/wsc25papers/inv197.pdf) | Allocation of **replicated simulation effort** across candidate designs to increase correct selection probability. | Correct budget-aware ranking-and-selection ancestry; standard OCBA repeated-run variances/cost model differ from distinct context-MAE reveals. An adaptation may be interesting but not first-line. |
| [Kossen, Farquhar, Gal & Rainforth (2021), **Active Testing**](https://proceedings.mlr.press/v139/kossen21a.html); [Hara et al. (2024), **Active Model Selection**](https://link.springer.com/article/10.1007/s10994-024-06603-1) | Select informative test labels to estimate model accuracy / identify the strongest model efficiently; active sampling can bias naive estimators and requires correct weighting. | Close **application** analogy, but one purchased *label* can often score all predictive models on that instance. In B1 each selected action reveals exactly one **algorithm×cell** MAE. Cost/information models cannot be conflated. |

## 3. Direct mathematical observation: Knowledge Gradient is tractable for the frozen B1 Gaussian model

This is a **derived compatibility statement**, not a claim made verbatim in any cited paper, and no numerical B1 results were generated.

For each algorithm $a$, the frozen B1 posterior has an 8-dimensional parameter vector with posterior mean $\theta_a$ and covariance $\Sigma_a$. Let the mean **across the 12 cells** be the random variable $M_a=v^\top\theta_a$, with current posterior mean $m_a$. For an as-yet-unseen cell with design vector $x_c$, the predictive observation variance under the frozen Gaussian model is


$$
  q_{ac}^2 = \sigma^2 + x_c^\top\Sigma_a x_c,\qquad \sigma=0.055.
$$


If the observation is acquired, the **posterior mean** of the whole-domain performance of algorithm $a$ changes by a zero-mean normally distributed amount (before seeing the result), with standard deviation


$$
  s_{ac}=\frac{|v^\top\Sigma_a x_c|}
               {\sqrt{\sigma^2+x_c^\top\Sigma_a x_c}}.
$$


Note that $s_{ac}^2$ equals **exactly the posterior variance-reduction score** already computed in B1's Informed/Top2 code. Thus KG needs *no different posterior model* and introduces no arbitrary acquisition hyperparameters.

Let $h_a=\min_{b\ne a}m_b$ be the strongest competing posterior mean, $d_a=|m_a-h_a|$, and let $\phi,\Phi$ be the standard-normal density and CDF. One-step KG for **minimization**, the expected improvement in the best final posterior mean after observing $(a,c)$, simplifies to


$$
  \mathrm{KG}(a,c)=
  \begin{cases}
    s_{ac}\phi(d_a/s_{ac})-d_a\Phi(-d_a/s_{ac}),
       &s_{ac}>0,\\
    0,&s_{ac}=0.
  \end{cases}
$$


**Derivation:** only the posterior mean of algorithm $a$ moves when its observation is acquired; all $m_b$, $b\ne a$, stay fixed. Write $M_a^{\rm updated}=m_a+s_{ac}Z$, $Z\sim N(0,1)$, and evaluate
$\min(m_a,h_a)-E_Z[\min(m_a+s_{ac}Z,h_a)]$. The standard Gaussian positive-part identity yields the expression above. Under the assumed Bayesian model, this is **one-step expected reduction in terminal Bayes simple regret** because the posterior expected minimum true algorithm mean is a martingale under observation. This *does not* claim frequentist regret improvement on the fixed archive.

**Crucial condition:** KG is exact only as a *one-step* lookahead given the B1 assumed Gaussian model and **currently unobserved** action. For $B-t>1$ remaining measurements, the Bayes-optimal policy is a finite-horizon belief-state dynamic program, which KG generally does **not** solve. Its no-repeat B1 restriction is straightforward: consider only unobserved actions when maximizing $\mathrm{KG}(a,c)$. It still uses no hidden values.

**Implementation preflight for a prospective benchmark**, before any replay: verify against independent normal quadrature or Monte Carlo **on synthetic posterior states**, confirm KG is nonnegative, and test deterministic ties, the no-repeat mask, exact seven-observation warm start, B=10 edge behavior and expected monotonicity with $s$ at fixed $d$. Never tune or inspect its performance against the already frozen Top2 contrast while implementing.

## 4. Compatibility and priority: choose baselines by science, not availability

| Candidate | Directly optimizes final decision value? | Can operate on 84 distinct nonrepeatable actions? | Works with B=10 warm start? | What would it be called in a new study? | Proposed role |
|---|---|---|---|---|---|
| **One-step KG** | **Yes, under Bayesian model** | **Yes, with eligible-action mask** | **Yes** | KG on B1 Gaussian structured actions (exact one-step acquisition) | **Primary literature-grounded comparator** |
| **BayesGap** | Indirectly via posterior gap / confidence | Needs explicit aggregate-target and cell-selection adaptation | Likely, with care | **B1-adapted BayesGap**, not untouched canonical code | Primary **gap-based** comparator |
| **UGapE** | Targets best-arm gap and identification probability, not necessarily expected regret | Needs confidence calibration and cell-selection adaptation | Possibly, not guaranteed standard regime | **B1-adapted UGapE** | Alternative to BayesGap |
| **Top-two probability / TTTS** | Primarily posterior optimality probability/error exponent | Arm selection easy, context selection **not specified** by original rule | Possible, but small budgets and cell constraint affect behavior | **Context-adapted top-two posterior sampling** | Optional high-priority comparator if posterior probabilities can be computed robustly |
| **Sequential Halving / Successive Rejects** | Mainly misidentification probability | Requires phase and cell-selection adaptation | **Severely constrained: only 3 discretionary actions** | Explicit **B1-adapted elimination control** | Sanity check, **not** mandatory decisive baseline |
| **Linear/transductive optimal design** | Usually identification/error exponent, depends on paper | Strong structural fit, distinct design construction | Requires careful adaptation | Structured fixed-budget design benchmark | **High research priority**, implementation may be more substantial |
| **OCBA** | Commonly PCS | Repeatability/variance estimates conflict with B1 atomic observations | Not obviously | Noncanonical OCBA adaptation | Lower priority |
| **Active Testing / Active Model Selection** | Test error/model choice | Changed information and labeling cost relative to B1 | Needs substantial reformulation | Specialized application comparison | Literature positioning first |

## 5. Recommended new *separately versioned* protocol (not approved for running)

**Mandatory invariant:** keep the complete original **4-policy B1 v1** experiment, all 4,800 episodes, all budgets, the regression terminal estimator, the source/archive hashes and bootstrap results **unchanged**. This is not an invitation to rerun B1 v1 under different rules.

First produce **method specifications**, without performance comparison:

1. **KG**: the analytic one-step expected terminal improvement above, every unseen $(a,c)$ admissible, same common Gaussian posterior and terminal recommendation. No free tuning constant.
2. **One established gap method (BayesGap *or* UGapE)**: define upper/lower confidence bounds on each **aggregate** $\mu_a$, which competing algorithms are selected, and exactly how they select an unobserved context $c$. Distinguish canonical theory from adaptations.
3. **One structural benchmark**: either a transductive/linear design rule with clear assumptions, **or** simple Sequential Halving as a clearly qualified non-repeat adaptation. These two answer different questions; the choice should be justified explicitly.
4. **Optional TTPS/TTTS**: only if we can define context selection without posthoc advantage and without claiming the asymptotic proof transfers.

Before testing any method on the original archive, freeze (a) its acquisition equations and tie-breaking; (b) exact B1 observation, budget and warm-start semantics; (c) identical terminal estimator; (d) randomization/replication/bootstrap schedule; (e) no-leakage source masks; and (f) a list of allowed synthetic correctness tests.

If an already-inspected original archive is used to compare new algorithms, the result is **retrospective supplementary development** only. Any strong independent transfer claim still needs new independent environments defined without outcome-guided selection and a cost gate.

## 6. Provisional scientific conclusion

**Scientific novelty cannot rest on** the intuition that selective budget allocation is better than random/balanced allocation, since strong literature already addresses fixed-budget best-arm identification and information-directed sampling. B1's strongest defensible potential contribution is a clean **structured, finite, nonrepeatable algorithm×world×graph evaluation** formulation, reproducible measurements, and assessment of how established acquisition methods behave with heterogeneous predictor costs and a common terminal decision. This is a *research hypothesis*, not yet a demonstrated novel result.

**Decision gate:** review and approve the shortlist of comparators, beginning with KG's exact compatibility; **no policies or scientific results were changed in this audit**.
