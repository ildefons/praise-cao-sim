---
title: "End-to-End SLA Estimation from Limited Provider Disclosures"
subtitle: "Methods, Experimental Record, and Limits of Reconstruction"
author:
  - "Ildefons Magrans de Abril"
  - "Xavier Franch"
  - "Schahram Dustdar"
date: "16 October 2026"
lang: en
geometry: "margin=0.86in"
fontsize: 10pt
colorlinks: true
linkcolor: "blue"
urlcolor: "blue"
toc: true
toc-depth: 2
numbersections: false
header-includes:
  - \usepackage{booktabs}
  - \usepackage{longtable}
  - \usepackage{microtype}
  - \usepackage{amsmath}
  - \usepackage{amssymb}
  - \usepackage{graphicx}
  - \usepackage{float}
---

# Executive synthesis {.unnumbered}

In composed cloud-edge services, individual providers may advertise limited workload and SLA evidence while keeping their stochastic execution models private. The methodological challenge is to combine these separate disclosures into a prediction of end-to-end SLA satisfaction over a time horizon, without assuming access to hidden process parameters. We report the development, implementation, and evaluation of a family of methods indexed by provider information representation $I$ and integration procedure $M$, together with a simulator and a complete account of observed limitations.

We define the evaluated quantity as $\sigma_G(A,H;\rho)=\Pr[c_G(A,H)\ge\rho]$, where $c_G(A,H)$ is the fraction of **decided** composed requests that meet a specified latency-cost-quality region by time $H$. A missed latency deadline is a decided failure; requests not yet decided are excluded; zero decided requests yield compliance one. This quantity measures the probability that the composed service meets its SLA compliance target over the observation horizon $H$.

