<!-- GitHub-optimized reading copy. The exact scientific source is B1_TECHNICAL_REPORT_DRAFT_V0_1.md; math is fenced for GitHub's math renderer. -->

# Executive synthesis 

Composed cloud-edge services can expose little more than provider-local workload and SLA evidence while keeping their stochastic execution models private. The methodological challenge is to predict an end-to-end, horizon-dependent SLA-satisfaction probability from these disclosures without silently assuming access to hidden process parameters. We report the development, implementation, and evaluation of a family of methods indexed by provider information representation $I$ and integration procedure $M$, together with a simulator and a complete account of observed limitations.

We define the evaluated quantity as $\sigma_G(A,H;\rho)=\Pr[c_G(A,H)\ge\rho]$, where $c_G(A,H)$ is the fraction of **decided** composed requests that meet a specified latency-cost-quality region by time $H$. A missed latency deadline is a decided failure; requests not yet decided are excluded; zero decided requests yield compliance one. This quantity measures the probability that the composed service meets its SLA compliance target over the observation horizon $H$.

The original controlled three-provider parallel-graph pilot was promising. Against a fresh $N_{\mathrm{WB}}=200$ white-box reference over 555 correlated query-horizon observations, the mean absolute errors (MAE) of a single reconstructed model (M1), a 27-member equal-weight ensemble (M2), and a Gibbs-weighted pilot M3 with 14 propagated joint models were respectively **0.18517, 0.06815 and 0.03037**. However, a retrospective cost-matched support audit found a Top1 estimator with MAE **0.02878**, slightly below the weighted Top14 estimator in that fixed pilot. The pilot therefore did not establish that multi-model averaging was necessary, nor did it establish transfer across provider worlds or graph forms.

A later, registered multi-world/multi-graph evaluation was the more informative generalization test. Sixteen physical cells were planned (four provider worlds times four logical graph structures); four P2 cells failed the prespecified Step-0 difficulty/eligibility gate and were excluded without replacement. On the remaining 12 cells, with independent $N_{\mathrm{WB}}=1000$ final white-box trajectories per cell and 6,660 correlated query-horizon observations per fully applicable method, the executed Phase-5 V3b algorithms produced MAE **0.15702** (M1), **0.13395** (M2), and **0.12189** (M3 FULL343). M3 retained the best aggregate ranking, but hard conditions still had substantial errors. Its algorithm and candidate support also changed from the pilot and from the initially registered Phase-5 method. Accordingly these numbers cannot be treated as direct replications of the original 14-member method.

Subsequent development tests revealed further limitations. On P4/G_SEQPAR, stronger reconstruction from I1 alone performed comparably to, and on average slightly better than, several richer I2 information-and-loss pipelines under matched search and graph-propagation designs. This does **not** isolate the causal utility of information quantity because fitting objectives also changed. In a separate P2/G_PAR experiment using a deterministically composed public graph region, M1, M2 and M3 achieved MAE **0.13200, 0.14058 and 0.12787**, respectively, under **unmatched** graph budgets. A privileged retrospective audit then found that the true generating provider parameters fitted the public I1 evidence better than the selected reconstructed candidates despite lying inside the search domain. This is direct evidence of a search/reconstruction deficit, not a proof of structural non-identifiability.

The overall conclusion is conditional: end-to-end SLA estimation from limited disclosure is demonstrably feasible **in some controlled cases**, but the developed finite-search integration methods have not delivered reliable prediction across the studied variations. The technical report retains favorable, negative, and inconclusive evidence and distinguishes numerical Monte Carlo precision from uncertainty about the hidden system.

# 1. Research problem, scope, and prior context

## 1.1 Composable offerings and information boundaries

The computing continuum spans resources and services controlled by different administrative entities. An integrator may know its own workflow or service-composition graph while observing only restricted public claims about the providers on which it depends. Physical execution is shaped by stochastic service times, queues, branch synchronization, workload and cost accumulation. Composing provider-local advertised measures is therefore not, in general, equivalent to observing the actual composed service.

The Composable Autonomic Offering (CAO) abstraction represents an offering as

```math
o=(G,s,\sigma,r), \tag{1}
```

where $G$ is the composition graph, $s$ describes service objectives, $\sigma$ represents dependability or survival information, and $r$ is the realization envelope [12]. The CAO abstraction motivates predicting a useful dependability quantity, but does not, by itself, prescribe which information must be disclosed or which numerical method can produce a dependable composition estimate.

We separate these choices explicitly:

```math
\tau=(I,M), \tag{2}
```

with **information interface** $I$ and **integration method** $M$. $I$ constrains what a provider can disclose, while $M$ selects, fits and propagates models from that disclosure. Distinct $M$ may use the same $I$; conversely an information-rich interface can require a different reconstruction objective, making the evaluated unit an **information–method pair**.

The question is not whether analytical or stochastic QoS composition exists. It does [3,8,17–19]. Rather, the specific problem is **inverse, public-evidence-constrained** composition: can an integrator, with provider-local probability surfaces and no hidden execution traces or true parameters, predict a finite-horizon, end-to-end SLA event?

## 1.2 Research questions and evidence categories

The program addresses four related questions:

**RQ1, feasibility and limits.** When can finite public provider disclosures support useful graph-level SLA-satisfaction prediction, and in which worlds, topologies, regimes, or query regions does prediction fail?

**RQ2, methods under a fixed interface.** How do analytical propagation, a single provider reconstruction, equal-weight reconstruction portfolios and evidence-weighted finite supports compare? Which observed differences are due to candidate search, support membership, weights or numerical allocation, and which cannot be causally separated?

**RQ3, disclosure.** Does enriching the public interface with marginal or paired temporal compliance information improve the resulting *information–loss–integration pipeline* under matched reconstruction resources?

**RQ4, provenance and decision meaning.** How reproducible are the finite results, and what do numerical Monte Carlo intervals, model spread, reference error and support-truncation guarantees actually mean for an SLA threshold?

We distinguish **frozen same-condition pilot**, **registered battery**, **documented pre-final-white-box development revision**, **final held-out reference evaluation**, **post-result development** and **privileged retrospective diagnostic**. “Prospective” always refers to the named freeze and reference bank, not to the idea that all versions were fixed at the beginning of the entire project.

## 1.3 Scientific boundaries

This document does not establish a structural identifiability theorem. Multiple candidate models with different parameters and similar *finite empirical* I1 errors may reflect a non-injective information map, measurement noise, search limitations, model family restrictions, or some combination. The present observations cannot distinguish these causes in full generality.

The report is also deliberately separate from earlier unpublished PPG work: no unpublished GP+DVI construction, readiness score, prior private code/data, or PPG-specific QR/YOLO/Lidar configuration is used to define this benchmark.

# 2. Formal SLA objective and benchmark semantics

## 2.1 Request-level admissibility

For a composed request, denote latency, accumulated cost and quality by $(L_G,C_G,Q_G)$. A rectangular admissibility region is

```math
A=\{(L,C,Q): L\le\ell,\ C\le c,\ Q\ge q\}.
```

