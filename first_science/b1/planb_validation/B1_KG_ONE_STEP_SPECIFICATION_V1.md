# B1 One-Step Knowledge Gradient (KG) — benchmark specification v1

**Decision / pre-result freeze:** 2026-11-05. **New, separate supplementary benchmark**; the original four-policy B1 experiment and all 4,800 episodes, bootstrap results, predictors and cost conventions remain immutable. **Status of this note: acquisition rule specified before inspecting any KG replay results.** After code preflight, this benchmark may be run on the same archived 7×12 matrix, but such a result is **retrospective development**, not independent-world validation.

## Science and primary source

Knowledge Gradient is a **one-step** Bayesian value-of-information policy, selecting the measurement expected to improve the *terminal decision value* most. [Frazier, Powell, Dayanik (2008), SIAM Journal on Control and Optimization, DOI:10.1137/070693424](https://doi.org/10.1137/070693424) and [Frazier, Powell, Dayanik (2009), correlated normal beliefs, DOI:10.1287/ijoc.1080.0314](https://doi.org/10.1287/ijoc.1080.0314).

The comparator is **one-step KG instantiated on B1's exact frozen Gaussian model**. It is not globally Bayes optimal for multiple remaining measurements and its analytical score is **model-conditional**, not a calibration of the original provider-simulator errors.

## Exact B1-compatible contract (no tuning parameters)

- Exactly the **seven original methods** and **12 original physical cells**, 84 unique actions \((a,c)\), one fixed archived cell MAE revealed once and only when selected; no new provider-world or WB simulations.
- Five **total** action budgets **10, 15, 20, 30, 40**, independently restarted at each budget (not incremental continuation). Common B1 initialization observes **all seven** methods on one same starting cell, counting seven actions.
- **All original B1 Gaussian posterior constants and terminal decision rules** are imported without modification from \`b1_budget_comparison_v1.py\`: intercept prior mean 0.17, intercept SD 0.12, world-effect SD 0.07, graph-effect SD 0.045, assumed noise SD **0.055**. Same 8D additive world/graph encoding, \`posterior\`, \`XX\`, \`V\`, and terminal \`np.argmin\` of the seven posterior cell-average means.
- The new acquisition **only** differs: choose the available \((a,c)\) that maximizes **one-step expected reduction in the best posterior mean of the terminal loss**. If more than one candidate is within the frozen B1 \`choose_tie\` score tolerance \(10^{-12}\), use **randomized tie-breaking** from the distinct RNG stream \`SeedSequence([20261105, B, starting_cell, repetition, 4])\`. No random exploratory mixing, added coverage phase, Bayesian hyperparameter retuning, model switching, forced exploration or fallback based on hidden true MAE.
- **All** 20 seeded repetitions for each of 12 initial cells at each of five budgets → **1,200 new KG episodes**, i.e. 240 per budget, and **27,600 acquired actions**. These are added to the prior 4,800 frozen episodes; do not rerun or overwrite them. No adaptive number of repetitions.
- For KG mean regret and probability of selecting the frozen reference-best, apply **2,000 starting-cell-stratified percentile bootstrap resamples**. Compare KG vs each of the **four original frozen strategies** using paired starting-cell/repetition indices, and report all five budgets plus the **equal-weight across-budget** contrast. Draw new bootstrap indices from an independently recorded seed **20262018 = 20261105+913**. Because comparisons are retrospective and multiple, all intervals are **descriptive, unadjusted**.
- Read input \`seven_method_matrix.csv\` only if its SHA-256 equals \`0b58b7b6ff7489aec169a36c88a166fdb75b88e5089f14b1a610721581bb314d\`. Read \`terminal_episodes.csv\` only if SHA-256 equals \`c219b700d55683899867051f3cf1f154cea54655853026c47fda814c887d9f12\`; enforce exactly 4,800 distinct original policy episodes. Output must be **new, nonexisting path** outside frozen B1 results. Log output and source hashes, never write to source archive.

## Exact KG equation: closed form under the *current independent per-algorithm* Gaussian B1 posterior

Let \(m_a\) be the current posterior mean of algorithm a's 12-cell average, and \(\Sigma_a\) its posterior parameter covariance. Let \(v\) be the mean 8D design vector, \(x_c\) the selected cell's vector, and \(h_a=\min_{b\ne a}m_b\).

One new observation \(Y_{ac}\) has posterior-predictive variance \(q_{ac}^2=\sigma^2+x_c^\top\Sigma_a x_c\), where \(\sigma=0.055\). Before that observation, the **updated posterior mean** of \(a\)'s full-domain mean can be represented as \(m_a+s_{ac}Z\), \(Z\sim N(0,1)\), where

\[
s_{ac} = \frac{|v^\top\Sigma_a x_c|}
                    {\sqrt{\sigma^2+x_c^\top\Sigma_a x_c}}.
\]

Only \(m_a\) moves, because B1's Gaussian models for different algorithms have independent priors and observations. The **exact one-step** information value under this model is

\[
\operatorname{KG}(a,c)
=\min(m_a,h_a)-E_Z[\min(m_a+s_{ac}Z,h_a)].
\]

Writing \(d_a=|m_a-h_a|\ge0\), this is

\[
\operatorname{KG}(a,c)=
\begin{cases}
s_{ac}\,\phi(d_a/s_{ac})-d_a\,\Phi(-d_a/s_{ac}), &s_{ac}>0,\\
0, &s_{ac}=0,
\end{cases}
\]

with standard-normal density \(\phi\) and CDF \(\Phi\). The output is nonnegative (floating point results are truncated at 0 to guard cancellation); if all gains tie, \`choose_tie\` samples among available actions.

This is equivalent to one-step expected **terminal Bayes simple-regret reduction under the assumed B1 prior** (the posterior expectation of the true minimum is conserved under future observations). It is **not** a general finite-horizon or objective-distribution optimality guarantee. The original frozen \`informed\` heuristic weights posterior variance reduction by every pair's proximity; KG instead integrates the *possible change of the identity/value of the current posterior winner*.

## Pre-performance correctness gates

Pass synthetic-only checks (no historical outcomes):
1. Compare analytic KG to independent numerical normal integration over multiple winner/challenger gap and variance cases.
2. Test KG zero/negative/nonfinite inputs, score nonnegativity and monotonicity with update SD at fixed gap.
3. Check one-action posterior mean updates against direct conjugate Gaussian refitting.
4. Check no repeated/unavailable action is selected and tie RNG is reproducible.
5. Check all five budgets and common seven-action initialization, exact action count, deterministic reproducibility.
6. Test no hidden future-value leakage: matrices identical on currently revealed entries produce identical **next** acquisition, regardless of unobserved values.
7. Fail closed on invalid budget, shape, original matrix and episode hashes.

**Stop if a test fails.** No policy tuning after inspecting archive KG outcomes. No claims of superiority before the comparison. The signed primary B1 result remains **Top2−Balanced = −0.0027652163** on its original 4,800 episodes.

## Outputs / interpretation

A separate runner, \`b1_kg_one_step_v1.py\`, writes a new versioned output directory with \`kg_terminal_episodes.csv\`, \`kg_action_history.csv\`, \`kg_budget_summary.csv\`, \`kg_vs_frozen_b1_contrasts.csv\`, \`kg_manifest.json\`. Unlike the original Top2 vs Balanced contrast, new KG-versus-Top2 intervals are not preregistered confirmation. The material scientific question is whether the simple Top2 schedule remains competitive against a **recognized terminal-value-of-information rule under equal measurement opportunities**. Do not present unequal real simulation costs as matched.

**No change to archived B1 methods, results, statistical target, or Step-0.**