**First, the controlled pilot ([Phase I](#appendix-c-experimental-chronology-and-method-versions))** tested the original three-provider parallel graph. The original controlled pilot was promising. Against a fresh white-box reference ($N_{\mathrm{WB}}=200$: 200 new simulation runs using the true underlying model), across 555 related measurements (15 SLA conditions, each evaluated at 37 time horizons using shared simulation runs), the mean absolute errors (MAE) of a single reconstructed model (M1), a 27-member equal-weight ensemble (M2), and a Gibbs-weighted pilot M3 with 14 propagated joint models were respectively **0.18517, 0.06815 and 0.03037**. However, a retrospective cost-matched support audit found a Top1 estimator with MAE **0.02878**, slightly below the weighted Top14 estimator in that fixed pilot. The pilot therefore did not establish that multi-model averaging was necessary.

**Next, the expanded evaluation ([Phase II](#appendix-c-experimental-chronology-and-method-versions))** evaluated generalization across multiple provider configurations and composition graphs. Sixteen evaluation cases were planned (four provider configurations combined with four composition graphs). The four cases involving configuration P2 did not meet the predefined criteria for informative SLA test conditions, so they were excluded without replacement. On the remaining 12 cells, with independent $N_{\mathrm{WB}}=1000$ final white-box trajectories per cell and 6,660 related measurements (555 per case) per fully applicable method, the executed [Phase-5 V3b](#appendix-c-experimental-chronology-and-method-versions) algorithms produced MAE **0.15702** (M1), **0.13395** (M2), and **0.12189** (M3 FULL343). M3 retained the best aggregate ranking, but hard conditions still had substantial errors. Its algorithm and candidate support also changed from the pilot and from the initially registered [Phase-5](#appendix-c-experimental-chronology-and-method-versions) method. Accordingly these numbers cannot be treated as direct replications of the original 14-member method.

**Finally, the retrospective investigation ([Phase III](#appendix-c-experimental-chronology-and-method-versions))** investigates that gap, including an original-style M3 comparison, without creating a new independent holdout. Reconstructing 48 public-I1-scored candidates/provider and propagating Top14 at B=1400 on the same 12 cells gave **MAE 0.15416** (separately simulated Top1, **0.16228**), versus **0.12189** for the executed V3b FULL343. Despite Top14 retaining at least **99.64%** of its inferred joint-model weight across P1, P3 and P4, FULL343 outperformed it in **11 of 12** cells. These post-result comparisons do not isolate member count or constitute a fresh holdout. A subsequent [Phase III](#appendix-c-experimental-chronology-and-method-versions) audit reproduced pilot estimator and native parallel-graph behavior on archived seeds while documenting candidate-domain drift and the transfer of the numerical Gibbs concentration instead of its original selection rule.

Subsequent development tests revealed further limitations. On P4/G_SEQPAR, stronger reconstruction from I1 alone performed comparably to, and on average slightly better than, several richer I2 information-and-loss pipelines under matched search and graph-propagation designs. This does **not** isolate the causal utility of information quantity because fitting objectives also changed. In a separate P2/G_PAR experiment using a deterministically composed public graph region, M1, M2 and M3 achieved MAE **0.13200, 0.14058 and 0.12787**, respectively, under **unmatched** graph budgets. A privileged retrospective audit then found that the true generating provider parameters fitted the public I1 evidence better than the selected reconstructed candidates despite lying inside the search domain. This is direct evidence of a search/reconstruction deficit, not a proof of structural non-identifiability.

The overall conclusion is conditional: end-to-end SLA estimation from limited disclosure is demonstrably feasible **in some controlled cases**, but the developed finite-search integration methods have not delivered reliable prediction across the studied variations. The technical report retains favorable, negative, and inconclusive evidence and distinguishes numerical Monte Carlo precision from uncertainty about the hidden system. In practical terms, this report provides the empirical foundation for a follow-up academic paper on how to design, validate, and report credible evidence for distributed management and optimization methods in hierarchical computing-continuum systems. The goal is to identify what must be controlled or tested before a promising pilot can support broader claims of robustness.

# 1. Research problem, scope, and prior context

## 1.1 Composable offerings and information boundaries

The computing continuum spans resources and services controlled by different administrative entities. An integrator may know its own workflow or service-composition graph while observing only restricted public claims about the providers on which it depends. Physical execution is shaped by stochastic service times, queues, branch synchronization, workload and cost accumulation. Predicting the performance of composed black-box services using only their providers' advertised performance measures is not equivalent to observing the resulting end-to-end behavior.

The Composable Autonomic Offering (CAO) abstraction represents an offering as

$$
o=(G,s,\sigma,r), \tag{1}
$$

where $G$ is the composition graph, $s$ describes service objectives, $\sigma$ represents dependability or survival information, and $r$ is the realization envelope [12]. The CAO abstraction motivates predicting a useful dependability quantity, but does not, by itself, prescribe which information must be disclosed or which numerical method can produce a dependable composition estimate.

We separate these choices explicitly:

$$
\tau=(I,M), \tag{2}
$$

with **information interface** $I$ and **integration method** $M$. The interface $I$ specifies what each provider discloses. Given these separate disclosures and the known composition graph $G$, the integrator applies $M$ to estimate the composed service's end-to-end SLA probability, $\widehat\sigma_G(A,H;\rho)$. Depending on the method, this may involve reconstructing provider models and propagating their predictions through $G$. Distinct $M$ may use the same $I$; conversely an information-rich interface can require a different reconstruction objective, making the evaluated unit an **information–method pair**.

The question is not whether analytical or stochastic QoS composition exists. It does [3,8,17–19]. Rather, the specific problem is **inverse, public-evidence-constrained** composition: can an integrator combine the probability surfaces advertised by individual black-box providers to estimate the composed service's finite-horizon, end-to-end SLA probability, without access to their execution traces or true parameters?

## 1.2 Research questions and evidence categories

The program addresses four related questions:

**RQ1, feasibility and limits.** When can finite public provider disclosures support useful graph-level SLA-satisfaction prediction, and in which worlds, topologies, regimes, or query regions does prediction fail?

**RQ2, methods under a fixed interface.** How do analytical propagation, a single provider reconstruction, equal-weight reconstruction portfolios and evidence-weighted finite supports compare? Which observed differences are due to candidate search, support membership, weights or numerical allocation, and which cannot be causally separated?

**RQ3, disclosure.** Does enriching the public interface with marginal or paired temporal compliance information improve the resulting *information–loss–integration pipeline* under matched reconstruction resources?

**RQ4, provenance and decision meaning.** How reproducible are the finite results, and what do numerical Monte Carlo intervals, model spread, reference error and support-truncation guarantees actually mean for an SLA threshold?

We classify the evidence by its scientific role, rather than by the names of repository folders or successive software versions. **First, a controlled pilot ([Phase I](#appendix-c-experimental-chronology-and-method-versions))** tested the methods in a single provider world and graph; it established a promising initial result, not cross-setting reliability. **Next, the expanded evaluation ([Phase II](#appendix-c-experimental-chronology-and-method-versions))** tested multiple worlds and composition graphs using a final white-box reference held back until predictions were frozen. Its implementation was revised during development, so this is not an unchanged confirmation of the pilot method. **Finally, retrospective diagnosis and further development ([Phase III](#appendix-c-experimental-chronology-and-method-versions))** compared historical variants, investigated divergence and explored richer provider disclosures after earlier results were known. These later tests do not constitute another independent holdout. Appendix C provides the experiment-by-experiment chronology and exact method-version identifiers.

## 1.3 Scientific boundaries

This document does not establish a structural identifiability theorem. Multiple candidate models with different parameters and similar *finite empirical* I1 errors may reflect a non-injective information map, measurement noise, search limitations, model family restrictions, or some combination. The present observations cannot distinguish these causes in full generality.

# 2. Formal SLA objective and benchmark semantics

## 2.1 Request-level admissibility

For a composed request, denote latency, accumulated cost and quality by $(L_G,C_G,Q_G)$. A rectangular admissibility region is

$$
A=\{(L,C,Q): L\le\ell,\ C\le c,\ Q\ge q\}.
$$

A request is **compliant** when it is decided and its final outcome lies in $A$. The simulator records the top-level emission and, if available before simulation stop, the completion time. An on-time request is decided at completion. An uncompleted or late request is decided as a latency failure when its deadline arrives. A request whose completion and deadline are still in the future is unresolved at the current evaluation horizon. The SLA-scoring rule does not equate “unresolved” with “failed”.

Let $\mathcal D_G(H)$ be the set of top-level requests *decided* by horizon $H$, and $\mathcal C_G(A,H)\subseteq\mathcal D_G(H)$ the compliant subset. Define, with the explicitly frozen zero-decision convention,

$$
c_G(A,H)=
\begin{cases}
1, &|\mathcal D_G(H)|=0,\\[2mm]
|\mathcal C_G(A,H)|/|\mathcal D_G(H)|, &|\mathcal D_G(H)|>0.
\end{cases}
\tag{3}
$$

For required compliance fraction $\rho\in[0,1]$, the true graph-level estimand is

$$
\boxed{\sigma_G(A,H;\rho)=\Pr\{c_G(A,H)\ge\rho\}.}
\tag{4}
$$

The probability is taken over independent stochastic trajectories of the specified provider world, workload and execution graph. The horizon $H$ determines which decided requests are included in the compliance fraction. As more requests are decided, this fraction may rise or fall, so $\sigma_G(A,H;\rho)$ is **not guaranteed to decrease with $H$**. We therefore use the precise term “horizon-dependent SLA-satisfaction probability” throughout the report.

The numerical methods compute $\widehat\sigma_G^{(I,M)}(A,H;\rho)$, and the hidden world is only evaluated through a separate finite white-box reference $\widehat\sigma_G^{\mathrm{WB}}$ under experimental conditions that permit it.

## 2.2 Prediction target and evaluation reference

**What do we estimate?** For a known composition graph $G$ and an SLA query $(A,H;\rho)$, Equation (4) defines $\sigma_G(A,H;\rho)$, the probability that the composed service meets the required compliance fraction. The integrator does not know the providers' hidden stochastic execution models. It has only the information each provider discloses through interface $I$. Integration method $M$ uses those disclosures and the known graph to produce the end-to-end prediction $\widehat\sigma_G^{(I,M)}(A,H;\rho)$. **The scientific task is to assess the accuracy and limits of this probability prediction.**

**How do we evaluate it?** In the simulator, the true provider models can be used to generate an independent finite white-box reference $\widehat\sigma_G^{\mathrm{WB}}(A,H;\rho)$. We compare each method's prediction with this reference across the tested SLA queries, horizons, provider worlds and graph topologies. The hidden provider models used for final reference generation are not supplied to the methods being evaluated. Because the reference is computed from a finite number of stochastic runs, it is itself an estimate of $\sigma_G$, not an exact value. Numerical simulation error and reconstruction error must therefore be distinguished (Section 9 and Appendix A).

# 3. Provider disclosures

## 3.1 Public interface I1

Under the original public interface I1, each provider advertises a finite family of rectangular admissibility regions indexed by a target content level $\rho_r$:

$$
A_i(\rho_r)=
\{L_i\le\ell_i(\rho_r),\, C_i\le c_i(\rho_r),\, Q_i\ge q_i\}.
\tag{5}
$$

Here $L_i$, $C_i$ and $Q_i$ are the provider's latency, cost and quality outcomes. The functions $\ell_i(\rho_r)$ and $c_i(\rho_r)$ specify **numerical latency and cost limits** for each advertised index $\rho_r$. They are finite lookup mappings, not time-varying performance functions. In this simulated experiment, the framework prepares a separate I1 card on behalf of each provider and makes it available to the integrator. To construct its advertised regions, the provider-side procedure fits a joint model of private latency and cost observations (a Gaussian mixture in log latency and log cost). It draws a fixed synthetic sample from that model and, for each $\rho_r$, chooses a minimum-area rectangle containing at least that fraction of sampled outcomes, while retaining the preceding region. Consequently the regions are **nested**: when $\rho_r<\rho_r'$, $A_i(\rho_r)\subseteq A_i(\rho_r')$, so neither the latency nor the cost limit decreases. In the studied provider worlds, the quality outcome is constant at $Q_i=0.5$, with advertised limit $q_i=0.5$. Thus quality is not a varied experimental dimension, and the regions differ only in their latency and cost limits.

The index $\rho_r$ thus specifies the **target content of the fitted latency-cost model**, not a guaranteed fraction of compliant requests during an execution horizon. The latter is the separate SLA-compliance threshold $\rho_q$. Once the regions are fixed, each provider advertises an empirical probability surface

$$
\widehat\sigma_i^{I1}(A_i(\rho_r),H;\rho_q)
\approx \Pr\{c_i(A_i(\rho_r),H)\ge\rho_q\}.
\tag{6}
$$

The historical pilot used $\rho_r,\rho_q\in\{0.95,0.975,0.98333,0.99,0.995\}$ and a 5-second horizon grid up to 240 seconds, with a workload period of 0.2 seconds. Provider-card acquisition used two disjoint banks of 100 complete simulation trajectories each. The first bank (seeds 6000--6099) was used only to fit the provider's latency-cost model and construct the regions. The second bank (seeds 6100--6199) evaluated the already fixed regions. For each $(A_i(\rho_r),H,\rho_q)$, each trajectory in the second bank contributed one binary outcome: whether its decided-request compliance fraction reached $\rho_q$ by horizon $H$. Thus $\widehat\sigma_i^{I1}=n_{\mathrm{pass}}/100$ is the fraction of successful trajectories, **not** an average of raw traces, the mean of per-trajectory compliance fractions, or the fraction of compliant requests pooled across trajectories. The same trajectories are reused across regions, horizons and compliance thresholds, so the points on the probability surface are correlated. Each simulation run also supplies provider-local ledgers for all three providers.

The public I1 card includes pointwise 95\% Wilson binomial confidence intervals for each estimated SLA-satisfaction probability (the chance that a new independent provider trajectory achieves at least the required fraction $\rho_q$ of compliant decided requests for region $A_i(\rho_r)$ by horizon $H$). These intervals are disclosed as part of I1, but none of the evaluated methods M0, M1, M2 or M3 uses them. The card does **not** disclose request timestamps, hidden queue/service trajectories or provider parameters.

The provider-side procedure uses private simulation evidence to construct the finite I1 card. The integrator, by design, sees only that card. This provider-versus-integrator information boundary is essential: giving a method the hidden sample identities, generating parameters or white-box graph predictions would change $I$ and invalidate the intended inverse reconstruction comparison.

Note that I1 discloses provider-level regions $A_i$, not the graph-level SLA query region $A_G$ for the composed service. For each experimental comparison, $A_G$ is fixed and shared by the methods being evaluated.

## 3.2 Enriched I2 interfaces

The post-result I1/I2 experiments were developed in the repository's `first_science/phase6/` folder (historical [Phase-6](#appendix-c-experimental-chronology-and-method-versions)) and belong to global [Phase III](#appendix-c-experimental-chronology-and-method-versions) in this report. They retain the I1 provider regions and horizon grid and reuse the corresponding provider-local simulation evidence. What changes is the information disclosed to the integrator about how often, and how consistently, each provider satisfies its advertised regions.

**I2a: distribution of compliance across simulation runs.** Fix one advertised provider region and one evaluation horizon. In each independent simulation run, the provider handles many requests. We calculate the percentage of requests decided by that horizon that satisfy the region's latency, cost and quality limits. This gives **one compliance percentage per run**. To illustrate, suppose four runs produce 98%, 96%, 94% and 70% compliance. If the SLA requires at least 95%, two runs satisfy it and two do not. For this threshold, I1 would report only the pass rate, 2 out of 4 runs (50%). I2a would instead disclose the four compliance percentages themselves, sorted as 70%, 94%, 96% and 98%. The integrator can therefore see not only how often the SLA is met, but also how much compliance varies and how severely it can fall below the requirement. In the actual experiment, **100 independent runs**, rather than four, provide 100 compliance percentages for each advertised region and horizon. These percentages are sorted separately for every horizon, so I2a does not reveal which values at different horizons came from the same run.

**I2b: paired compliance at two horizons.** I2b includes the I2a distributions and adds pairs of compliance fractions measured in the *same* trajectory at two selected horizons. A pair such as (0.98, 0.91) means that cumulative compliance in one run declined from 98% to 91% between those horizons; the fractions still refer to all requests decided since the start, not just requests processed within the interval. For each selected interval, the published representation contains 100 such pairs. The frozen design samples intervals starting at 5 seconds and then every 10 seconds, with separations of 20, 30, 40, 50, 75, 100, 150 or 200 seconds where both endpoints fit within the 240-second horizon. The pairs reveal whether good or poor compliance tends to persist or change over time. They contain no trajectory identifiers, and the published records cannot be linked across different intervals by a shared identifier; they are not complete request histories or labelled trajectories.

**Additional disclosure in I2b-v4.** The later I2b-v4 extension publishes one more value for each selected interval: the average, across the 100 runs, of the difference between the highest and lowest cumulative compliance fractions recorded during that interval on the 5-second evaluation grid. This describes variation *inside* an interval that its two endpoint values alone cannot reveal. Individual runs' ranges and complete histories remain private. Section 4.3 explains how M2 uses I1, I2a, I2b and this additional summary to reconstruct provider models. The results appear in Section 8.3.

# 4. Integration algorithms and historical method versions

## 4.1 M0: analytical public-boundary predictor

M0 asks a worst-case question: **If every provider meets its advertised limits for a request, what limits follow for the complete service?** The advertised region $A_i(\rho_r)$ (Eq. (5)) specifies maximum latency $\ell_i$, maximum cost $c_i$ and minimum quality $q_i$. In a sequence, latencies add. In an all-required parallel join whose branches start together, latency is determined by the slowest branch. Cost adds because every required service incurs cost. The model defines composed quality as the minimum across required services. Before including processing and communication overheads, the limits are

$
\begin{aligned}
\operatorname{Seq}:&\quad
\ell=\sum_i\ell_i,\quad c=\sum_i c_i,\quad q=\min_i q_i,\\
\operatorname{ParAll}:&\quad
\ell=\max_i\ell_i,\quad c=\sum_i c_i,\quad q=\min_i q_i.
\end{aligned}
\tag{7}
$

These limits apply to a request only if all required providers respect their advertised limits. M0 applies the same rules recursively to graphs built from sequence and all-required parallel operations. For example, in $G=A\to(B\parallel C)$, the provider-only latency limit is $\ell_A+\max(\ell_B,\ell_C)$, cost is $c_A+c_B+c_C$, and quality is $\min(q_A,q_B,q_C)$. Fixed processing, network and synchronization costs or delays are included at their actual positions in the graph.

For the frozen [Phase-I](#appendix-c-experimental-chronology-and-method-versions) pilot, Source $\to$ Fpre $\to$ $(A\parallel B\parallel C)$ $\to$ Fpost, three network-data hops contribute $0.001001$ s each, a completion-control message contributes $0.001$ s, and Fpre and Fpost contribute $0.005$ s each. Thus the additional latency is $3(0.001001)+0.001+2(0.005)=0.014003$ s. The two fixed services add $0.015+0.015=0.03$ cost units, while network costs are zero. The resulting limits are $\ell_G^{M0}=0.014003+\max_i\ell_i$, $c_G^{M0}=0.03+\sum_i c_i$ and $q_G^{M0}=\min_i q_i$. These constants come from the simulator configuration and must be recalculated for other graph configurations.

Applying these rules to the advertised I1 regions gives the M0-induced region $A_G^{I1+M0}$, which need not equal the requested graph-level SLA region $A_G$. For example, M0 may calculate an $80$ ms latency limit while the requested SLA allows $100$ ms. M0 makes a prediction only when $A_G^{I1+M0}\subseteq A_G$: its calculated maximum latency and cost do not exceed the requested maxima, and its minimum quality meets the requested minimum. Otherwise it reports **not applicable**, which does not mean the service will fail. Provided the required I1 values are available, the prediction is

$$
\widehat\sigma_G^{M0}(A_G,H;\rho)
=\prod_{i\in\{A,B,C\}}
\widehat\sigma_i^{I1}(A_i(\rho),H;\rho).
\tag{8}
$$

M0 estimates the SLA probability from the providers' I1 cards; the white-box reference evaluates the requested graph-level region $A_G$ directly. With fixed cards, $H$ and $\rho$, M0 gives the same probability for every requested region containing $A_G^{I1+M0}$, even though the white-box probability can change with $A_G$. The estimate can also be wrong when the regions coincide: providers can fail on different requests, and the product in Eq. (8) does not account for those different failure sets or for execution coupling.

## 4.2 M1: one reconstructed provider process per provider

M0 estimates the end-to-end SLA-satisfaction probability (Eqs. (3) and (4)) using analytical composition rules and the probabilities advertised by individual providers. M1 follows a different approach. It reconstructs one stochastic execution model for each provider from its public I1 information, connects these models according to the known composition graph $G$, and estimates the end-to-end SLA probability through simulation. Unlike M0, M1 evaluates the requested graph-level SLA region $A_G$ directly in the simulated executions of the reconstructed system.

Each reconstructed provider is represented by three parameters:

$
\theta_i=(\mu_i,\kappa_i,\mathrm{CV}_i),
\tag{9}
$

where $\mu_i$ is the mean processing time, $\kappa_i$ is the cost per unit of processing time, and $\mathrm{CV}_i$ is the coefficient of variation of processing time, defined as its standard deviation divided by its mean. Processing times follow a gamma distribution with the specified mean and variability. This parameterization defines the family of candidate provider models used by M1, M2 and M3.

For each provider, M1 searches for parameters whose simulated I1 SLA-satisfaction probabilities resemble those publicly advertised by that provider. Candidate models are compared with the published probabilities across the advertised regions, horizons and compliance thresholds using root mean squared error (RMSE). The search uses a Tree-structured Parzen Estimator (TPE) to propose candidate parameters. It has no access to the provider's internal traces or generating parameters. Consequently, its objective is to construct a model consistent with the disclosed evidence, not necessarily to recover the provider's true implementation.

In the expanded multi-world evaluation (historical [Phase-5 V3b](#appendix-c-experimental-chronology-and-method-versions)), M1 performs seven independent TPE searches per provider, each evaluating 25 candidate configurations using 15 local simulation runs per candidate. The seven selected candidates are then reevaluated using a fresh common bank of 100 provider-local simulations. The candidate with the lowest I1 RMSE is retained for each provider. A second independent local bank is used only for diagnostics, not selection. Finally, the three selected provider models are combined and simulated within the native composition graph to estimate the requested end-to-end SLA probability. The historical [Phase-3](#appendix-c-experimental-chronology-and-method-versions)/4 implementation used a different search procedure, summarized in the method-version matrix.

## 4.3 M2: equal-weight finite model propagation

Like M1, M2 reconstructs stochastic provider models from public disclosures and simulates their composition using the known graph to estimate end-to-end SLA satisfaction. The difference is that M2 retains three reconstructed models per provider instead of one. It then simulates all $3^3=27$ combinations of the three providers' models and averages the resulting graph-level predictions with equal weights:

$$
\widehat\sigma_G^{M2}(A_G,H;\rho)
=\frac{1}{27}\sum_{j=1}^{27}
\widehat\sigma_G(A_G,H;\rho\mid\vartheta_j).
\tag{10}
$$

Here $\vartheta_j$ denotes one joint model containing a reconstructed model for each provider, and the conditional prediction is obtained by simulating that model on graph $G$ for the requested region $A_G$, horizon $H$ and compliance threshold $\rho$. Equal weighting is a design choice, not an estimate of the probability that any reconstructed model is the true provider implementation.

In the expanded evaluation across multiple provider configurations and graphs (historical [Phase-5 V3b](#appendix-c-experimental-chronology-and-method-versions)), M2 uses the same seven I1-fitted candidates per provider described in Section 4.2 and retains the three with the lowest common-bank I1 RMSE. Each provider's M1-selected model is therefore included in M2's support, and the M1 joint model is one of the 27 combinations. This selection has no explicit diversity requirement or hard I1-compatibility threshold. The historical [Phase-4](#appendix-c-experimental-chronology-and-method-versions) M2 instead selected diverse candidates and excluded the M1 anchor, as recorded in the method-version matrix.

Each of the 27 joint models is simulated for 100 graph trajectories, giving **2,700 graph trajectories per physical cell**. Shared seed indices across member simulations must be respected in numerical uncertainty estimates (Section 9.1). By retaining several provider reconstructions selected for their agreement with the public I1 evidence, M2 reduces the dependence of the graph-level prediction on a single fitted model. The hypothesis is that averaging predictions from these alternative reconstructions can mitigate errors specific to one model selection, especially when the disclosed evidence does not clearly favor a unique reconstruction.

**Reconstruction with enriched provider information.** M2 depends on the quality of the reconstructed provider models. Even when several models are retained, I1 discloses only probabilities of satisfying a finite set of compliance thresholds. We therefore investigated whether richer public evidence could better constrain provider reconstruction and improve subsequent graph-level prediction. I2a discloses the distribution of compliance across runs at each horizon, while I2b additionally discloses paired compliance fractions at two horizons within the same run (Section 3.2).

Six reconstruction variants were evaluated using the same M2 aggregation rule in Eq. (10). All use the same provider-model family and parameter domains, retain three models per provider, and propagate their 27 joint combinations with equal weights. The I1STRONG_M2 variant provides an I1-based reference under the same strengthened search budget. The variants differ in the **disclosed evidence used for fitting and the criterion used to select provider models**.

For each provider and variant, the matched search evaluates 256 parameter settings: 64 initial space-filling proposals followed by 192 adaptive proposals. Each candidate is scored with 25 provider-local simulation runs; the best 24 are rescored on a fresh common bank of 100 runs, and the best three are retained. The 27 resulting joint models are each simulated for 100 graph trajectories, giving **2,700 graph trajectories per variant and physical cell**. Search budgets and random-number banks are matched, although adaptive proposals can diverge because their fitting scores differ.

| M2 variant | Public evidence and reconstruction criterion |
|:--|:--|
| I1STRONG_M2 | Fits the full I1 surface of published probabilities across advertised regions, horizons and compliance thresholds. |
| I2AFS_M2 | Fits the I2a distributions of per-run compliance across all possible thresholds, rather than only the five thresholds published by I1. |
| I2B_M2 | Fits the joint distribution of I2b compliance pairs at two horizons within a run, weighting the eight time separations equally and windows equally within each separation. |
| I2BVAR_M2 | Uses the same I2b pair-matching loss but gives more weight to windows with larger average squared changes between endpoints; weights are normalized globally across windows. |
| I2BHIER_M2 | Uses the same I2b pairs, weighting larger endpoint changes more heavily within each region and separation, while preserving equal total weight for the five regions and eight separations. |
| I2BV4_M2 | Uses the I2b pair-matching loss and the additional public mean within-interval range (Section 3.2). The range determines fitting weights; it is not itself an additional direct fitting target. |

These variants differ not only in what providers disclose (I1, I2a or I2b), but also in how the evidence is used to fit reconstructed models. Their comparison therefore evaluates complete disclosure-and-fitting procedures, not the isolated contribution of additional information. The tests were conducted after earlier results were known, on the previously studied P4/G_SEQPAR cell, and are **post-result development evidence**, not an independent confirmation (historical [Phase-6](#appendix-c-experimental-chronology-and-method-versions); see Section 8.3).

## 4.4 M3: public-evidence-weighted finite reconstruction

M1 selects one reconstructed model per provider, and M2 averages predictions from three equally weighted models per provider. M3 instead retains a larger set of candidate reconstructions and gives more influence to those that better reproduce the provider's public I1 information. The motivation is to retain alternative explanations of the disclosed evidence without assuming they should all contribute equally.

In the expanded evaluation, **M3 uses the same seven provider candidates generated by the reconstruction procedure in Section 4.2**. No additional provider-parameter search is performed for M3. Whereas M1 selects the lowest-I1-RMSE candidate and M2 retains the three lowest-I1-RMSE candidates, M3 retains all seven and computes a separate evidence-based weight for each. All use the same gamma-process family and parameterization in Eq. (9).

To measure agreement with I1, let $\mathcal R_i$ be the advertised region, compliance-threshold and horizon combinations with $H>0$ for provider $i$. At observation $r\in\mathcal R_i$, let $p_{i,r}$ be the published probability of satisfying the SLA requirement and $q_{i,k,r}$ the corresponding probability simulated from candidate $k$. M3 uses the mean Bernoulli Kullback--Leibler (KL) discrepancy

$$
\begin{aligned}
E_{i,k}
&=\frac{1}{|\mathcal R_i|}\sum_{r\in\mathcal R_i}
d_{\mathrm B}(\widetilde p_{i,r},\widetilde q_{i,k,r}),\\
d_{\mathrm B}(p,q)
&=p\log\frac{p}{q}+(1-p)\log\frac{1-p}{1-q}.
\end{aligned}
\tag{11}
$$

The tildes indicate Jeffreys smoothing: for an empirical probability $p$ estimated from $N$ runs, $\widetilde p=(Np+1/2)/(N+1)$, and likewise for $q$ using its own number of runs. In the expanded evaluation both the published I1 estimates and the common-bank candidate estimates use $N=100$. Smoothing avoids zero or one probabilities producing undefined or infinite logarithmic discrepancies.

**Why KL rather than RMSE?** RMSE measures absolute discrepancies between advertised and reconstructed compliance probabilities, regardless of their values. However, the same absolute error can have different implications for reliability. For example, predicting 0.99 when the advertised compliance probability is 0.90 underestimates the probability of noncompliance by a factor of ten, whereas a comparable error near 0.50 has a much smaller relative effect. Bernoulli KL penalizes such discrepancies more strongly because it measures the excess expected logarithmic loss of a candidate's probability predictions. We use this property to give less weight to reconstructed models that make overconfident predictions inconsistent with the public evidence. Whether this weighting improves graph-level prediction compared with RMSE-based weighting remains an empirical question not isolated by the present experiments.

Candidate $k$ for provider $i$ receives the normalized weight

$$
w_{i,k}
=\frac{\exp[-\lambda E_{i,k}]}
{\sum_{k'}\exp[-\lambda E_{i,k'}]},
\tag{12}
$$

where $\lambda\ge0$ determines the concentration of weights: $\lambda=0$ gives equal weights, while larger values favor smaller KL discrepancies. In the original pilot, $\lambda=30$ was selected by five-fold cross-validation on the public I1 probability surface, without access to the graph white-box reference. The expanded evaluation **reused the value 30 without repeating that cross-validation**; Section 8.2 reports the consequences of that protocol difference. These Gibbs weights express relative support within a finite candidate bank; they are **not calibrated posterior probabilities** that candidates are the hidden generating models.

For a joint reconstruction $\vartheta_j=(\theta_{A,a},\theta_{B,b},\theta_{C,c})$, M3 multiplies the three provider weights:

$$
W_{a,b,c}=w_{A,a}w_{B,b}w_{C,c}.
\tag{13}
$$

This factorization concerns weights assigned to candidate provider models. It does not assume independent graph execution: queueing, request histories and branch dependencies remain coupled within the native simulation of each joint model. For a propagated support $S$, with normalized weights $\alpha_j=W_j/\sum_{k\in S}W_k$, M3 predicts

$$
\widehat\sigma_G^{M3}(A_G,H;\rho)
=\sum_{j\in S}\alpha_j
\widehat\sigma_G(A_G,H;\rho\mid\vartheta_j).
\tag{14}
$$

The **initial controlled pilot (historical M3-v4)** used a different candidate-generation procedure: 48 Latin-hypercube-derived candidates per provider rather than seven independently fitted candidates. With public-I1 Gibbs weights at $\lambda=30$, it propagated the **Top14** joint models using graph budgets of $B=1400$ or $2000$. Those 14 members held about 99.917% of the weight **within that finite inferred distribution**, not of the probability of the true provider system.

The subsequent expanded evaluation (historical [Phase-5 V3b](#appendix-c-experimental-chronology-and-method-versions)) used the seven candidates per provider described above and propagated **all $7^3=343$ joint models** with total graph budget $B=1400$. The initially registered Top14 approximation was replaced before the final graph white-box results were read because a permitted pre-graph diagnostic found that Top14 retained only 0.552 of the inferred mass in P1, 0.962 in P3 and 0.867 in P4. This preserved the candidate bank and Gibbs weights, but changed numerical propagation and therefore remains a **documented method revision**, not an unchanged test of the original Top14 method.

For any retained subset of total Gibbs weight $m_S$, omitting the remaining reconstructed models changes the exact weighted-portfolio prediction by at most $1-m_S$. The maximum difference was approximately 0.000826 for the original pilot Top14 and zero for FULL343 within its own 343-member bank; neither value bounds prediction error relative to the real composed service.

**Allocation of the graph-simulation budget.** After weighting the reconstructed joint models, M3 still needs graph simulations to estimate their individual SLA probabilities. In the expanded evaluation, all 343 joint models share a budget of $B=1400$ trajectories. Allocating the same number of runs to every model would ignore their unequal influence on the weighted prediction. Instead, M3 allocates runs to reduce an upper bound on the prediction's Monte Carlo variance.

For a propagated support $S$ with normalized weights $\alpha_j$ (Eq. (14)), let $N_j$ be the number of independent graph trajectories simulated for model $j$. Each trajectory records whether the requested compliance target is met. Assuming independent simulation estimates across joint models, the conditional numerical variance satisfies

$
\mathrm{Var}_{MC}(\widehat\sigma_G^{M3})
\le\frac14\sum_{j\in S}\frac{\alpha_j^2}{N_j},
\qquad \sum_{j\in S}N_j=B.
\tag{15}
$

For fixed models, weights and simulation counts, the bound uses the elementary fact that a Bernoulli indicator with success probability $p_j$ has variance $p_j(1-p_j)\le1/4$. Minimizing this **worst-case numerical variance bound** with a continuous trajectory budget gives $N_j=B\alpha_j$, a special case of the weighted allocation principle of Neyman (1934; Appendix D). This is not an allocation optimized for the unknown member-specific variances.

For integer counts $N_j\ge1$, adding one trajectory to member $j$ reduces the bound by $\alpha_j^2/[4N_j(N_j+1)]$. M3 starts with one trajectory per joint model and assigns each remaining trajectory to the largest reduction, with deterministic rank-based ties. This is a marginal-priority integer allocation of the kind studied by Wright (2014; Appendix D). The factor $1/4$ is common to all members and can be omitted when ranking priorities. In the executed FULL343 support, $\alpha_j=W_j$, giving the implemented rule $\Delta_j=W_j^2/[N_j(N_j+1)]$.

A separate read-only verification script `first_science/b1/verify_method_support_v0_1.py` reproduced the archived 343-member, $B=1400$ allocation counts for P1, P3 and P4; its findings are recorded in `METHOD_SUPPORT_VERIFICATION_REVIEW_2026-10-16.md` (Appendix B.1). This checks agreement between the saved allocations and the specified rule. It does **not** demonstrate improved prediction accuracy, verify every simulation trajectory or address error caused by the reconstructed provider models.

**M3 Top1 is not necessarily M1.** M1 selects by minimum I1 RMSE, while M3's highest-weight joint model is determined by the product of KL-based provider weights. More generally, comparing M3 with M2 also changes candidate coverage, weighting loss and graph-simulation allocation. An observed difference in prediction accuracy therefore does not isolate the effect of KL weighting alone.

# 5. Native simulator, graph structures, and experiment protocol

## 5.1 AICon-based simulation framework and composition extensions

The experiments use AICon (Agentic Intelligence for the Computing Continuum) [11], built on a modified fork of YAFS (Yet Another Fog Simulator) [9]. YAFS provides a Python-based discrete-event environment for simulating applications across edge, fog and cloud infrastructure, including network communication, service execution and queueing. AICon adds a management-agent layer through which agents can observe simulated system conditions and intervene in their operation.

Why use AICon rather than extend YAFS directly? The choice connects this performance-prediction testbed to the broader research programme on Composable Autonomic Offerings (CAO) [12]. In future work, management agents could use runtime observations and performance predictions to investigate **local resilience**: detecting degradation and considering changes to service offerings or compositions before operational objectives are lost. This is a direction for subsequent CAO experiments, **not a capability validated by the present results**. In particular, the prediction accuracy demonstrated here is not assumed sufficient for dependable autonomous intervention.

For the present study, the modified AICon/YAFS runtime provides service-composition mechanisms beyond individual service execution. It registers branches and their execution dependencies, tracks the progress of each composition request separately, releases a dependent branch only after the required predecessor results for that request have arrived, and emits a single result when all required branches complete. Standalone engineering probes exercise joins, isolation between concurrent composition requests and nested composition behavior. These mechanisms let us measure end-to-end service outcomes under sequential and parallel dependencies, including the effects of queueing and network delays.

A second extension introduces **stochastic instruction demand** for simulated application modules. Instead of assigning the same instruction count to every invocation, a message can carry a distribution from which the instruction count is sampled when that message is instantiated. The simulator converts the sampled instruction demand into execution time using the processing capacity of the infrastructure node executing the application module, expressed in instructions per simulation time unit (IPT). In these experiments, provider work is Gamma-distributed, with a deterministic case when the specified variation is zero [23]. Thus, successive requests can take different times on the same infrastructure, with the resulting variation interacting with queueing and composition dependencies.

The expanded [Phase-5](#appendix-c-experimental-chronology-and-method-versions) evaluation (Phase II) tests the prediction methods beyond the initial single-world, single-graph pilot, across several service-composition graphs $G$ and provider worlds. Here $G$ denotes the **logical dependencies among provider services**. The battery considers four fixed three-provider graphs: fully parallel, fully sequential, and two mixed sequence/parallel structures. For each provider world, the four compositions use the same physical infrastructure and provider placements. Only the execution dependencies among the providers change. Periodic arrivals trigger stochastic provider services, with native queueing, service cost and network delays. The experiment covers these four structures, rather than arbitrary nested service graphs; Section 5.2 describes the provider-world and SLA-query variations.

The four frozen dependency maps are:

| Logical graph | A predecessors | B predecessors | C predecessors | Reading |
|:--|:--|:--|:--|:--|
| G_PAR | none | none | none | $A\parallel B\parallel C$ |
| G_SEQ | none | A | B | $A\to B\to C$ |
| G_SEQPAR | none | A | A | $A\to(B\parallel C)$ |
| G_PARSEQ | none | none | B | $A\parallel(B\to C)$ |

The simulator can also represent device power consumption and the quality of a service's output. In this evaluation, the power-consumption parameter (WATT) is set to zero for every simulated device. AICon can vary output quality according to the fraction of an application's required instructions that are executed, but here each module executes its full instruction demand, so this mechanism does not introduce quality variation. Although the SLA objective includes latency, cost and quality $(L,C,Q)$, the experiments primarily investigate latency and cost, not changes in energy consumption or output quality.

## 5.2 Experimental design

To evaluate the prediction methods under different conditions, we considered four provider configurations (P1–P4) and the four service-composition graphs introduced in Section 5.1, giving 16 planned test cases. For each case, preliminary simulations using the underlying provider models were used to select SLA requirements suitable for evaluating prediction accuracy. This preliminary selection, called Step-0, was intended to avoid test conditions that were insufficiently informative. All four cases involving provider configuration P2 failed this selection and were excluded without replacement, leaving 12 cases for evaluation.

For each retained case, we evaluated 15 SLA conditions over 37 observation horizons, from 60 to 240 seconds in steps of five seconds. This gives 555 probability estimates per case and 6,660 across the 12 cases. These measurements are related because different SLA conditions and horizons can be evaluated using the same simulation trajectories.

The prediction methods received the published provider information and the composition graph, but not the underlying provider models. Their predictions were recorded before being compared with a separate reference generated from 1,000 new simulations of each composition using its actual provider models. This reference, which we call *white-box*, provides an independent estimate of the SLA satisfaction probability against which prediction accuracy can be measured.

## 5.3 Evaluation safeguards and reproducibility

As summarized in [Appendix C](#appendix-c-experimental-chronology-and-method-versions), the research progressed from a controlled pilot (Phase I) to a broader evaluation (Phase II) and subsequent retrospective investigations (Phase III). Here we focus on how the expanded evaluation separated predictions from their reference results, what the recorded evidence verifies, and which reproducibility limitations remain.

To evaluate prediction accuracy, the predictions must be recorded before the reference results used to assess them become available. For each of the 12 eligible test cases, the methods first estimated end-to-end SLA satisfaction using the information published by the providers. These predictions were then fixed, before a separate set of simulations using the underlying provider models generated the reference probabilities. This separation allowed the predictions to be evaluated without using the final reference results to construct them.

A subsequent audit examined whether this separation was supported by the saved experimental records. For all 12 cases, the saved prediction files matched the hashes recorded when predictions were frozen, and the final-reference records linked back to that same frozen prediction set.

The methods and procedures also changed during development. Provider-model reconstruction and the integration of reconstructed models were revised in response to earlier diagnostics, before the final reference results were examined. Some engineering checks were completed after scientific experiments had already begun. Appendix C identifies these revisions and their scientific roles, so the expanded evaluation should not be interpreted as an unchanged test of the original plan. The repository retains source versions, simulation configurations and verification records, but the exact AICon/YAFS software state used in every historical run has not been fully established. Reference [23] identifies the audited AICon checkout; complete bitwise reproduction of the original runs is therefore not claimed.

# 6. Controlled pilot (Phase I)

The controlled pilot (Phase I) provided the first evaluation of the prediction methods using a single provider configuration and composition graph. It established an initial comparison of their prediction accuracy under fixed experimental conditions. The results also motivated the broader evaluation presented in the following section. As detailed in Appendix C, the pilot and subsequent evaluations involved different method versions and therefore serve distinct scientific purposes.

## 6.1 Construction of the pilot reference

The pilot evaluated one fixed service composed of three providers operating in parallel, with a new request generated every 0.2 seconds. To measure prediction accuracy, we needed reference probabilities for the actual composed service. We therefore simulated it repeatedly using the underlying provider models, which were not available to the prediction methods. Each simulation produced request outcomes from which we could assess end-to-end SLA compliance at different observation horizons. The provider models and their published I1 information remained fixed throughout the pilot.

The simulation outcomes could be assessed against many different SLA requirements, so we first had to choose which requirements to test. In the original pilot, we used the advertised provider limits as a starting point. We combined them using M0's aggregation rules (Section 4.1): for this parallel graph, the baseline latency is the largest provider latency plus fixed delays, the costs are added together with fixed costs, and the baseline quality is the lowest provider quality. This defines the baseline SLA region $A_G^{\rm base}(\rho)=A_G^{I1+M0}(\rho)$. We then scaled its latency and cost limits by a factor $\gamma$, leaving the quality limit unchanged:

$$
A_G(\gamma,\rho)
=\{L_G\le\gamma\ell_G^{\rm base}(\rho),\
C_G\le\gamma c_G^{\rm base}(\rho),\
Q_G\ge q_G^{\rm base}(\rho)\}.
\tag{16}
$$

The scaling factor specifies the difficulty of the requested SLA: $\gamma>1$ allows more latency and cost, whereas $\gamma<1$ imposes tighter limits. We combined three such difficulty levels with five compliance thresholds $\rho$, giving 15 SLA conditions. Each condition was evaluated at 37 observation horizons, from 60 to 240 seconds, using the same bank of $N_{\rm WB}=200$ independent simulation trajectories. For each trajectory and horizon, we calculated the fraction of decided requests satisfying the requested SLA region. The reference probability was the proportion of trajectories in which that fraction reached the required threshold $\rho$. Because the same trajectories were evaluated repeatedly, these reference measurements are related.

Using M0's aggregation rules to choose the SLA test conditions is separate from using M0 to predict SLA satisfaction. The reference probabilities were obtained from simulations of the actual composed service, independently of M0's predictions.

## 6.2 Prediction errors and historical cutoff diagnostic

Table 1 compares the prediction errors of the four methods against the pilot's simulation-based reference probabilities:

**Table 1.** Pilot prediction errors, measured against the simulation-based reference. MAE is mean absolute error; RMSE is root mean squared error. The applicable measurements differ for M0.

| Method, pilot | Graph trajectories | Applicable points | MAE | RMSE | Signed bias |
|:--|--:|--:|--:|--:|--:|
| M0, applicable subset | 0 | 333 | 0.57204 | not included in principal comparison | -0.57204 |
| M1 | 100 | 555 | 0.18517 | 0.23074 | +0.18517 |
| M2, 27 equal members | 2,700 | 555 | 0.06815 | 0.09414 | +0.04737 |
| M3 pilot Top14, $B=1400$ | 1,400 | 555 | **0.03037** | 0.03578 | +0.02824 |
| M3 pilot Top14, $B=2000$ | 2,000 | 555 | **0.02755** | 0.03306 | +0.02447 |

*MAE, RMSE and bias are computed against the finite WB reference. Positive bias means optimistic prediction. M0 has a different applicable query set (9/15 queries, 333 horizon points), so its row must not be ranked directly against all 555-point methods. The main M3 graph-propagation budget B=1400 is 48.15% smaller than M2's 2700 trajectories, **not** proof of smaller end-to-end computational cost including provider fitting. The M0 RMSE value is deliberately not invented where the archived review does not report it as a reconciled principal comparison.*

As a **secondary historical diagnostic**, the pilot applied an arbitrary cutoff $\beta=0.90$ to predicted and white-box-referenced SLA-satisfaction probabilities and compared the resulting yes/no labels. This cutoff was **not a contractual SLA requirement**, and the diagnostic was not part of the main probability-estimation objective. The audit used reference-WB pointwise Wilson intervals to identify **481 reference-certain** query/horizon points among 555. Only **274** were M0-applicable and reference-certain. The historically observed agreements were **33.94%** (M0 on 274), **37.63%** (M1), **86.07%** (M2), **96.47%** (M3 B1400), and **97.09%** (M3 B2000), with the latter four computed on 481 points. These percentages are **descriptive conditional agreements against a finite WB reference**, not calibrated real-world admission success rates or independent-scenario accuracy estimates.

The pilot's M3 production errors were substantially smaller than those of M1/M2 in this exact world and graph. That is a genuine, archived numerical observation. It does not demonstrate the same numerical advantage in worlds with altered provider demand or different logical dependencies.

## 6.3 Retrospective support and weighting

A later frozen pilot Stage-B audit compared several estimators at matched total $B=1400$ in the same world:

| Retrospective pilot estimator | MAE | RMSE | Bias |
|:--|--:|--:|--:|
| Top1 B1400 | **0.02878** | 0.03406 | +0.02498 |
| Uniform14 equal-allocation B1400 | 0.05490 | 0.06570 | +0.05362 |
| Weighted14 equal-allocation B1400 | 0.04222 | 0.05016 | +0.04066 |
| Weighted14 production-allocation B1400 | 0.03037 | 0.03578 | +0.02824 |

Using the **same 14 model members and the same equal-allocation ledgers**, weighted versus uniform averaging is the cleanest isolated *weighting* contrast. However, the production versus equal-allocation comparison also changes seed/trajectory allocation; its difference is descriptive rather than a clean causal isolate. Top1 does slightly better than production weighted14 on this same retrospective fixed-world matched-budget test, which defeats any claim that *retaining more models is intrinsically necessary for point accuracy*.

The historical operational readouts also reported Top1 B100 and Top3 B300 MAEs near 0.0399 and 0.0401, respectively, but the direct underlying first-100 source arrays have not yet been independently reconciled in the B1 checks. They remain **reported historical numbers, not upgraded to primary independently checked evidence**.

## 6.4 Hidden-parameter audit and restricted cost frontier

The retrospective pilot Table 4 compared hidden generating parameters with M1 and M3-Top1 surrogate parameters and public-I1 reconstruction losses. The archived values were independently reconciled. Their discrepancies, including notably different Provider C reconstructions, show that **good graph prediction can co-occur with very poor recovery of hidden parameters in this one pilot**. They do not prove the public interface cannot identify those parameters in principle.

The historical Figure 2 labeled a curve the “nondominated” recurring-cost/MAE frontier while plotting only chosen primary prospective implementations. In the same reported two-coordinate cost plane, the retrospective operational Top1 at B100/MAE 0.0399 dominates M1 at B100/MAE 0.1852. Thus the original line is **not** the nondominated frontier over all reported operating points; it can only be described as the frontier of the *selected prospective primary set*, or it must be redrawn and annotated with retrospective status and additional provider-construction cost. This first B1 draft does not reuse the misleading frontier graphic.

# 7. Expanded evaluation (Phase II)

## 7.1 Eligibility and exact prediction population

[Phase-5](#appendix-c-experimental-chronology-and-method-versions) planned 16 physical world-by-graph cells. Under the Step-0 eligibility/confirmation protocol, the four cells in world P2 failed. The remaining **12** cells cover worlds P1, P3, P4 across G_PAR, G_SEQ, G_SEQPAR and G_PARSEQ. Each has 15 frozen SLA queries, evaluated at 37 horizons; each has a distinct fresh $N_{\mathrm{WB}}=1000$ graph reference.

There is **no estimate for the preregistered P2 component of the [Phase-5](#appendix-c-experimental-chronology-and-method-versions) directional heterogeneity contrast**. The later induced-public-region P2 study used a different query design and cannot be substituted into this missing prospective cohort.

## 7.2 Executed V3b method comparison

The [Phase-5](#appendix-c-experimental-chronology-and-method-versions) evaluation used V3b-selected candidate banks: **M1 = one joint model, M2 = 27 equal-weight joint members, M3 = FULL343 weighted joint members**. The independently checked saved pointwise metrics are:

| [Phase-5](#appendix-c-experimental-chronology-and-method-versions) executed V3b | Evaluated points | Graph trajectories/cell | MAE | RMSE | Signed bias |
|:--|--:|--:|--:|--:|--:|
| M0 on applicable subset | 1,776 | 0 | 0.41874 | 0.45392 | -0.41808 |
| M1 | 6,660 | 100 | 0.15702 | 0.22588 | +0.14968 |
| M2 | 6,660 | 2,700 | 0.13395 | 0.19045 | +0.10094 |
| **M3 FULL343** | **6,660** | **1,400** | **0.12189** | **0.18081** | **+0.06511** |

![Phase-5 aggregate MAE from verified frozen V3b pointwise results. The full 12-cell eligible battery contains 6,660 related SLA measurements (across conditions and time horizons) per model. Different graph budgets apply: M1 100, M2 2,700 and M3 1,400 trajectories per cell. M0 is omitted because its applicable subset is different.](figures/phase5_aggregate_mae_v0_1.svg){width=95%}

These are aggregate scores over the **12 eligible physical cells only**, not a population-generalization estimate. No method dominates all conditions. The remaining MAEs, even for M3, are substantial relative to probabilities bounded by one. The positive aggregate biases for reconstructed methods indicate a systematic tendency towards overprediction within this eligible design, though their magnitude varies with the condition.

Because M0 is defined on a smaller and selected applicable set, its aggregate MAE cannot be directly compared to the all-query rows. Moreover M1/M2/M3 have sharply different graph simulation budgets, so the aggregate ranking does not isolate simulation efficiency at equal cost, nor does the pre-WB change from Top14 to FULL343 permit a direct unchanged-algorithm replication of the September pilot.

## 7.3 Topology and provider-world effects

The prospectively specified topology statistic for each method and provider world was

$$
\Delta_P^M =
\operatorname{MAE}_M(P,G_{\mathrm{SEQ}})
-
\operatorname{MAE}_M(P,G_{\mathrm{PAR}}).
\tag{17}
$$

The original directional masking hypothesis anticipated $\Delta_P^M>0$. The completed analysis did **not** yield that sign consistently across the eligible worlds: P1 differed in sign from P3/P4 for the examined contrast. It is therefore not supported as a universal or robust rule by this evaluation. A second registered heterogeneous-minus-symmetric contrast required P2 and was **not estimable** after Step-0 exclusion. The two other graph ASTs offer mechanistic triangulation but do not constitute a clean factorial manipulation separating workload shift from aggregation structure.

The 6,660 measurements reuse simulation trajectories across SLA conditions and time horizons, so they are not independent experiments. They cannot be treated as 6,660 independent physical deployments when assessing variation across provider configurations. A WB-reference bootstrap resamples the **complete trajectory/seed index** jointly across horizons, queries and shared-seed cells, keeping method predictions fixed. It addresses finite-$N_{\mathrm{WB}}$ reference fluctuation, **not model-selection uncertainty or future-world robustness**.

The scientifically material result is twofold: a weighted finite ensemble maintained a favorable aggregate *ranking* among the executed methods, and its **absolute prediction remained too inaccurate in several difficult regions** to claim dependable generic SLA estimation.

# 8. Retrospective investigation (Phase III)

[Phase III](#appendix-c-experimental-chronology-and-method-versions) brings together original-method comparisons on the previously inspected [Phase II](#appendix-c-experimental-chronology-and-method-versions) reference, D0--D9 pilot–battery forensic checks, and related post-result exploratory investigations. The latter retain their historical experiment labels and do not provide a new independent holdout.

## 8.1 Original-style M3 transfer to the Phase II battery

To address the missing comparison with the original M3, a **retrospective** experiment reconstructed the originally registered [Phase-5 V2](#appendix-c-experimental-chronology-and-method-versions)-style M3 method across all **12 Step-0-eligible physical cases** (P1, P3 and P4, each on four graph structures). This experiment was designed **after** the earlier [Phase-5 V3b](#appendix-c-experimental-chronology-and-method-versions) reference outcomes had been inspected. It reused the existing frozen 15 SLA queries per cell, 37 scored horizons (60 to 240 seconds), and N=1000 final white-box reference per cell. P2 was neither repaired nor reintroduced.

For each provider in each eligible world, the registered V2-style **48-point nonadaptive LHS** was sampled within the frozen search domain and scored using the public **I1** surface and frozen N=100 local-rescore bank. Jeffreys-smoothed Bernoulli-KL energies with $\lambda=30$ produced provider-wise Gibbs weights, whose products defined the $48^3=110{,}592$ possible joint models. The 14 highest-weight combinations were propagated with **B=1400 graph trajectories per case**, allocated using the historical integer minimax variance-bound rule. The highest-weight **Top1 was separately simulated at B=1400**. All 12 retrospective predictions were frozen before the retrospective code read the existing white-box result. The earlier seven-fit **V3b FULL343** remains an unchanged comparator. This re-instantiates major registered V2 M3 rules, but is **not** a bit-for-bit reproduction of the September [Phase-4](#appendix-c-experimental-chronology-and-method-versions) pilot.

| Method on 12 eligible [Phase-5](#appendix-c-experimental-chronology-and-method-versions) cases | Scored points | MAE | RMSE | Signed bias |
|:--|--:|--:|--:|--:|
| **Executed [Phase-5 V3b](#appendix-c-experimental-chronology-and-method-versions) FULL343** | 6,660 | **0.121890** | **0.180806** | +0.065105 |
| Retrospective original-style Top14 | 6,660 | 0.154155 | 0.212843 | +0.044867 |
| Retrospective original-style Top1 | 6,660 | 0.162280 | 0.225373 | +0.054562 |

Top14 retained mass within the reconstructed 48-per-provider joint bank was **0.996404 (P1)**, **0.996771 (P3)** and **0.998925 (P4)**. Applying the omitted-weight bound stated in Section 4.4, the *full-bank versus truncated-bank expectation* discrepancy is at most 0.003596, 0.003229 and 0.001075, respectively. This bound does **not** cover graph-simulation noise and does **not** guarantee accuracy relative to the true white-box composition. High internal support coverage coexists here with material external prediction error.

| Provider world | FULL343 MAE | Top14 MAE | Top1 MAE |
|:--|--:|--:|--:|
| P1 | 0.17326 | 0.21172 | 0.21149 |
| P3 | 0.07169 | 0.12659 | 0.14299 |
| P4 | 0.12073 | 0.12415 | 0.13237 |

| Graph | FULL343 MAE | Top14 MAE | Top1 MAE |
|:--|--:|--:|--:|
| G_PAR | 0.13586 | 0.20183 | 0.21773 |
| G_PARSEQ | 0.11016 | 0.14450 | 0.14318 |
| G_SEQ | 0.14624 | 0.14642 | 0.16105 |
| G_SEQPAR | 0.09530 | 0.12387 | 0.12716 |

FULL343 achieves lower MAE than original-style Top14 in **11 of the 12 cells**, while original-style Top14 beats its separately simulated Top1 in **8 of 12**. The advantage is not homogeneous. **P3/G_PAR contributes 49.3%** of the aggregate Top14-minus-FULL343 MAE gap (0.25108 versus 0.06001), while **P3/G_SEQ reverses the ranking** (0.08302 for Top14 versus 0.11633 for FULL343). Removing P3/G_PAR still leaves a mean FULL343 advantage of 0.01783 across 11 cells; P4 is close to a tie.

These results **do not establish that a larger ensemble causes better predictions**. The 48-point LHS and seven-fit V3b reconstructions change proposal/fit procedures, model selection and support weights, and **equal graph budgets do not imply equal total reconstruction cost**. The 6,660 scored query-horizon points are related observations, not independent real-world experiments. The methods were compared retrospectively against an already studied reference, not a fresh holdout.

The supplied result archive passed **316 independently recomputed numerical and SHA-256 checks, with zero failures**. This includes 12/12 global prediction-manifest links, all included model-prediction hashes, provider weight normalization, recovery of the Top14 from all $48^3$ joint products, and pointwise/error table reconciliation. The comparator reproduces the earlier FULL343 MAE 0.121890. The archive does **not** include 12 Top14 member-curve files or raw graph trajectory ledgers, so this is numerical/artifact verification, **not an independent bitwise replay**.

## 8.2 Pilot–battery divergence tracing

This [Phase III](#appendix-c-experimental-chronology-and-method-versions) forensic control tests what was preserved when progressing from the [Phase I](#appendix-c-experimental-chronology-and-method-versions) controlled pilot to the [Phase II](#appendix-c-experimental-chronology-and-method-versions) expanded battery. It uses archived records and sampled replay trajectories, not a new prospective accuracy test.

**The estimator and parallel-graph engines were reproduced.** The original public-I1 candidate curves yield Gibbs weight differences no larger than 2.78e-16 when recomputed by the newer helper. All 14 pilot joint models, their order, retained mass 0.999174197017, and their B1400 allocations agree. Using the frozen original models and matching IPT=10^6, the newer G_PAR implementation reproduced the original G0 native ledgers across all 14 archived member subsets. Ranks 1–9 used two seeds each (2,398 requests/rank); ranks 10–14 had only one archived trajectory each (1,199 requests/rank). Changing the numerical provider-IPT gauge to 10^9 caused small continuous changes, but no completion-status changes. For ranks 10–14, **zero of 555 original-pilot query-horizon SLA predictions changed**, even at the new gauge. The entire weighted B1400 pilot and its 14-rank SLA aggregate were **not** resimulated.

**The reconstruction procedure did change.** The same 48 normalized Latin-hypercube coordinates were retained for each provider, but physical parameter bounds changed and every new provider-world combination selected a different highest-weight candidate index. The original pilot selected Gibbs `lambda=30` by blocked five-fold cross-validation on public I1. The battery and original-style retrospective carried over the *value* 30 rather than repeating that selection rule. Reapplying the original rule retrospectively gives:

| World | Public-I1 CV-selected lambda | Used lambda | Best held-out provider KL | Provider KL with lambda=30 | Relative KL increase |
|:--|--:|--:|--:|--:|--:|
| Original pilot | 30 | 30 | 0.126042 | 0.126042 | 0% |
| P1 | 3 | 30 | 0.099806 | 0.124984 | +25.23% |
| P3 | 5 | 30 | 0.082610 | 0.158658 | +92.06% |
| P4 | 20 | 30 | 0.090682 | 0.098781 | +8.93% |

These scores measure how well the models reproduce each provider's advertised probability surfaces, **not** the composed-service SLA probability. We have not simulated alternative graph models under the new lambdas, so the CV result identifies a protocol deviation, **not a demonstrated cause of graph error**. The pilot's adaptive 99.9%-mass rule gave K=14; on the new model banks the same rule would require K=19 (P1), K=22 (P3), and K=15 (P4), rather than the retrospective fixed K=14.

**A simple provider-fit explanation also fails.** Mean provider-level Full48 public-I1 reconstruction MAE was 0.1277 (pilot), 0.1314 (P1), 0.1556 (P3), and 0.1101 (P4), while original-style Top14 G_PAR graph MAE was respectively 0.0304, 0.2447, 0.2511, and 0.1098. Provider-level and composed-graph MAE measure different targets and cannot be equated. They nevertheless show that the new-world failures were not simply accompanied by uniformly worse provider fits. Composition-sensitive statistics, query calibration, approximation errors and cancellation remain competing explanations; *intrinsic insufficiency of I1 has not been proved*.

**The methodological lessons have two levels.** First, a **predictive-sufficiency challenge**: matching public provider statistics may not preserve everything relevant to a composed SLA decision. Second, a **protocol-fidelity challenge**: a nominally unchanged method can be instantiated with different candidate domains, hyperparameter-selection rules, model support and evaluation regions. [Phase III](#appendix-c-experimental-chronology-and-method-versions) closes the bounded D0–D9 equivalence checks, but **does not uniquely attribute the pilot–battery accuracy gap**. That would require prospective one-factor-at-a-time ablations on fresh holdout conditions.

The complete audit ledger is `first_science/b1/retrospective_m3/PHASE_III_DIVERGENCE_CONTROL_REGISTER_2026-10-20.md`.

## 8.3 Post-result I1/I2 pipeline development (historical Phase-6)

After the [Phase II](#appendix-c-experimental-chronology-and-method-versions) expanded battery (historical [Phase-5](#appendix-c-experimental-chronology-and-method-versions)), the six M2 variants defined in Section 4.3 were evaluated on **P4/G_SEQPAR**, using 15 queries × 37 horizons = 555 related SLA measurements per variant. Their reconstruction-search architecture and graph-propagation budgets were matched at **B=2,700 graph runs per variant**. Their disclosed evidence and/or provider-fitting criteria differed, as specified in Section 4.3.

| P4/G_SEQPAR M2 variant | MAE | RMSE |
|:--|--:|--:|
| **I1STRONG_M2** | **0.09178** | **0.11390** |
| I2AFS_M2 | 0.09475 | 0.11826 |
| I2B_M2 | 0.10210 | 0.13617 |
| I2BHIER_M2 | 0.09429 | 0.11695 |
| I2BV4_M2 | 0.10854 | 0.15354 |
| I2BVAR_M2 | 0.15731 | 0.22086 |

![Phase-6 P4/G_SEQPAR matched-budget development comparison. All six rows use 555 related SLA measurements (15 conditions at 37 horizons) and 27-member M2 graph propagation at B=2,700; disclosed information and fitting losses vary together.](figures/phase6_matched_mae_v0_1.svg){width=95%}

The stronger I1 control performs best or near-best among these **joint information–loss pipeline** variants in this cell. Richer information is not a monotone improvement *under the tested objectives*. This does not show that I2 information is useless, that an ideal I2 estimator cannot improve on I1, or that the comparisons are independent held-out validation: the P4/G_SEQPAR cell had already informed iterative I2 development.

Privileged known-provider/oracle studies and provider-factorial substitutions were additionally reported, but are not treated as deployable I1-only methods or as equivalently independently audited core results.

## 8.4 Distinct P2 public-induced-region comparison

The October P2/G_PAR study chose the graph admissibility region deterministically from the **same published I1 rectangles** for all three reconstruction methods. It evaluated five same-$\rho$ queries over 37 horizons, or **185 points per method**, with a new reference design distinct from the failed [Phase-5](#appendix-c-experimental-chronology-and-method-versions) P2 Step-0 conditions.

| P2/G_PAR method | Native graph trajectories | MAE | RMSE | Bias |
|:--|--:|--:|--:|--:|
| M1 V3b | 100 | 0.13200 | 0.15332 | +0.04149 |
| M2 V3b | 2,700 | 0.14058 | 0.16371 | +0.13791 |
| M3 V3b FULL343 | 1,400 | **0.12787** | **0.14853** | +0.04263 |

Here all three methods are evaluated against **the same** $A_G^{I1+M0}$, constructed from the I1 provider limits using M0's boundary rules. They differ in process reconstruction and subsequent graph prediction. Hence no difference above measures graph-region reconstruction quality. The simulation budgets are **unmatched**; M3's small observed MAE advantage does not establish equal-cost superiority. This study cannot be read as a post-hoc repair of four earlier ineligible P2 cells.

## 8.5 Privileged search-deficit diagnosis

A separate P2 audit evaluated the actual hidden provider parameters against the public I1 target using the **same $N=100$ rescore and independent replay bank** as the finite reconstruction candidates. For each of three providers the true parameter vector was inside the search domain, yet it achieved better I1 RMSE than the selected best available V3b candidates:

| P2 provider | True $\theta$ rescore RMSE | Selected-best rescore RMSE | True $\theta$ replay RMSE | Selected-best replay RMSE |
|:--|--:|--:|--:|--:|
| A | **0.03443** | 0.10961 | **0.03151** | 0.12247 |
| B | **0.05337** | 0.17780 | **0.08178** | 0.18344 |
| C | **0.06110** | 0.13099 | **0.08437** | 0.12106 |

The registered seven-by-25-trial search generated **525** total provider trials across three providers. If the generating parameters fit the disclosed evidence better than the selected candidates despite being searchable in principle, then the executed **search and ranking procedure failed to find a comparatively favorable fit** under this test. This is a concrete optimization/inference failure mode.

It remains possible for a public interface to be non-identifying in some formal sense; however this particular evidence cannot prove that non-identifiability caused the observed prediction error. A 42-configuration, two-seed-bank $\pm20\%$ one-at-a-time local perturbation audit additionally measured finite objective sensitivity; it neither identifies the full local Hessian nor proves uniqueness or global optimizer convergence.

# 9. Uncertainty mathematics and cross-experiment interpretation

## 9.1 Numerical Monte Carlo precision

For a fixed reconstructed ensemble with normalized weights $\alpha_j$ and estimates $\widehat p_j$, let $\widehat p_M=\sum_j\alpha_j\widehat p_j$. The variance identity is

$$
V_{\rm MC}(\widehat p_M)
=\sum_j\alpha_j^2 V_j+
2\sum_{j<k}\alpha_j\alpha_k C_{jk}.
\tag{18}
$$

The covariance $C_{jk}$ matters for **M2's shared seed indices**. A seed-index paired bootstrap should resample each 27-member seed-vector as one unit rather than resampling individual member trajectories independently. M3's independent member seed streams permit the simpler variance form in Eq. (15), conditional on fixed weights, models and allocation.

The pilot's numerical-width appendix used Wilson intervals for fixed single-model binomial curves, paired percentile resampling for M2 and a normal approximation for M3 using a **worst-case variance**. The variance bound itself is conservative; the resulting **normal-approximation 95% interval is not an exact distribution-free confidence interval**, particularly when the FULL343 allocation leaves some models with only one trajectory. All such intervals are **pointwise** over $(A,H,\rho)$ and conditional on the reconstructed method, not simultaneous across all 555 or 6,660 related SLA measurements.

Separately, the Wilson intervals included in I1 measure sampling uncertainty in the provider-side probability estimates conditional on regions fitted from the independent construction bank. They do not include uncertainty in the fitted regions or provide simultaneous coverage across the I1 probability surface.

A rigorous fixed-sample conditional alternative, if required in later work, can be derived from a weighted Hoeffding inequality for independent bounded member outcomes, but this was **not an evaluated new estimator** in the frozen experiments. Sequentially peeking at ordinary fixed-sample intervals until a threshold is crossed does not preserve nominal coverage without a separately specified anytime-valid procedure.

## 9.2 Model dispersion is a distinct diagnostic

Let $p_j=E[\widehat p_j]$, $p_\alpha=\sum_j\alpha_jp_j$ and $\widehat p=\sum_j\alpha_j\widehat p_j$. The observed finite-ensemble dispersion is

$$
V_{\rm raw}
=\sum_j\alpha_j(\widehat p_j-\widehat p)^2.
\tag{19}
$$

Under fixed weights and unbiased member estimators, its expectation equals latent finite-model spread plus a contribution from numerical sampling,

$$
E[V_{\rm raw}]
=\sum_j\alpha_j(p_j-p_\alpha)^2+
\sum_j\alpha_j\operatorname{Var}(\widehat p_j)
-\operatorname{Var}(\widehat p).
\tag{20}
$$

The manuscript's nonnegative MC-subtracted plug-in diagnostic estimates only the *spread among the selected models*. The max-with-zero clipping and finite member budgets make it neither an unbiased calibrated risk estimate nor a guaranteed bound on model-to-hidden-world error.

Similarly, if the method predictor and white-box reference are independent and individually unbiased for their conditional targets, then

$$
E\!\left[(\widehat p_M-\widehat p_{\rm WB})^2\right]
=(p_M-\sigma_G)^2+V_{\rm MC,M}+V_{\rm WB}.
\tag{21}
$$

Subtracting empirical noise estimates from an observed squared difference and clipping at zero is an **experimental noise-correction diagnostic**. It does not make the unobserved model approximation error known exactly, and its square root adds estimation bias.

The different uncertainties are summarized as follows:

| Quantity | Obtained from | What it does *not* certify |
|:--|:--|:--|
| MC variance or Wilson/bootstrapped numerical band | Repeated graph simulation of frozen model(s) | Distance to hidden $\sigma_G$ |
| Finite-model min/max and weighted spread | Enumerated reconstructed joint hypotheses | Coverage of all physically possible models |
| Gibbs omitted mass $1-m_S$ | A normalized **chosen finite** Gibbs bank | Truth error outside that bank |
| Finite-WB reference bootstrap | Reference WB seed/trajectory resampling | Generalization to unseen worlds or new optimization searches |
| Across-world/graph variation | Distinct designed physical cells | Representative real-world uncertainty from only a few cells |
| Hidden-truth error and parameter diagnostics | Privileged reference available after freeze | A deployable estimator without privileged evidence |

## 9.3 Cross-phase lessons

These lessons compare global [Phase I](#appendix-c-experimental-chronology-and-method-versions) (controlled pilot), [Phase II](#appendix-c-experimental-chronology-and-method-versions) (expanded battery) and [Phase III](#appendix-c-experimental-chronology-and-method-versions) (retrospective divergence tracing) while preserving their distinct reference populations and evidence status.

**Candidate search is a plausible limiting mechanism, demonstrably so in P2.** The fact that true parameters better fit I1 than selected candidates makes the inverse search procedure a high-priority diagnosis. It does not eliminate other causes of graph discrepancy, including information compression and model-family restrictions.

**Ensembling is neither futile nor proved necessary.** The pilot same-support weighting test favored nonuniform public-evidence weights over uniform weights, while pilot Top1 slightly outperformed the larger weighted mixture at a matched budget. In the larger [Phase-5](#appendix-c-experimental-chronology-and-method-versions) study M3 FULL343 had the best aggregate MAE but still made sizeable errors. The data support context-dependent method performance, not a model-count law.

**Internal mixture coverage is not external prediction validity.** The retrospective original-style Top14 captured over 99.6% of the inferred joint-model mass in each eligible provider world, yet its overall MAE exceeded V3b FULL343. This does not isolate member count because the candidate-fitting and weighting pipelines changed.
**Richer disclosure is not sufficient by itself.** The I2 development variants were matched in broad search effort but changed loss functions and used an already studied cell. Their results test implemented pipelines, not the optimal value of their disclosed statistics.

**Graph structure matters without a simple universal directional rule.** A registered serial-versus-parallel masking prediction did not retain one direction across eligible worlds. The finite design does not identify a universal composition-graph error mechanism.

**Numerical convergence is insufficient for dependability.** Larger graph budget can reduce finite simulation noise without changing bias due to model/search error. No threshold band yet covers the total uncertainty required for a certified real-service admission decision.

# 10. Threats to validity and reproducibility

**Finite physical setting.** The core study uses three providers and four logical ASTs on a fixed physical embedding. It does not generalize by itself to arbitrary service graphs, cross-region placement, multi-tenant failures, dynamic routing or real production deployments. The provider generators and fitted process family are related; robustness to substantial model misspecification is not established.

**Limited observables.** I1 is deliberately compressed and empirical. Region construction was calibrated in frozen simulated worlds; its disclosure noise and dependence on the acquisition policy can affect inverse fits. Quality and power are part of the broader conceptual LCQ/continuum setting but not demonstrated as independent varying stress dimensions here.

**I1 acquisition verification.** The I1 acquisition procedure was checked against its frozen implementation and provenance records, but the complete acquisition was not independently reproduced from raw simulation events. Moreover, the actual coverage of the constructed regions in the generating provider worlds was not separately validated against the target probability content of the fitted latency-cost models.

**Condition selection and missing P2.** The [Phase-5](#appendix-c-experimental-chronology-and-method-versions) registered Step-0 eligibility gate failed for P2 and removed four of 16 intended physical cells. Main 12-cell estimates are **conditional on eligibility**, not estimates of all planned or unseen worlds. The P2-derived retrospective tests use new query regions and are not missing-data imputation.

**Method changes and development leakage.** V3, V3b and FULL343 changed model search, selection and support after earlier development evidence. The final graph WB was held back behind a hashed global prediction freeze, and archived timestamps/hash links were checked, but this does not restore the stronger status of having all methods fixed before every component of experimental evidence was observed. The same cell was reused while developing [Phase-6](#appendix-c-experimental-chronology-and-method-versions) I2 variants.

**Retrospective divergence controls.** The public-I1 CV re-analysis is diagnostic, not a new selected operational hyperparameter. Exact graph parity is checked on archived-seed subsets, not through a full B1400 replay. Causal attribution across changed worlds and SLA regions remains open.

**Retrospective original-style M3.** The B1400 Top14 and Top1 comparison was specified after prior V3b outcomes were known and reused the same reference. Different provider proposal/fit and local costs prevent causal attribution to ensemble size. The archived audit omits raw native graph ledgers, so it verifies included results rather than bitwise replay.
**Budget and correlation.** M1/M2/M3 graph budgets differ (100/2700/1400); their numbers of locally simulated trajectories and method fitting time differ as well. The 555 and 6,660 SLA measurements reuse simulation trajectories and query definitions, so they are not independent. Reference bootstrap and per-method numerical error do not simultaneously quantify scenario selection, model-search and physical-world extrapolation uncertainty.

**Engineering and software provenance.** The modified composition controller is in an external AICon/YAFS repository. The local current dependency revision and source SHA fingerprints were recorded, but exact clean-tree/source-lock provenance at each archived October run was not recovered. Several required smoke checks were completed only after early scientific work, a sequencing deviation documented in the audit. The [Phase-5](#appendix-c-experimental-chronology-and-method-versions) graph simulator received optional trace-exposure updates after main runs, so current repository HEAD alone does not identify the historical program state.

**Numerical evidence tier.** Primary saved result summaries and selected hashes have been independently checked against existing pointwise artifacts. This is not complete bitwise replay from every raw YAFS request event. Some ancillary historical pilot operating-point curves and an M2 paired-bootstrap width remain as reported source claims rather than independently recomputed numerical evidence. No statement above requires inventing their raw observations.

**External literature and coauthor consent.** The bibliography is inherited from the source manuscript and is **provisional**. References, citation details, current related work and venue overlap policy must be verified before any public release. This draft is internal and does not constitute coauthor approval for arXiv posting.

# 11. Conclusions and falsifiable next questions

Across [Phase I](#appendix-c-experimental-chronology-and-method-versions) (controlled pilot), [Phase II](#appendix-c-experimental-chronology-and-method-versions) (expanded battery) and [Phase III](#appendix-c-experimental-chronology-and-method-versions) (retrospective divergence tracing), the PRAISE program implemented a discrete-event native composition benchmark, finite public provider SLA disclosures and multiple reconstructed-model integration procedures. It established robust provenance for important frozen outputs, including a hash-frozen prediction/reference separation in the broad [Phase-5](#appendix-c-experimental-chronology-and-method-versions) battery. The favorable single-world pilot numerical findings were genuine, but the broader evaluation showed **material residual prediction errors** and did not establish general reconstruction sufficiency.

The added retrospective M3 study shows that near-complete mass coverage of an inferred bank cannot ensure external SLA prediction accuracy. [Phase III](#appendix-c-experimental-chronology-and-method-versions) confirms bounded estimator and native-graph equivalence while demonstrating reconstruction-protocol changes, especially inherited Gibbs lambda rather than repeated public-I1 CV. These are established differences, not a unique cause of graph error. A new holdout with controlled reconstruction ablations is needed to distinguish the causes.

The most actionable scientific questions now concern mechanisms rather than adding model members indiscriminately:

1. **Search recoverability:** When true generating parameters lie inside the search domain and fit I1 markedly better, which proposal distributions, loss landscapes or structural changes allow a public-only learner to find equivalent-quality fits with modest budget? This must be tested with a frozen search protocol and separate end-to-end graph reference.
2. **Information conditional value:** Can a fixed reconstruction objective/architecture be defined so that I1 and I2 disclosures differ *only* in the information made available, permitting an interpretable matched-information comparison?
3. **Graph sensitivity:** Which structural or workload conditions amplify small provider-level errors into end-to-end SLA error, and can the resulting condition be predicted using **publicly observable** quantities rather than privileged white-box outcomes?
4. **Finite-model approximation:** Under what observable diagnostics does Top1 suffice, when do additional hypotheses help and when does weighting mislead? Any rule proposed from a development world must be frozen and tested on other worlds.
5. **Decision calibration:** Can a method produce externally validated error coverage for the hidden graph SLA under clearly limited assumptions? This is a separate problem from making the Monte Carlo standard error small.

These questions are **future hypotheses**, not positive claims established by the existing evaluation. As a scholarly technical record, B1 can support a later focused methodological manuscript by providing precise definitions, method versions, extended experiments and explicit negative outcomes. Publication as a citable preprint remains a subsequent coauthor and venue-policy decision.

# Appendix A. Mathematical and numerical interpretation

## A.1 Finite-portfolio admission envelopes

🟩 **REVISIT APPENDIX A.1 WHEN REVIEWING THIS SECTION.** The historical $\beta$-based admission-envelope interpretation below is retained provisionally. Decide whether to remove it or reinterpret the finite-model extrema as a descriptive range of predicted SLA-satisfaction probabilities. Do not treat $\beta$ as part of the contracted SLA.

For a specified, finite method-generated set $\mathcal M_M$ of joint stochastic models, define

$$
\sigma^{-}_{G,M}(A,H;\rho)=\min_{\vartheta\in\mathcal M_M}
\sigma_G(A,H;\rho\mid\vartheta),\qquad
\sigma^{+}_{G,M}(A,H;\rho)=\max_{\vartheta\in\mathcal M_M}
\sigma_G(A,H;\rho\mid\vartheta).
\tag{A1}
$$

If $\beta\le\sigma^-_{G,M}$ then *all enumerated models* accept under their own ideal probabilities; if $\beta>\sigma^+_{G,M}$ all reject; otherwise there is disagreement among the finite set. This is a direct statement about the chosen set, **not** a calibrated confidence set, structural-identifiability theorem or SLA truth guarantee. Estimates of the extrema from finite graph simulations add MC error that is absent from this idealized algebra.

## A.2 Conditional numerical precision and model spread

The general covariance identity (18) holds for fixed finite weights. M2's paired common-seed bootstrap captures cross-model covariance; M3's independent-member variance bound (15) is conditional on the model bank, fixed weights and allocation. For member success probabilities $p_j$, independence across members and trajectories gives the exact conditional identity

$
\mathrm{Var}_{MC}(\widehat\sigma_G^{M3})
=\sum_{j\in S}\frac{\alpha_j^2p_j(1-p_j)}{N_j}
\le\frac14\sum_{j\in S}\frac{\alpha_j^2}{N_j}.
$

For a positive normalized weight vector, Cauchy--Schwarz gives $\sum_j\alpha_j^2/N_j\ge(\sum_j\alpha_j)^2/B=1/B$, with equality at $N_j=B\alpha_j$ in the continuous relaxation. For integer allocations, the bound decrease from one extra run is $\alpha_j^2/[4N_j(N_j+1)]$, a diminishing quantity as $N_j$ grows. Greedily taking the largest available decrease therefore minimizes this separable bound among positive integer allocations at a fixed total $B$ (cf. Neyman, 1934; Wright, 2014, Appendix D). It need not minimize variance based on unknown $p_j(1-p_j)$ or physical-model error. For a fixed sample allocation and truly independent bounded member outcomes, a weighted Hoeffding inequality gives

$$
\Pr\bigl(|\widehat p-p_\alpha|\ge\varepsilon\bigr)
\le 2\exp\left(-\frac{2\varepsilon^2}{\sum_j\alpha_j^2/N_j}\right),
\tag{A2}
$$

yielding a fixed-sample half-width

$$
\varepsilon_\delta=
\sqrt{\frac12\ln(2/\delta)\sum_j\frac{\alpha_j^2}{N_j}}.
\tag{A3}
$$

This is included as an *analytical consequence of standard bounded-variable concentration*, **not** a newly tested method or a bound on $|p_\alpha-\sigma_G|$. It is not automatically anytime-valid if sample sizes are chosen by repeatedly observing the outcomes.

The historical noise-adjusted model-spread quantities and white-box correction (19)–(21) are expectation-based diagnostics. Positive-part corrections may be convenient but must not be described as exact interval widths for physical model misspecification.

## A.3 Numerical-width scaling

The historical precision appendix extrapolated mean **pointwise interval width** approximately as $\overline W(B)=c/\sqrt B$, holding support, allocation and the simulation experiment fixed, so that a target width $w^\star$ corresponds formally to $B^\star\approx(c/w^\star)^2$. The pilot anchors were approximately M1 B100/width 0.0375; M2 B2700/width 0.0563 (not independently reproduced here from per-seed paired bootstrap arrays); M3 Top14 B1400/width 0.0493 and B2000/width 0.0425, using **interval clipping to [0,1]** for the reported M3 widths. These are illustrative numerical precision projections, **not evaluated accuracy-versus-budget forecasts**, and they exclude provider reconstruction expense and persistent model bias.

# Appendix B. Archived source and audit provenance

## B.1 Canonical authority hierarchy

For experimental assertions: frozen experiment contract plus source implementation and selected archive manifests/pointwise tables take precedence over later commentary. The numerical checks verify historical saved outputs, not new simulation. For mathematical definitions, the implementation and mathematical audit take precedence over loosely worded pilot-era prose.

The following documents in \`first_science/b1/\` are the companion reproducibility record:

- \`evidence_registry_v1_0.json\`, E01–E12, machine-readable study roles, versions, source paths, numerical values and caveats;
- \`METHOD_VERSION_CHRONOLOGY_2026-10-16.md\`, [Phase1](#appendix-c-experimental-chronology-and-method-versions)–6 and October P2 stage order;
- \`PHASE4_VERIFICATION_REVIEW_2026-10-16.md\`, independent pilot and Stage-B pointwise checks;
- \`VERIFICATION_REVIEW_V0_3_2026-10-16.md\`, [Phase5](#appendix-c-experimental-chronology-and-method-versions)/[Phase6](#appendix-c-experimental-chronology-and-method-versions)/P2 verified saved metrics;
- \`TABLES_FIGURES_SOURCE_RECONCILIATION_2026-10-16.md\`, 22 original source files, Table2–4 and Fig2–3 checks;
- \`METHOD_SUPPORT_VERIFICATION_REVIEW_2026-10-16.md\`, 132 V3b selection/allocation checks;
- \`SIMULATOR_PROVENANCE_AUDIT_2026-10-16.md\` and \`RUNTIME_PROVENANCE_VERIFICATION_REVIEW_2026-10-16.md\`, code scope, smoke sequencing, 94-pass stage/hash audit;
- \`UNCERTAINTY_MATHEMATICS_AUDIT_2026-10-16.md\`, exact and approximate interval/variance results;
- B1_M3_RETROSPECTIVE_EVIDENCE_AUDIT_2026-10-20.md, retrospective original-style M3: 316 pass, zero fail;
- \`retrospective_m3/PHASE_III_DIVERGENCE_CONTROL_REGISTER_2026-10-20.md\`, bounded D0–D9 controls and unresolved causal interpretations;
- \`FINAL_AUDIT_SIGNOFF_2026-10-16.md\`, conditional drafting authorization and unresolved publication gates;
- \`MANUSCRIPT_CLAIM_AUDIT_V0_1.csv\`, 68 claims and required dispositions.

The Phase-5 M3 allocation check uses `first_science/b1/verify_method_support_v0_1.py` to recompute greedy member counts from archived Gibbs weights and compare them with frozen pre-execution allocation tables for P1, P3 and P4. This is an allocation-consistency check, not independent evidence of predictive validity.

### Audited integrity milestones

| Artifact | Verification |
|:--|:--|
| Initial B1 inventory | 31 source files and 17 data roots available; 233 manifests inventoried |
| [Phase5](#appendix-c-experimental-chronology-and-method-versions)/6/P2 saved-results reconciliation | 399 passed, zero failed |
| [Phase4](#appendix-c-experimental-chronology-and-method-versions) pilot and Stage-B reconciliation | 60 passed, zero failed |
| [Phase5 V3b](#appendix-c-experimental-chronology-and-method-versions) member selection/allocation | 132 passed, zero failed |
| Historical pilot source display archive | 22/22 collector hashes and 13/13 checked scientific output hashes match |
| [Phase5](#appendix-c-experimental-chronology-and-method-versions) runtime/reference chain | 94 passed; 12/12 prediction hashes and 12/12 WB freeze backlinks |
| Retrospective original-style M3 archive | 316 passed; all 12 prediction-manifest backlinks verified |
| Historical source paper | 26-page \`v11_45\` PDF, preserved and not overwritten |

## B.2 Version-dependent costs and seeds

Reproducing the [Phase-5](#appendix-c-experimental-chronology-and-method-versions) executed comparison requires the source at the **archived PRAISE code_commit**, the external modified YAFS/AICon dependency, the public I1 provider cards, V3b selected provider-model and joint-support tables, the frozen graph ASTs, original Step-0 eligibility, named seed banks and archived graph prediction manifests. The final-WB source enumerates **54000–54999** per eligible physical cell. M1/M2 share one method-wide graph seed-index bank in the executed design and M3 uses separate rank-specific blocks. No missing seed or archived experiment is reconstructed in this draft.

For a future reproducibility package, the already assembled B1 tools can extract exact manifest and source hashes without touching frozen data. Current installed source fingerprints are useful but cannot replace a historical environment lock if byte-for-byte results are desired.

# Appendix C. Experimental chronology and method versions

This appendix distinguishes the **scientific role** of an experiment from the **historical implementation identifier** used in the repository. A stage number is not evidence of independent confirmation. In particular, the broad evaluation changed several methods before the final graph reference was inspected, and post-result experiments reused previously examined conditions.

## C.1 Experiment chronology (Table C.1)

| Scientific purpose | Historical repository stage | What was done and what it establishes |
|:--|:--|:--|
| Benchmark and disclosure development | Phase-1 and Phase-2 | Established the white-box simulator, the SLA scoring conventions and the public I1 interface. These were design and calibration activities, not independent tests of predictive accuracy. |
| Initial integration-method development | Phase-3 and early Phase-4 (G1/G2, Step-0) | Developed M0/M1 and subsequently M2, native graph compositions and informative query selection. These were developmental experiments, not a cross-world confirmation. |
| First controlled accuracy test (Phase I) | Phase-4 M3-v4 pilot | Frozen single-provider-world/graph comparison of M1, M2 and Top14-weighted M3, using 555 related query-horizon points and a fresh N=200 graph reference. Encouraging but setting-specific. |
| Retrospective pilot audit (Phase I evidence) | Phase-4 Stage A/B and parameter audits | Re-examined the same pilot with Top1, weighting, allocation and hidden-parameter comparisons. These were post-result diagnostics, not a second holdout. |
| Expanded-study protocol (Phase II) | Phase-5 registered V2 | Planned four provider worlds and four graph structures, with white-box-based Step-0 eligibility and independent final graph references. This version was registered but not executed unchanged. |
| Expanded evaluation (Phase II) | Phase-5 V3/V3b, M3 FULL343 | Revised provider fitting and model selection, then replaced M3 Top14 propagation with all 343 joint models after a permitted retained-mass diagnostic, before opening the final graph reference. Twelve of 16 planned cells passed Step-0; N=1000 fresh reference trajectories per eligible cell. A broader evaluation, **not an unchanged confirmation** of the pilot algorithm. |
| Retrospective divergence investigation (Phase III) | October original-style M3 and D0–D9 controls | Revisited earlier results, reconstructed the original-style Top14/Top1 approach and audited pilot-to-battery differences using previously inspected evidence. No new independent holdout. |
| Richer-disclosure development (Phase III) | Phase-6 I1-strong/I2a/I2b M2 variants | Compared six disclosure-and-loss pipelines on the already studied P4/G_SEQPAR cell, with matched search and graph budgets. Development evidence, not an isolated test of information quantity. |
| Separate post-result diagnostic (Phase III) | October P2/G_PAR and privileged P2 parameter audits | Tested a new public-induced graph region and diagnosed provider reconstruction against hidden generating parameters. It does not replace the four Phase-5 P2 cells excluded by Step-0. |

The repository chronology and frozen source-level method audits are listed in Appendix B. The global labels Phase I/II/III describe evidence roles; Phase-1 through Phase-6 and V2/V3b identify historical engineering stages or method versions.

## C.2 Method-version matrix (Table C.2)

| Period | M1 selection | M2 membership | M3 support | Main M3 graph budget | Evidence role |
|:--|:--|:--|:--|--:|:--|
| Phase-4 pilot | Historical TPE single fit/provider | 3 diverse/provider; M1 anchor excluded | 48/provider $\to$ weighted Top14 | 1,400 or 2,000 | Same-world frozen pilot |
| Phase-5 registered V2 | Frozen TPE/domain policies | Separate diversity/compatibility policy | Originally Top14 | Planned 1,400 | Protocol, not final executed version |
| Phase-5 executed V3b | Best common-$N100$ RMSE of seven | RMSE ranks 1–3; includes M1 anchor | All 7/provider $\to$ FULL343 | 1,400 | 12-cell final-WB evaluation |
| October retrospective M3 | V3b remains comparator | Not re-estimated | 48/provider Top14 and Top1 | 1,400 each | Post-result same-WB comparison |
| Phase-6 matched | Strong I1 or I2-specific loss and 256-trial search | Top3/provider, 27 equal weights | **Not evaluated** | Not applicable | Post-Phase5 development |

The matrix deliberately does **not** imply identical candidate search, local costs, physical-cell populations or empirical credibility across the rows.

# Appendix D. Provisional literature references

**Bibliographic status:** Entries 1–20 are transcribed or lightly reformatted from the historical October 2 manuscript, without a new verification of every bibliographic detail. The allocation-specific references 21–22 were checked against publisher and U.S. Census Bureau records. Entry 23 identifies the audited AICon source-code revision; it does not certify the historical installed environment. This list does not claim exhaustive coverage of 2026 research.

1. Bissiri, P. G., Holmes, C. C., and Walker, S. G. “A general framework for updating belief distributions.” *Journal of the Royal Statistical Society B* **78**(5), 1103–1130 (2016). DOI: 10.1111/rssb.12158.
2. Bergstra, J., Bardenet, R., Bengio, Y., and Kégl, B. “Algorithms for hyper-parameter optimization.” *NeurIPS 24*, 2546–2554 (2011).
3. Blake, M. B., Cummings, D. J., Bansal, A., and Bansal, S. K. “Workflow composition of service level agreements for web services.” *Decision Support Systems* **53**(1), 234–244 (2012). DOI: 10.1016/j.dss.2012.01.017.
4. Chen, Y. “Web services composition with incomplete QoS information.” *CIT Workshops 2008*, 652–656. DOI: 10.1109/CIT.2008.Workshops.13.
5. De Giacomo, G., De Masellis, R., and Patrizi, F. “Composition of partially observable services exporting their behaviour.” *ICAPS 2009*, 90–97. DOI: 10.1609/icaps.v19i1.13360.
6. Geebelen, D., Geebelen, K., Truyen, E., Michiels, S., Suykens, J. A. K., Vandewalle, J., and Joosen, W. “QoS prediction for web service compositions using kernel-based quantile estimation with online adaptation of the constant offset.” *Information Sciences* **268**, 397–424 (2014). DOI: 10.1016/j.ins.2013.12.063.
7. Gouriéroux, C., Monfort, A., and Renault, E. “Indirect inference.” *Journal of Applied Econometrics* **8**(S1), S85–S118 (1993). DOI: 10.1002/jae.3950080507.
8. Jaeger, M. C., Rojec-Goldmann, G., and Mühl, G. “QoS aggregation for web service composition using workflow patterns.” *EDOC 2004*, 149–159. DOI: 10.1109/EDOC.2004.1342512.
9. Lera, I., Guerrero, C., and Juiz, C. “YAFS: A simulator for IoT scenarios in fog computing.” *IEEE Access* **7**, 91745–91758 (2019). DOI: 10.1109/ACCESS.2019.2927895.
10. Luo, Z., Wang, D., Yin, Y., Ignatius, J., and Cheng, T. C. E. “Service composition and optimal selection in cloud manufacturing under event-dependent distributional uncertainty of manufacturing capabilities.” *European Journal of Operational Research* **325**(2), 281–302 (2025). DOI: 10.1016/j.ejor.2025.03.005.
11. Magrans de Abril, I., Rouska, N.-M., Casamayor Pujol, V., and Dustdar, S. “AICon: Agentic intelligence for the computing continuum.” *IEEE Internet Computing* **29**(6), 53–62 (2025). DOI: 10.1109/MIC.2025.3645964.
12. Magrans de Abril, I., Sedlak, B., Casamayor-Pujol, V., and Dustdar, S. “Composable autonomic offerings for decentralized service provisioning in the computing continuum.” *ApPLIED 2026*, article 3:1–3:9. DOI: 10.1145/3820355.3820395.
13. Mertens, H., Quatmann, T., and Katoen, J.-P. “Compositional reasoning for probabilistic automata with uncertainty.” *arXiv:2603.29550* (2026). DOI: 10.48550/arXiv.2603.29550.
14. Razian, M., Fathian, M., Bahsoon, R., Toosi, A. N., and Buyya, R. “Service composition in dynamic environments: A systematic review and future directions.” *Journal of Systems and Software* **188** (2022). DOI: 10.1016/j.jss.2022.111290.
15. Sedlak, B., Casamayor Pujol, V., Magrans de Abril, I., Donta, P. K., Toosi, A. N., and Dustdar, S. “Service orchestration in the computing continuum: Structural challenges and vision.” *IEEE Internet Computing* **30**(2), 88–98 (2026). DOI: 10.1109/MIC.2026.3662064.
16. Wu, Z., Xiong, N., Huang, Y., Gu, Q., Hu, C., Wu, Z., and Hang, B. “A fast optimization method for reliability and performance of cloud services composition application.” *Journal of Applied Mathematics* **2013**, 1–12. DOI: 10.1155/2013/407267.
17. Xu, D. N., Gössler, G., and Girault, A. “Probabilistic contracts for component-based design.” *ATVA 2010*, LNCS 6252, 325–340. DOI: 10.1007/978-3-642-15643-4_24.
18. Zeng, L., Benatallah, B., Ngu, A. H. H., Dumas, M., Kalagnanam, J., and Chang, H. “QoS-aware middleware for web services composition.” *IEEE Transactions on Software Engineering* **30**(5), 311–327 (2004). DOI: 10.1109/TSE.2004.11.
19. Zheng, H., Yang, J., and Zhao, W. “Probabilistic QoS aggregations for service composition.” *ACM Transactions on the Web* **10**(2), 1–36 (2016). DOI: 10.1145/2876513.
20. Gibbs, A. L., and Su, F. E. “On choosing and bounding probability metrics.” *International Statistical Review* **70**(3), 419–435 (2002). DOI: 10.1111/j.1751-5823.2002.tb00178.x.
21. Neyman, J. “On the two different aspects of the representative method: The method of stratified sampling and the method of purposive selection.” *Journal of the Royal Statistical Society* **97**(4), 558–606 (1934). DOI: 10.1111/j.2397-2335.1934.tb04184.x.
22. Wright, T. “A simple method of exact optimal sample allocation under stratification with any mixed constraint patterns.” U.S. Census Bureau, Research Report Series RRS2014-07 (2014). https://www.census.gov/library/working-papers/2014/adrm/rrs2014-07.html.
23. AICon. *Agentic Intelligence for the Computing Continuum*, source repository, audited checkout revision `6eabfa7` (2 September 2026). https://github.com/ildefons/aicon/tree/6eabfa70531e7091e777a0946ffa967721c0f538. The October 2026 runtime audit identified this checkout revision but did not certify the historical imported source state for every frozen execution.