A request is **compliant** when it is decided and its final outcome lies in $A$. The simulator records the top-level emission and, if available before simulation stop, the completion time. An on-time request is decided at completion. An uncompleted or late request is decided as a latency failure when its deadline arrives. A request whose completion and deadline are still in the future is unresolved at the current evaluation horizon. The SLA-scoring rule does not equate “unresolved” with “failed”.

Let $\mathcal D_G(H)$ be the set of top-level requests *decided* by horizon $H$, and $\mathcal C_G(A,H)\subseteq\mathcal D_G(H)$ the compliant subset. Define, with the explicitly frozen zero-decision convention,

```math
c_G(A,H)=
\begin{cases}
1, &|\mathcal D_G(H)|=0,\\[2mm]
|\mathcal C_G(A,H)|/|\mathcal D_G(H)|, &|\mathcal D_G(H)|>0.
\end{cases}
\tag{3}
```

For required compliance fraction $\rho\in[0,1]$, the true graph-level estimand is

```math
\boxed{\sigma_G(A,H;\rho)=\Pr\{c_G(A,H)\ge\rho\}.}
\tag{4}
```

The probability is taken over independent stochastic trajectories of the specified provider world, workload and execution graph. $H$ describes a *cumulative observation horizon*, not necessarily the time until the first violation. A trajectory can be below its required compliance fraction at one horizon and rise above it later when more compliant requests are decided. Consequently $\sigma_G(A,H;\rho)$ is **not guaranteed to decrease with $H$**. While historical CAO writing uses the shorthand “survival”, in this report “horizon-dependent SLA-satisfaction probability” is the exact term.

The numerical methods compute $\widehat\sigma_G^{(I,M)}(A,H;\rho)$, and the hidden world is only evaluated through a separate finite white-box reference $\widehat\sigma_G^{\mathrm{WB}}$ under experimental conditions that permit it.

## 2.2 Decisions versus predictions

An optional numerical rule at an admission threshold $\beta$ is

```math
\widehat D_{\beta}^{(I,M)}(A,H;\rho)
=\mathbf 1\!\left[\widehat\sigma_G^{(I,M)}(A,H;\rho)\ge\beta\right].
\tag{5}
```

This is a **decision made under a fitted model**. It is not a validated guarantee that the true service meets the objective with probability $\beta$.

The distinction remains even if a pointwise numerical interval around the fitted estimate lies entirely above $\beta$. Such an interval can quantify finite Monte Carlo error conditional on the reconstructed models; it does not include arbitrary provider-model misspecification or hidden-system uncertainty. The precise uncertainty decomposition appears in Chapter 10 and Appendix A.

## 2.3 Graph composition algebra and its status

For ideal rectangular local service bounds, a serial composition accumulates latency and cost and takes the minimum quality, while an all-required parallel join takes the longest branch latency, adds branch costs and takes the minimum branch quality. Ignoring shared fixed terms for the moment,

```math
\begin{aligned}
\operatorname{Seq}:&\quad
\ell=\sum_i\ell_i,\quad c=\sum_i c_i,\quad q=\min_i q_i,\\
\operatorname{ParAll}:&\quad
\ell=\max_i\ell_i,\quad c=\sum_i c_i,\quad q=\min_i q_i.
\end{aligned}
\tag{6}
```

This is **boundary algebra**, not a theorem that an analogous product of finite-horizon trajectory-compliance probabilities exactly predicts composed compliance under queueing and synchronized arrivals. The original fixed parallel pilot also includes measured fixed terms $\ell_G=0.014003+\max_i\ell_i$ and $c_G=0.03+\sum_i c_i$ under its own graph/network configuration; these constants are not to be transferred automatically to other experimental graph structures.

# 3. Provider disclosure interfaces and reconstruction targets

## 3.1 Public interface I1

The original provider-local public interface I1 offers a nested family of rectangular admissibility regions:

```math
A_i(\rho_r)=
\{L_i\le\ell_i(\rho_r),\, C_i\le c_i(\rho_r),\, Q_i\ge q_i\}.
\tag{7}
```

Here **$\rho_r$ is a region-content index**, used in constructing the provider-local region. It is conceptually distinct from **$\rho_q$**, the required fraction of decided requests inside the region. For each region the public card exposes an empirical probability surface

```math
\widehat\sigma_i^{I1}(A_i(\rho_r),H;\rho_q)
\approx \Pr\{c_i(A_i(\rho_r),H)\ge\rho_q\}.
\tag{8}
```

The historical pilot used $\rho_r,\rho_q\in\{0.95,0.975,0.98333,0.99,0.995\}$ and a 5-second horizon grid up to 240 seconds. Separate $N=100$ trajectory banks were used for region construction and the empirical probability surface; the workload period was 0.2 seconds. The card does **not** disclose request timestamps, hidden queue/service trajectories or the provider parameters.

The source-side procedure uses provider-private simulation evidence to *publish* a finite I1 card. The integrator, by design, sees only the card. This publisher-versus-consumer division is essential: giving a method the hidden sample identities, generating parameters or white-box graph predictions would change $I$ and invalidate the intended inverse reconstruction comparison.

The underlying experiments assume a family of provider surrogate processes parameterized by

```math
\theta_i=(\mu_i,\kappa_i,\mathrm{CV}_i),
\tag{9}
```

for mean service time, cost rate, and coefficient of variation of service time. The inverse learner does not observe $\theta_i$. The historical I1 specification enforces nested local regions in its frozen acquisition design; complete raw-event/acquisition replay and all probabilistic-coverage properties were not independently reverified for this report version.

## 3.2 I1 is not the same as the SLA query region

The local disclosure rectangles must be distinguished from the **requested graph-level** region $A_G$. The historical pilot first composed local rectangles to obtain an induced graph region $A_G^{\rm base}(\rho_r)$, then multiplied only the induced latency and cost limits by calibrated factors $\gamma$ to define Easy, Mid and Stress evaluation regions. In the Phase-5 battery, query construction and eligibility used a separate preregistered Step-0 calibration/confirmation process.

The subsequent October P2/G_PAR study instead explicitly tested an **unscaled, deterministically induced public graph region** $A_G^{I1}=\operatorname{Compose}_G(A_A,A_B,A_C)$ and varied the stochastic prediction methods over the **same** region. The study does not compare alternative learned global region constructors, and it does not reinstate P2 in the excluded Phase-5 prospective cohort.

## 3.3 Enriched I2 interfaces

The Phase-6 experiments explore additional anonymous provider-compliance summaries. **I2a** exposes a fuller marginal distribution of the trajectory compliance statistic, compared with the I1 thresholded surfaces. **I2b** provides anonymous paired within-window temporal-compliance information; later I2b variants test different weighting and hierarchical reconstruction losses.

These augmentations enlarge or reorganize disclosed information. However, they also change the objective used to fit provider surrogates. A comparison between I1strong-M2 and an I2b-M2 variant therefore tests an **interface plus reconstruction-loss combination** under a matched search/propagation architecture. It does not, by itself, identify the effect of information quantity while holding the inference method fixed.

# 4. Integration algorithms and historical method versions

## 4.1 M0: analytical public-boundary predictor

M0 propagates the local rectangular boundaries through the known composition graph, without fitting private stochastic provider processes. For a requested graph region $A_G$, it is scored only where the publicly induced rectangle $A_G^{I1}$ is contained in $A_G$. On applicable queries its same-$\rho$ product is

```math
\widehat\sigma_G^{M0}(A_G,H;\rho)
=\prod_{i\in\{A,B,C\}}
\widehat\sigma_i^{I1}(A_i(\rho),H;\rho).
\tag{10}
```

This is an **explicit heuristic baseline**, not a general stochastic lower or upper bound for the graph SLA. Each provider's local compliance fraction can exceed $\rho$ while the sets of locally failing requests differ, preventing a corresponding end-to-end compliance implication. Queue interactions and branch synchronization create additional coupling. M0 applicability is also nonuniform, so its aggregate MAE cannot be ranked against all-query M1/M2/M3 without reporting the denominator.

## 4.2 M1: one reconstructed provider process per provider

M1 fits one stochastic surrogate to each provider's public evidence, combines the three selected provider models and simulates the native graph. The original Phase-3/4 method used a larger single TPE search with its own confirm/replay process and selected one provider hypothesis each. The executed Phase-5 V3b version instead started from **seven independent 25-trial TPE searches per provider**, with separate local search seeds. It rescored the seven run winners on a fresh common $N=100$ local evidence bank and selected the minimum I1 RMSE candidate. A second independent local bank was diagnostic and not used to choose the model.

A reconstructed parameter vector is a **candidate fitted to I1**, not a recovered physical truth. Later privileged P2 tests found lower I1 errors at the actual generating parameters than at the selected candidates.

## 4.3 M2: equal-weight finite model propagation

Given three candidate provider models for each provider, M2 propagates the $3^3=27$ Cartesian joint models. Its point estimate is

```math
\widehat\sigma_G^{M2}
=\frac{1}{27}\sum_{j=1}^{27}\widehat\sigma_G(A,H;\rho\mid\vartheta_j).
\tag{11}
```

The historical **Phase-4 M2** selected deliberately diverse I1-compatible representatives and **excluded the M1 anchor** from its portfolio by contract. The executed **Phase-5 V3b M2** chose ranks 1–3 by common-bank I1 RMSE among seven candidates per provider, so the M1 rank-1 provider model **is included** in each V3b M2 local portfolio. There was no hard I1-compatible threshold in the V3b ranking. M2's reported 27 models are thus not a fixed scientific intervention across phases.

The main Phase-5 graph budget for M2 was 100 trajectories per joint model, **2,700 trajectories per physical cell**. Shared seed indices were used across M2 member graph simulations, so a paired seed-index bootstrap is the appropriate numerical dependence-aware design.

## 4.4 M3: public-evidence-weighted finite reconstruction

M3 forms a provider-model candidate bank and scores its members only against public information. In the evaluated family, finite provider weights take the form

```math
w_{i,k}
=\frac{\exp[-\lambda E_{i,k}]}
{\sum_{k'}\exp[-\lambda E_{i,k'}]},
\tag{12}
```

where $E_{i,k}$ is a public-I1 loss (for the executed version, a Jeffreys-smoothed Bernoulli KL discrepancy) and the temperature parameter $\lambda$ was selected from public-evidence development procedures. A joint model $\vartheta_j=(\theta_{A,a},\theta_{B,b},\theta_{C,c})$ receives product weight

```math
W_{a,b,c}=w_{A,a}w_{B,b}w_{C,c}.
\tag{13}
```

This is a weight over *hypotheses about providers*. The product does not remove the actual queueing/dependency interactions once a joint triple is propagated through the native simulator; those interactions remain inside each stochastic graph run. These Gibbs weights are **not calibrated posterior probabilities** of the hidden generating model.

For a selected set $S$, normalized aggregate weights $\alpha_j=W_j/\sum_{k\in S}W_k$ yield

```math
\widehat\sigma_G^{M3}
=\sum_{j\in S}\alpha_j
\widehat\sigma_G(A,H;\rho\mid\vartheta_j).
\tag{14}
```

The **historical pilot M3-v4** began with **48 candidates per provider**, used public-I1 Gibbs weights with $\lambda=30$, and propagated the **Top14** joint hypotheses under total graph budgets $B=1400$ or $2000$. Within this *finite* inferred distribution, those 14 members carried approximately 99.917% of the joint weight.

The executed **Phase-5 V3b M3 FULL343** instead used **seven independently obtained candidates per provider** and propagated **all $7^3=343$ joint hypotheses** with total budget $B=1400$. This replaced the registered Top14 execution after a **pre-graph-white-box** mass diagnostic found Top14 retained mass only 0.552 in P1, 0.962 in P3, and 0.867 in P4. It preserved the candidate bank and frozen weights, assigned at least one graph trajectory per joint member and greedily allocated the remaining budget using the reduction in the upper variance objective. The change was documented before the end-to-end graph reference was read, but it was still a **method revision**, not a confirmatory unchanged test of originally registered Top14.

For weights $W_j$ and independent Bernoulli member trajectories,

```math
\mathrm{Var}_{MC}(\widehat\sigma_G^{M3})
\le\frac14\sum_j\frac{W_j^2}{N_j},
\qquad \sum_jN_j=B.
\tag{15}
```

The continuous relaxation gives $N_j\propto W_j$; the finite algorithm initializes one trajectory/member and iteratively chooses the largest $\Delta_j=W_j^2/[N_j(N_j+1)]$, with a frozen rank tie-break rule. Archive verification reconstructed the P1/P3/P4 allocations **exactly**.

Crucially, **M3 Top1 is not definitionally M1**. M1 selects per-provider candidates by minimum common-bank I1 RMSE. M3 Top1 takes the maximum *product* of provider Gibbs weights based on KL energies; the two may select the same parameter tuple in some worlds, but identity is not guaranteed.

## 4.5 Within-ensemble support bounds

For any finite normalized Gibbs support, let $S$ retain weight mass $m_S\in(0,1]$, and let $p_{\rm full}$ and $p_S$ be respectively the expected SLA probability under the full finite distribution and the normalized retained submixture. Since each member probability is in $[0,1]$,

```math
\boxed{|p_{\rm full}-p_S|\le1-m_S.}
\tag{16}
```

The proof writes $p_{\rm full}=m_Sp_S+(1-m_S)p_{\rm omitted}$ and uses both probabilities in $[0,1]$. This is an **exact within-bank truncation bound**. For the pilot Top14, $1-m_S$ was approximately $0.000826$; for Phase-5 FULL343 it is zero **relative to the chosen 343-member bank**. Neither statement bounds error with respect to hidden graph truth.

### Method-version matrix

| Period | M1 selection | M2 membership | M3 support | Main M3 graph budget | Evidence role |
|:--|:--|:--|:--|--:|:--|
| Phase-4 pilot | Historical TPE single fit/provider | 3 diverse/provider; M1 anchor excluded | 48/provider $\to$ weighted Top14 | 1,400 or 2,000 | Same-world frozen pilot |
| Phase-5 registered V2 | Frozen TPE/domain policies | Separate diversity/compatibility policy | Originally Top14 | Planned 1,400 | Protocol, not final executed version |
| Phase-5 executed V3b | Best common-$N100$ RMSE of seven | RMSE ranks 1–3; includes M1 anchor | All 7/provider $\to$ FULL343 | 1,400 | 12-cell final-WB evaluation |
| Phase-6 matched | Strong I1 or I2-specific loss and 256-trial search | Top3/provider, 27 equal weights | **Not evaluated** | Not applicable | Post-Phase5 development |

The matrix deliberately does **not** imply identical candidate search, local costs, physical-cell populations or empirical credibility across the rows.

# 5. Native simulator, graph structures, and experiment protocol

## 5.1 Modified YAFS/AICon composition engine

The discrete-event environment uses YAFS as extended under AICon [9,11]. Modified YAFS application/core code registers compositions and per-branch dependencies, carries a per-request **composition path**, activates a dependent branch when its required sibling completions for that invocation have been received, and emits a single all-required composition output. Standalone code probes cover elementary joins, scoped dependency isolation and nested compositions.

The Phase-5 scientific test does **not** exercise arbitrary nested service DAGs. It compiles a small family of exactly three-provider sequence/parallel ASTs into dependencies in **one** native composition controller. Source/Fpre/provider/Fpost execution uses fixed physical node embedding and placement across all four logical graphs. Periodic arrivals are sent to stochastic provider services, with native queueing, service cost and network delays.

The four frozen dependency maps are:

| Logical graph | A predecessors | B predecessors | C predecessors | Reading |
|:--|:--|:--|:--|:--|
| G_PAR | none | none | none | $A\parallel B\parallel C$ |
| G_SEQ | none | A | B | $A\to B\to C$ |
| G_SEQPAR | none | A | A | $A\to(B\parallel C)$ |
| G_PARSEQ | none | none | B | $A\parallel(B\to C)$ |

**These are four logical composition structures, not four separately changed physical infrastructure topologies.** The companion source-level audit documents the Graph AST compiler, validation of unique leaves, deterministic replay probes and controller source locations.

The inspected runtime constructs an empty acting management-agent network. It therefore evaluates *offline graph performance estimation*, not online active-inference orchestration, decentralized planning or adaptive placement. WATT is zero in these test topologies and messages use a neutral QoS propagation specification; although $(L,C,Q)$ is the formal admissibility schema, strong empirical energy/quality variation was not established by the core battery. These are limits on external validity, not omissions to conceal.

## 5.2 White-box worlds, public evidence, and test set design

The research stages intentionally distinguish **disclosure production**, **query design**, **reconstruction**, **blind prediction**, **final white-box reference** and **evaluation**. The ability to inspect generating provider parameters belongs to privileged experiment construction and later retrospective diagnostics, not to the permitted reconstruction method.

The Phase-5 registered experiment included four provider worlds P1–P4, the four graph forms above and a five-$\rho$ by three-regime query battery in each planned world-by-graph cell. Step-0 used dedicated calibration and confirmation white-box evidence to freeze nondegenerate regional difficulty and determine eligibility. This evidence was allowed for **experiment design only**; it was not the final embargoed graph reference. Four P2 cells failed the registered Step-0 gate. They were recorded as missing/failed design conditions and **not repaired, silently replaced or included** in the 12-cell evaluation.

The main evaluation used horizons $H=60,65,\ldots,240$ seconds, **37 per query**, 15 query conditions per eligible physical cell, or **555 correlated points per cell**. With 12 eligible cells, this yields 6,660 points per fully applicable M1/M2/M3 method. Each cell's separate final graph white-box reference used 1,000 trajectories, held back until global prediction freezing.

## 5.3 Execution chronology and integrity controls

The registered research pipeline was intended to flow from engineering smoke through I1 publication, Step-0 eligibility, reconstruction, blind graph prediction, global freeze, final WB and deterministic evaluation. The Phase-5 V3/V3b and FULL343 revisions occurred after examining specific *permitted* local/mass diagnostics but before the final graph WB was opened. This keeps an important end-to-end reference separation, **without** pretending the entire original V2 method was held constant.

The user-executed local B1 provenance audit found **94 passed checks, no failures or warnings, five informational statuses**. In particular, all 12 blind-prediction cell hashes matched the global freeze manifest, and all 12 final-WB cell manifests linked to the same freeze. The global prediction freeze was recorded on **7 October 2026 at 19:26:06 UTC**, before the earliest final white-box cell start at **19:51:50 UTC**, a gap of **25 minutes 43 seconds**. These are independently checked archived-manifest links and timestamps, not a formal information-flow proof.

The required engineering-smoke checks were ultimately completed, with four frozen PASS manifests marked **non-scientific**. Nevertheless, some mandatory supplemental checks were performed **after** early I1/Step0/M1/M2 scientific activity. This is a documented **sequencing deviation**, which later smoke completion does not retroactively erase. The repository separately records source commits, SHA-256 manifests and seed ranges. The external AICon/YAFS runtime currently resolves to the public September 2 commit, but a contemporaneous pristine imported YAFS build for every October execution has not been attested. Exact bitwise re-execution is therefore not claimed.

# 6. Research sequence and comparison validity

A reconstruction methodology cannot be evaluated independently of its development history. The main chronology is summarized below; exact paths and freeze IDs are supplied in Appendix B and the companion machine-readable registry.

| Stage | Event or revision | Inferential role |
|:--|:--|:--|
| Phases 1–2 | Physical generator and finite public I1 cards | Benchmark design and disclosure |
| Phase 3 | M0 public product and M1 inverse fitting | Method development |
| Phase 4 G1/G2 | M2 diversity selection and prospective graph stresses | Exploratory/prospective *within stage* |
| September pilot | M3 48/provider, weighted Top14, N200 reference | Frozen same-world benchmark |
| September post-hoc | Top1/Top3/support/weighting/hidden-parameter audits | Retrospective explanation |
| Phase-5 V2 | Four-world, four-graph protocol; 16 planned cells | Registered battery design |
| Phase-5 V3/V3b | Seven independent fit runs; common-N100 candidate ranking | Pre-final-WB method development |
| Phase-5 FULL343 | Replace Top14 after poor retained mass, before graph WB | Pre-graph-WB support revision |
| Phase-5 final | 12 eligible cells, N1000 final WB, deterministic comparison | Primary broad evaluation of executed V3b |
| Phase 6 | I1strong, I2a and I2b reconstruction variations | Post-main development on a known cell |
| October P2 | Public induced region, fit-fidelity and perturbation probes | Separate retrospective/development evidence |

Interpretations should be made **within a row** unless there is a justified same-population, same-budget and same-method cross-row comparison. No retrospective experiment is disguised as a registered test.

# 7. Historical fixed-graph pilot

## 7.1 Query population and reference

The original pilot held one hidden three-provider configuration, one fixed parallel-all graph, a workload period of 0.2 seconds and the public I1 card constant. Query difficulty was varied by scaling the latency and cost limits of a graph region induced from public local regions:

```math
A_G(\gamma,\rho)
=\{L_G\le\gamma\ell_G^{\rm base}(\rho),\
C_G\le\gamma c_G^{\rm base}(\rho),\
Q_G\ge q_G^{\rm base}(\rho)\}.
\tag{17}
```

Five thresholds times three difficulty regimes generated 15 queries. Evaluation used 37 horizons from 60 to 240 seconds. The pilot's fresh reference bank contained $N_{\rm WB}=200$ trajectories.

## 7.2 Prediction errors and conditional decisions

The original pilot production results were re-scored from saved pointwise tables and manifest-linked hashes:

| Method, pilot | Graph trajectories | Applicable points | MAE | RMSE | Signed bias |
|:--|--:|--:|--:|--:|--:|
| M0, applicable subset | 0 | 333 | 0.57204 | not included in principal comparison | -0.57204 |
| M1 | 100 | 555 | 0.18517 | 0.23074 | +0.18517 |
| M2, 27 equal members | 2,700 | 555 | 0.06815 | 0.09414 | +0.04737 |
| M3 pilot Top14, $B=1400$ | 1,400 | 555 | **0.03037** | 0.03578 | +0.02824 |
| M3 pilot Top14, $B=2000$ | 2,000 | 555 | **0.02755** | 0.03306 | +0.02447 |

*MAE, RMSE and bias are computed against the finite WB reference. Positive bias means optimistic prediction. M0 has a different applicable query set (9/15 queries, 333 horizon points), so its row must not be ranked directly against all 555-point methods. The main M3 graph-propagation budget B=1400 is 48.15% smaller than M2's 2700 trajectories, **not** proof of smaller end-to-end computational cost including provider fitting. The M0 RMSE value is deliberately not invented where the archived review does not report it as a reconciled principal comparison.*

An illustrative $\beta=0.90$ decision audit used reference-WB pointwise Wilson intervals to identify **481 reference-certain** query/horizon points among 555. Only **274** were M0-applicable and reference-certain. The historically observed agreements were **33.94%** (M0 on 274), **37.63%** (M1), **86.07%** (M2), **96.47%** (M3 B1400), and **97.09%** (M3 B2000), with the latter four computed on 481 points. These percentages are **descriptive conditional agreements against a finite WB reference**, not calibrated real-world admission success rates or independent-scenario accuracy estimates.

The pilot's M3 production errors were substantially smaller than those of M1/M2 in this exact world and graph. That is a genuine, archived numerical observation. It does not demonstrate the same numerical advantage in worlds with altered provider demand or different logical dependencies.

## 7.3 Retrospective support and weighting

A later frozen pilot Stage-B audit compared several estimators at matched total $B=1400$ in the same world:

| Retrospective pilot estimator | MAE | RMSE | Bias |
|:--|--:|--:|--:|
| Top1 B1400 | **0.02878** | 0.03406 | +0.02498 |
| Uniform14 equal-allocation B1400 | 0.05490 | 0.06570 | +0.05362 |
| Weighted14 equal-allocation B1400 | 0.04222 | 0.05016 | +0.04066 |
| Weighted14 production-allocation B1400 | 0.03037 | 0.03578 | +0.02824 |

Using the **same 14 model members and the same equal-allocation ledgers**, weighted versus uniform averaging is the cleanest isolated *weighting* contrast. However, the production versus equal-allocation comparison also changes seed/trajectory allocation; its difference is descriptive rather than a clean causal isolate. Top1 does slightly better than production weighted14 on this same retrospective fixed-world matched-budget test, which defeats any claim that *retaining more models is intrinsically necessary for point accuracy*.

The historical operational readouts also reported Top1 B100 and Top3 B300 MAEs near 0.0399 and 0.0401, respectively, but the direct underlying first-100 source arrays have not yet been independently reconciled in the B1 checks. They remain **reported historical numbers, not upgraded to primary independently checked evidence**.

## 7.4 Hidden-parameter audit and restricted cost frontier

The retrospective pilot Table 4 compared hidden generating parameters with M1 and M3-Top1 surrogate parameters and public-I1 reconstruction losses. The archived values were independently reconciled. Their discrepancies, including notably different Provider C reconstructions, show that **good graph prediction can co-occur with very poor recovery of hidden parameters in this one pilot**. They do not prove the public interface cannot identify those parameters in principle.

The historical Figure 2 labeled a curve the “nondominated” recurring-cost/MAE frontier while plotting only chosen primary prospective implementations. In the same reported two-coordinate cost plane, the retrospective operational Top1 at B100/MAE 0.0399 dominates M1 at B100/MAE 0.1852. Thus the original line is **not** the nondominated frontier over all reported operating points; it can only be described as the frontier of the *selected prospective primary set*, or it must be redrawn and annotated with retrospective status and additional provider-construction cost. This first B1 draft does not reuse the misleading frontier graphic.

# 8. Phase-5 multi-world, multi-graph evaluation

## 8.1 Eligibility and exact prediction population

Phase-5 planned 16 physical world-by-graph cells. Under the Step-0 eligibility/confirmation protocol, the four cells in world P2 failed. The remaining **12** cells cover worlds P1, P3, P4 across G_PAR, G_SEQ, G_SEQPAR and G_PARSEQ. Each has 15 frozen SLA queries, evaluated at 37 horizons; each has a distinct fresh $N_{\mathrm{WB}}=1000$ graph reference.

There is **no estimate for the preregistered P2 component of the Phase-5 directional heterogeneity contrast**. The later induced-public-region P2 study used a different query design and cannot be substituted into this missing prospective cohort.

## 8.2 Executed V3b method comparison

The Phase-5 evaluation used V3b-selected candidate banks: **M1 = one joint model, M2 = 27 equal-weight joint members, M3 = FULL343 weighted joint members**. The independently checked saved pointwise metrics are:

| Phase-5 executed V3b | Evaluated points | Graph trajectories/cell | MAE | RMSE | Signed bias |
|:--|--:|--:|--:|--:|--:|
| M0 on applicable subset | 1,776 | 0 | 0.41874 | 0.45392 | -0.41808 |
| M1 | 6,660 | 100 | 0.15702 | 0.22588 | +0.14968 |
| M2 | 6,660 | 2,700 | 0.13395 | 0.19045 | +0.10094 |
| **M3 FULL343** | **6,660** | **1,400** | **0.12189** | **0.18081** | **+0.06511** |

![Phase-5 aggregate MAE from verified frozen V3b pointwise results. The full 12-cell eligible battery contains 6,660 correlated horizon-query points per model. Different graph budgets apply: M1 100, M2 2,700 and M3 1,400 trajectories per cell. M0 is omitted because its applicable subset is different.](figures/phase5_aggregate_mae_v0_1.svg)

These are aggregate scores over the **12 eligible physical cells only**, not a population-generalization estimate. No method dominates all conditions. The remaining MAEs, even for M3, are substantial relative to probabilities bounded by one. The positive aggregate biases for reconstructed methods indicate a systematic tendency towards overprediction within this eligible design, though their magnitude varies with the condition.

Because M0 is defined on a smaller and selected applicable set, its aggregate MAE cannot be directly compared to the all-query rows. Moreover M1/M2/M3 have sharply different graph simulation budgets, so the aggregate ranking does not isolate simulation efficiency at equal cost, nor does the pre-WB change from Top14 to FULL343 permit a direct unchanged-algorithm replication of the September pilot.

## 8.3 Topology and provider-world effects

The prospectively specified topology statistic for each method and provider world was

```math
\Delta_P^M =
\operatorname{MAE}_M(P,G_{\mathrm{SEQ}})
-
\operatorname{MAE}_M(P,G_{\mathrm{PAR}}).
\tag{18}
```

The original directional masking hypothesis anticipated $\Delta_P^M>0$. The completed analysis did **not** yield that sign consistently across the eligible worlds: P1 differed in sign from P3/P4 for the examined contrast. It is therefore not supported as a universal or robust rule by this evaluation. A second registered heterogeneous-minus-symmetric contrast required P2 and was **not estimable** after Step-0 exclusion. The two other graph ASTs offer mechanistic triangulation but do not constitute a clean factorial manipulation separating workload shift from aggregation structure.

The score population consists of highly correlated repeated horizons and SLA queries drawn from a small number of fixed physical worlds. Across-world variation cannot be inferred from the number 6,660 as though each row were an independent physical deployment. A WB-reference bootstrap resamples the **complete trajectory/seed index** jointly across horizons, queries and shared-seed cells, keeping method predictions fixed. It addresses finite-$N_{\mathrm{WB}}$ reference fluctuation, **not model-selection uncertainty or future-world robustness**.

The scientifically material result is twofold: a weighted finite ensemble maintained a favorable aggregate *ranking* among the executed methods, and its **absolute prediction remained too inaccurate in several difficult regions** to claim dependable generic SLA estimation.

# 9. Post-main investigations: information, public regions and search

## 9.1 Phase-6 matched information–method pipelines

After Phase 5, the I1 strong-control and I2 experiments focused on **P4/G_SEQPAR**, using 15 queries × 37 horizons = 555 related points per method. They matched reconstruction search architecture (Sobol initialization followed by TPE refinement, frozen rescore banks) and 27-member equal-weight M2 graph propagation at **B=2700 per variant**, while altering the public interface and the corresponding reconstruction loss.

| P4/G_SEQPAR method | MAE | RMSE | Evidence status |
|:--|--:|--:|:--|
| **I1STRONG_M2** | **0.09178** | **0.11390** | Stronger I1 fitting |
| I2AFS_M2 | 0.09475 | 0.11826 | I2a/full marginal loss |
| I2B_M2 | 0.10210 | 0.13617 | I2b paired loss |
| I2BHIER_M2 | 0.09429 | 0.11695 | I2b hierarchical loss |
| I2BV4_M2 | 0.10854 | 0.15354 | I2b later weighting variant |
| I2BVAR_M2 | 0.15731 | 0.22086 | I2b variation-weighted loss |

![Phase-6 P4/G_SEQPAR matched-budget development comparison. All six rows use 555 related H-query points and 27-member M2 graph propagation at B=2,700; disclosed information and fitting losses vary together.](figures/phase6_matched_mae_v0_1.svg)

The stronger I1 control performs best or near-best among these **joint information–loss pipeline** variants in this cell. Richer information is not a monotone improvement *under the tested objectives*. This does not show that I2 information is useless, that an ideal I2 estimator cannot improve on I1, or that the comparisons are independent held-out validation: the P4/G_SEQPAR cell had already informed iterative I2 development.

Privileged known-provider/oracle studies and provider-factorial substitutions were additionally reported, but are not treated as deployable I1-only methods or as equivalently independently audited core results.

## 9.2 Distinct P2 public-induced-region comparison

The October P2/G_PAR study chose the graph admissibility region deterministically from the **same published I1 rectangles** for all three reconstruction methods. It evaluated five same-$\rho$ queries over 37 horizons, or **185 points per method**, with a new reference design distinct from the failed Phase-5 P2 Step-0 conditions.

| P2/G_PAR method | Native graph trajectories | MAE | RMSE | Bias |
|:--|--:|--:|--:|--:|
| M1 V3b | 100 | 0.13200 | 0.15332 | +0.04149 |
| M2 V3b | 2,700 | 0.14058 | 0.16371 | +0.13791 |
| M3 V3b FULL343 | 1,400 | **0.12787** | **0.14853** | +0.04263 |

Here all three methods receive **the same** $A_G^{I1}$ and differ in process reconstruction and subsequent graph prediction. Hence no difference above measures graph-region reconstruction quality. The simulation budgets are **unmatched**; M3's small observed MAE advantage does not establish equal-cost superiority. This study cannot be read as a post-hoc repair of four earlier ineligible P2 cells.

## 9.3 Privileged search-deficit diagnosis

A separate P2 audit evaluated the actual hidden provider parameters against the public I1 target using the **same $N=100$ rescore and independent replay bank** as the finite reconstruction candidates. For each of three providers the true parameter vector was inside the search domain, yet it achieved better I1 RMSE than the selected best available V3b candidates:

| P2 provider | True $\theta$ rescore RMSE | Selected-best rescore RMSE | True $\theta$ replay RMSE | Selected-best replay RMSE |
|:--|--:|--:|--:|--:|
| A | **0.03443** | 0.10961 | **0.03151** | 0.12247 |
| B | **0.05337** | 0.17780 | **0.08178** | 0.18344 |
| C | **0.06110** | 0.13099 | **0.08437** | 0.12106 |

The registered seven-by-25-trial search generated **525** total provider trials across three providers. If the generating parameters fit the disclosed evidence better than the selected candidates despite being searchable in principle, then the executed **search and ranking procedure failed to find a comparatively favorable fit** under this test. This is a concrete optimization/inference failure mode.

It remains possible for a public interface to be non-identifying in some formal sense; however this particular evidence cannot prove that non-identifiability caused the observed prediction error. A 42-configuration, two-seed-bank $\pm20\%$ one-at-a-time local perturbation audit additionally measured finite objective sensitivity; it neither identifies the full local Hessian nor proves uniqueness or global optimizer convergence.

# 10. Uncertainty mathematics and cross-experiment interpretation

## 10.1 Numerical Monte Carlo precision

For a fixed reconstructed ensemble with normalized weights $\alpha_j$ and estimates $\widehat p_j$, let $\widehat p_M=\sum_j\alpha_j\widehat p_j$. The variance identity is

```math
V_{\rm MC}(\widehat p_M)
=\sum_j\alpha_j^2 V_j+
2\sum_{j<k}\alpha_j\alpha_k C_{jk}.
\tag{19}
```

The covariance $C_{jk}$ matters for **M2's shared seed indices**. A seed-index paired bootstrap should resample each 27-member seed-vector as one unit rather than resampling individual member trajectories independently. M3's independent member seed streams permit the simpler variance form in Eq. (15), conditional on fixed weights, models and allocation.

The pilot's numerical-width appendix used Wilson intervals for fixed single-model binomial curves, paired percentile resampling for M2 and a normal approximation for M3 using a **worst-case variance**. The variance bound itself is conservative; the resulting **normal-approximation 95% interval is not an exact distribution-free confidence interval**, particularly when the FULL343 allocation leaves some models with only one trajectory. All such intervals are **pointwise** over $(A,H,\rho)$ and conditional on the reconstructed method, not simultaneous over 555 or 6,660 correlated queries.

A rigorous fixed-sample conditional alternative, if required in later work, can be derived from a weighted Hoeffding inequality for independent bounded member outcomes, but this was **not an evaluated new estimator** in the frozen experiments. Sequentially peeking at ordinary fixed-sample intervals until a threshold is crossed does not preserve nominal coverage without a separately specified anytime-valid procedure.

## 10.2 Model dispersion is a distinct diagnostic

Let $p_j=E[\widehat p_j]$, $p_\alpha=\sum_j\alpha_jp_j$ and $\widehat p=\sum_j\alpha_j\widehat p_j$. The observed finite-ensemble dispersion is

```math
V_{\rm raw}
=\sum_j\alpha_j(\widehat p_j-\widehat p)^2.
\tag{20}
```

Under fixed weights and unbiased member estimators, its expectation equals latent finite-model spread plus a contribution from numerical sampling,

```math
E[V_{\rm raw}]
=\sum_j\alpha_j(p_j-p_\alpha)^2+
\sum_j\alpha_j\operatorname{Var}(\widehat p_j)
-\operatorname{Var}(\widehat p).
\tag{21}
```

The manuscript's nonnegative MC-subtracted plug-in diagnostic estimates only the *spread among the selected models*. The max-with-zero clipping and finite member budgets make it neither an unbiased calibrated risk estimate nor a guaranteed bound on model-to-hidden-world error.

Similarly, if the method predictor and white-box reference are independent and individually unbiased for their conditional targets, then

```math
E\!\left[(\widehat p_M-\widehat p_{\rm WB})^2\right]
=(p_M-\sigma_G)^2+V_{\rm MC,M}+V_{\rm WB}.
\tag{22}
```

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

## 10.3 Cross-experiment lessons

**Candidate search is a plausible limiting mechanism, demonstrably so in P2.** The fact that true parameters better fit I1 than selected candidates makes the inverse search procedure a high-priority diagnosis. It does not eliminate other causes of graph discrepancy, including information compression and model-family restrictions.

**Ensembling is neither futile nor proved necessary.** The pilot same-support weighting test favored nonuniform public-evidence weights over uniform weights, while pilot Top1 slightly outperformed the larger weighted mixture at a matched budget. In the larger Phase-5 study M3 FULL343 had the best aggregate MAE but still made sizeable errors. The data support context-dependent method performance, not a model-count law.

**Richer disclosure is not sufficient by itself.** The I2 development variants were matched in broad search effort but changed loss functions and used an already studied cell. Their results test implemented pipelines, not the optimal value of their disclosed statistics.

**Graph structure matters without a simple universal directional rule.** A registered serial-versus-parallel masking prediction did not retain one direction across eligible worlds. The finite design does not identify a universal composition-graph error mechanism.

**Numerical convergence is insufficient for dependability.** Larger graph budget can reduce finite simulation noise without changing bias due to model/search error. No threshold band yet covers the total uncertainty required for a certified real-service admission decision.

# 11. Threats to validity and reproducibility

**Finite physical setting.** The core study uses three providers and four logical ASTs on a fixed physical embedding. It does not generalize by itself to arbitrary service graphs, cross-region placement, multi-tenant failures, dynamic routing or real production deployments. The provider generators and fitted process family are related; robustness to substantial model misspecification is not established.

**Limited observables.** I1 is deliberately compressed and empirical. Region construction was calibrated in frozen simulated worlds; its disclosure noise and dependence on the acquisition policy can affect inverse fits. Quality and power are part of the broader conceptual LCQ/continuum setting but not demonstrated as independent varying stress dimensions here.

**Condition selection and missing P2.** The Phase-5 registered Step-0 eligibility gate failed for P2 and removed four of 16 intended physical cells. Main 12-cell estimates are **conditional on eligibility**, not estimates of all planned or unseen worlds. The P2-derived retrospective tests use new query regions and are not missing-data imputation.

**Method changes and development leakage.** V3, V3b and FULL343 changed model search, selection and support after earlier development evidence. The final graph WB was held back behind a hashed global prediction freeze, and archived timestamps/hash links were checked, but this does not restore the stronger status of having all methods fixed before every component of experimental evidence was observed. The same cell was reused while developing Phase-6 I2 variants.

**Budget and correlation.** M1/M2/M3 graph budgets differ (100/2700/1400); their numbers of locally simulated trajectories and method fitting time differ as well. The 555 and 6660 curve points share trajectories and query structure. Reference bootstrap and per-method numerical error do not simultaneously quantify scenario selection, model-search and physical-world extrapolation uncertainty.

**Engineering and software provenance.** The modified composition controller is in an external AICon/YAFS repository. The local current dependency revision and source SHA fingerprints were recorded, but exact clean-tree/source-lock provenance at each archived October run was not recovered. Several required smoke checks were completed only after early scientific work, a sequencing deviation documented in the audit. The Phase-5 graph simulator received optional trace-exposure updates after main runs, so current repository HEAD alone does not identify the historical program state.

**Numerical evidence tier.** Primary saved result summaries and selected hashes have been independently checked against existing pointwise artifacts. This is not complete bitwise replay from every raw YAFS request event. Some ancillary historical pilot operating-point curves and an M2 paired-bootstrap width remain as reported source claims rather than independently recomputed numerical evidence. No statement above requires inventing their raw observations.

**External literature and coauthor consent.** The bibliography is inherited from the source manuscript and is **provisional**. References, citation details, current related work and venue overlap policy must be verified before any public release. This draft is internal and does not constitute coauthor approval for arXiv posting.

# 12. Conclusions and falsifiable next questions

The PRAISE program implemented a discrete-event native composition benchmark, finite public provider SLA disclosures and multiple reconstructed-model integration procedures. It established robust provenance for important frozen outputs, including a hash-frozen prediction/reference separation in the broad Phase-5 battery. The favorable single-world pilot numerical findings were genuine, but the broader evaluation showed **material residual prediction errors** and did not establish general reconstruction sufficiency.

The most actionable scientific questions now concern mechanisms rather than adding model members indiscriminately:

1. **Search recoverability:** When true generating parameters lie inside the search domain and fit I1 markedly better, which proposal distributions, loss landscapes or structural changes allow a public-only learner to find equivalent-quality fits with modest budget? This must be tested with a frozen search protocol and separate end-to-end graph reference.
2. **Information conditional value:** Can a fixed reconstruction objective/architecture be defined so that I1 and I2 disclosures differ *only* in the information made available, permitting an interpretable matched-information comparison?
3. **Graph sensitivity:** Which structural or workload conditions amplify small provider-level errors into end-to-end SLA error, and can the resulting condition be predicted using **publicly observable** quantities rather than privileged white-box outcomes?
4. **Finite-model approximation:** Under what observable diagnostics does Top1 suffice, when do additional hypotheses help and when does weighting mislead? Any rule proposed from a development world must be frozen and tested on other worlds.
5. **Decision calibration:** Can a method produce externally validated error coverage for the hidden graph SLA under clearly limited assumptions? This is a separate problem from making the Monte Carlo standard error small.

These questions are **future hypotheses**, not positive claims established by the existing evaluation. As a scholarly technical record, B1 can support a later focused methodological manuscript by providing precise definitions, method versions, extended experiments and explicit negative outcomes. Publication as a citable preprint remains a subsequent coauthor and venue-policy decision.

# Appendix A. Mathematical and numerical interpretation

## A.1 Finite-portfolio admission envelopes

For a specified, finite method-generated set $\mathcal M_M$ of joint stochastic models, define

```math
\sigma^{-}_{G,M}(A,H;\rho)=\min_{\vartheta\in\mathcal M_M}
\sigma_G(A,H;\rho\mid\vartheta),\qquad
\sigma^{+}_{G,M}(A,H;\rho)=\max_{\vartheta\in\mathcal M_M}
\sigma_G(A,H;\rho\mid\vartheta).
\tag{A1}
```

If $\beta\le\sigma^-_{G,M}$ then *all enumerated models* accept under their own ideal probabilities; if $\beta>\sigma^+_{G,M}$ all reject; otherwise there is disagreement among the finite set. This is a direct statement about the chosen set, **not** a calibrated confidence set, structural-identifiability theorem or SLA truth guarantee. Estimates of the extrema from finite graph simulations add MC error that is absent from this idealized algebra.

## A.2 Conditional numerical precision and model spread

The general covariance identity (19) holds for fixed finite weights. M2's paired common-seed bootstrap captures cross-model covariance; M3's independent-member variance bound (15) is conditional on the model bank and frozen weight rule. For a fixed sample allocation and truly independent bounded member outcomes, a weighted Hoeffding inequality gives

```math
\Pr\bigl(|\widehat p-p_\alpha|\ge\varepsilon\bigr)
\le 2\exp\left(-\frac{2\varepsilon^2}{\sum_j\alpha_j^2/N_j}\right),
\tag{A2}
```

yielding a fixed-sample half-width

```math
\varepsilon_\delta=
\sqrt{\frac12\ln(2/\delta)\sum_j\frac{\alpha_j^2}{N_j}}.
\tag{A3}
```

This is included as an *analytical consequence of standard bounded-variable concentration*, **not** a newly tested method or a bound on $|p_\alpha-\sigma_G|$. It is not automatically anytime-valid if sample sizes are chosen by repeatedly observing the outcomes.

The historical noise-adjusted model-spread quantities and white-box correction (20)–(22) are expectation-based diagnostics. Positive-part corrections may be convenient but must not be described as exact interval widths for physical model misspecification.

## A.3 Numerical-width scaling

The historical precision appendix extrapolated mean **pointwise interval width** approximately as $\overline W(B)=c/\sqrt B$, holding support, allocation and the simulation experiment fixed, so that a target width $w^\star$ corresponds formally to $B^\star\approx(c/w^\star)^2$. The pilot anchors were approximately M1 B100/width 0.0375; M2 B2700/width 0.0563 (not independently reproduced here from per-seed paired bootstrap arrays); M3 Top14 B1400/width 0.0493 and B2000/width 0.0425, using **interval clipping to [0,1]** for the reported M3 widths. These are illustrative numerical precision projections, **not evaluated accuracy-versus-budget forecasts**, and they exclude provider reconstruction expense and persistent model bias.

# Appendix B. Archived source and audit provenance

## B.1 Canonical authority hierarchy

For experimental assertions: frozen experiment contract plus source implementation and selected archive manifests/pointwise tables take precedence over later commentary. The numerical checks verify historical saved outputs, not new simulation. For mathematical definitions, the implementation and mathematical audit take precedence over loosely worded pilot-era prose.

The following documents in \`first_science/b1/\` are the companion reproducibility record:

- \`evidence_registry_v1_0.json\`, E01–E12, machine-readable study roles, versions, source paths, numerical values and caveats;
- \`METHOD_VERSION_CHRONOLOGY_2026-10-16.md\`, Phase1–6 and October P2 stage order;
- \`PHASE4_VERIFICATION_REVIEW_2026-10-16.md\`, independent pilot and Stage-B pointwise checks;
- \`VERIFICATION_REVIEW_V0_3_2026-10-16.md\`, Phase5/Phase6/P2 verified saved metrics;
- \`TABLES_FIGURES_SOURCE_RECONCILIATION_2026-10-16.md\`, 22 original source files, Table2–4 and Fig2–3 checks;
- \`METHOD_SUPPORT_VERIFICATION_REVIEW_2026-10-16.md\`, 132 V3b selection/allocation checks;
- \`SIMULATOR_PROVENANCE_AUDIT_2026-10-16.md\` and \`RUNTIME_PROVENANCE_VERIFICATION_REVIEW_2026-10-16.md\`, code scope, smoke sequencing, 94-pass stage/hash audit;
- \`UNCERTAINTY_MATHEMATICS_AUDIT_2026-10-16.md\`, exact and approximate interval/variance results;
- \`FINAL_AUDIT_SIGNOFF_2026-10-16.md\`, conditional drafting authorization and unresolved publication gates;
- \`MANUSCRIPT_CLAIM_AUDIT_V0_1.csv\`, 68 claims and required dispositions.

### Audited integrity milestones

| Artifact | Verification |
|:--|:--|
| Initial B1 inventory | 31 source files and 17 data roots available; 233 manifests inventoried |
| Phase5/6/P2 saved-results reconciliation | 399 passed, zero failed |
| Phase4 pilot and Stage-B reconciliation | 60 passed, zero failed |
| Phase5 V3b member selection/allocation | 132 passed, zero failed |
| Historical pilot source display archive | 22/22 collector hashes and 13/13 checked scientific output hashes match |
| Phase5 runtime/reference chain | 94 passed; 12/12 prediction hashes and 12/12 WB freeze backlinks |
| Historical source paper | 26-page \`v11_45\` PDF, preserved and not overwritten |

## B.2 Version-dependent costs and seeds

Reproducing the Phase-5 executed comparison requires the source at the **archived PRAISE code_commit**, the external modified YAFS/AICon dependency, the public I1 provider cards, V3b selected provider-model and joint-support tables, the frozen graph ASTs, original Step-0 eligibility, named seed banks and archived graph prediction manifests. The final-WB source enumerates **54000–54999** per eligible physical cell. M1/M2 share one method-wide graph seed-index bank in the executed design and M3 uses separate rank-specific blocks. No missing seed or archived experiment is reconstructed in this draft.

For a future reproducibility package, the already assembled B1 tools can extract exact manifest and source hashes without touching frozen data. Current installed source fingerprints are useful but cannot replace a historical environment lock if byte-for-byte results are desired.

# Appendix C. Provisional literature references

**Bibliographic status:** The entries below are transcribed or lightly reformatted from the historical October 2 manuscript. They provide a sourced scholarly starting point, **not a newly completed verification of every author, venue, year or DOI**, and do not claim exhaustive coverage of 2026 research.

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
