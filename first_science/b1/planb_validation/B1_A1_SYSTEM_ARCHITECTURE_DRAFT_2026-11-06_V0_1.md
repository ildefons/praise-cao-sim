# A1 — End-to-end architecture for budget-aware selection of composed-service predictors

**Date:** 6 November 2026  
**Status:** Systems-paper architecture **draft v0.1**, pending researcher review and module-by-module implementation audit. No new runtime implementation is implied.  
**Parent agenda:** [Route A–first dual-track research agenda](B1_DUAL_TRACK_RESEARCH_AGENDA_2026-11-06_V1.md).  
**Companion:** [A2 systems novelty audit](B1_A2_COMPUTING_CONTINUUM_SYSTEMS_NOVELTY_AUDIT_2026-11-06_V0_1.md).

## 1. The decision, stated at the correct system level

Given a **composed service** specified by a graph G, an SLA/admissibility request A and horizon H, and partial disclosures from its constituent providers, several candidate composition-prediction methods M may produce different estimates of the compliance-success probability sigma_G(A,H;rho). The system-level validation task is **not** to select a service, a resource or a graph. It is to use limited validation evidence to **select an appropriate prediction method** for the system / study domain.

There are **two distinct decisions**, which must not be conflated:

1. **Prediction:** method M_i maps provider information + graph/request into an estimated composed-service success probability \hat sigma_i(G,A,H;rho).
2. **Method selection:** a finite-budget evaluator gathers evidence of the accuracy of competing M_i over prespecified worlds × graph conditions and recommends a method \hat i_B using a terminal criterion (currently equal-cell mean MAE across 12 cells).

**Scope qualification:** the current B1 test chooses **one overall predictor** for the evaluated 12-condition domain, not a different predictor for every incoming graph or SLA request. Per-request/per-graph routing, online self-adaptation, real provider telemetry ingestion and live orchestration integration are prospective architecture extensions, **not demonstrated results**.

## 2. Architecture diagram — evidence and decision flow

~~~mermaid
flowchart TB
  subgraph INPUT["Problem and provider information"]
    G["Service composition graph G and requested A,H,rho"]
    I["Provider disclosures / interface contracts I"]
    REG["Candidate predictor registry M0–M3 variants"]
  end
  subgraph PRED["Composed-service prediction"]
    P["Prediction adapters: consume G,A,H,rho and admissible provider evidence"]
    O["Predicted sigma values / compliance estimates"]
  end
  subgraph EVAL["Offline validation and method selection — demonstrated as archive replay"]
    CAT["Eligible validation catalogue: predictor x world x graph"]
    ACQ["Budget controller: Random / Balanced / Informed / Top2 / KG and new two-stage variants"]
    REVEAL["Validation evidence provider: archived per-cell predictor MAE (one action at a time)"]
    POST["Common statistical decision model: posterior over predictor mean MAE"]
    REC["Terminal recommendation: predictor with smallest posterior mean domain error"]
  end
  subgraph OUT["Outputs and boundaries"]
    SELECT["Selected prediction method + evaluation budget + evidence provenance"]
    CONSUMER["Possible future decision consumer / orchestration integration (NOT implemented by B1)"]
    AUDIT["Research-only full matrix and white-box reference; evaluator cannot see hidden entries"]
  end
  G --> P
  I --> P
  REG --> P
  P --> O
  P -.-> CAT
  G --> CAT
  CAT --> ACQ
  POST --> ACQ
  ACQ -->|"request an unevaluated (method,condition)"| REVEAL
  REVEAL -->|"revealed MAE for that one cell"| POST
  POST --> REC
  REC --> SELECT
  SELECT -.-> CONSUMER
  AUDIT -.->|"offline scoring only, never policy foresight"| REC
  AUDIT -.-> REVEAL
~~~

**Diagram semantics.** Solid arrows connect established logical or implemented computation/data roles. Dotted arrows identify *offline evaluation coupling* or a potential future integration. In particular, the full MAE matrix and WB reference are available only to the replay oracle and retrospective evaluator; the allocation controller never consults unseen entries.

## 3. Exact functional contracts and implementation maturity

| Block | Input | Output | Verified status / constraints |
|---|---|---|---|
| Composition specification | graph G (PAR, SEQ, PARSEQ, SEQPAR in current battery), requested A,H,rho | predictor request | Composition and request semantics implemented upstream; do not turn experimental graph set into claimed support for arbitrary DAGs. |
| Provider evidence adapters | I1 static, I2a marginal, I2b paired-window, I5 white-box (each with its own disclosure meaning) | admissible information for prediction and validation | Interface definitions and individual experimental comparisons exist upstream. **B1's seven-method matrix does not demonstrate every interface-method combination**. I5 is the reference oracle for evaluation, not a cheap normal disclosure or allocation feature. |
| Predictor registry / execution | provider evidence, composition graph, query | composed-service probability estimate | Existing M0 analytic / M1 one-model / M2 3x3x3 / M3 weighted candidate families; B1 uses a *frozen seven-method subset* of M1/M2/M3 variants, not M0 nor all I variants. |
| Validation reference | WB outcome evidence, predictor-specific pointwise errors | MAE for one eligible method–condition entry | Complete 7×12 matrix verified from archived sources; **the current allocator replays fixed MAEs** and does not launch a simulation or online measurement. Each observation is one *already aggregated* cell MAE (over 555 query-horizon points). |
| Feasible action catalogue | 7 candidate predictors × 12 eligible conditions | masked list of unevaluated (a,c) pairs | 84 nonrepeatable choices; all seven evaluated initially on the same condition; budgets B=10,15,20,30,40 inclusive. P2 is excluded by historical eligibility gate, not quietly imputed. |
| Acquisition controller | observed action history; frozen surrogate posterior; budget remaining | next method–condition pair | Random, Balanced, Informed and Top2 in original experiment; separate joint KG and new matched two-stage KG/Top2 in supplementary experiments. Two-stage policy variants have **different arm-selection rules** than historical joint-action policies. |
| Bayesian evaluation model | observed per-cell MAEs + provider/graph indicators | per-arm posterior mean and covariance for whole-domain MAE | Gaussian additive, independent per predictor, fixed heuristic priors and observation SD; not demonstrated calibrated probability or robustness to interactions. |
| Final method choice | posterior mean over same 12 equally weighted cells | argmin posterior mean method + derived retrospective regret | Executed by episode replay. The final regret needs the **full hidden archive** only for retrospective scoring, not online prediction of future errors. |
| System integration | selected predictor and provenance | potential use by composition decision maker | **Conceptual boundary.** No claim of a deployed orchestration loop, switching engine or signed SLA certificate from current B1 evidence. |
| Reproducibility | hashes, source records, seeds, policy definitions, bootstraps | traceable B1 report, figures, replay results | Original scripts and five-policy results preserved. Controlled two-stage summaries/plots committed; its full action histories are local and hash-recorded, not all in Git. |

## 4. Interfaces: preserve I + M factorization, avoid a misleading global algorithm list

An upstream prediction pipeline has two orthogonal design axes:

- **Provider information interface I**: controls what statistical or temporal evidence is available about individual providers (I1 static; I2a marginal; I2b paired-window; I5 WB reference).
- **Composition/prediction method M**: specifies how admitted evidence is propagated or combined over G (M0 analytic, M1 single provider, M2 small equal-weight ensemble, M3 weighted model family).

The seven predictors in B1 are **frozen concrete algorithmic variants** (including full M3 and Top14/Top1 and fixed-CV variants), not seven distinct I interfaces nor seven independent “models” in the sense of seven unrelated learning architectures. Eligibility and methods must be represented as a matrix of *actually supported combinations*, not a fiction that every I can be coupled with every M.

This distinction matters for systems positioning: the method-selection layer operates **above** provider-information and graph-prediction mechanisms; it is a validator/selector of predictors, not their substitute.

## 5. Formal target and the system's decision

Define archived per-cell loss Y_{a,c} as the MAE of predictor a against the applicable WB reference over the fixed query × horizon grid in condition c. For the completed experimental domain, C=12 (3 provider worlds × 4 graphs) and K=7. The whole-domain target is

\[
  \mu_a = \frac{1}{C}\sum_{c=1}^C Y_{a,c},\qquad
  a^\star=\mathop{\mathrm{argmin}}_a\mu_a.
\]

A sequential evaluator at B total distinct observations returns \hat a_B. Its retrospective terminal simple regret is

\[
 r_B = \mu_{\hat a_B}-\mu_{a^\star}.
\]

Each episode begins with K evaluations on **one shared condition**, meaning only B-K actions are selected sequentially. Every observation action (a,c) is unique. The experiment currently assumes equal cost per action **as an abstraction**; different predictor/graph methods can require substantially different computation in reality.

**Crucial operational distinction:** selecting a predictor by *offline* domain-averaged MAE is not a per-request SLA assurance, and a lower expected selection regret does not directly imply fewer SLA violations in a running application. Real deployment requires a formal connection between selected predictive performance and the downstream composition decision.

## 6. Logical application sequence

1. Specify a composed-service family and client requirement (G,A,H,rho).
2. Establish provider disclosure contract and admissibility (which I levels are available and which methods can legitimately consume them).
3. Construct a candidate set of composition-level prediction methods; obtain predicted compliance probabilities for relevant requests.
4. Define a validation population of provider worlds × graphs × query/horizon grids, and a credible independent WB reference. **This population is a pre-specified evaluation target**, not something the policy adaptively changes.
5. Initialize the sequential evaluator by revealing each candidate's archived loss on a common condition.
6. For each remaining budget action, choose an unevaluated predictor–condition pair; reveal its validated loss; update statistical beliefs; repeat.
7. Recommend the predictor with the lowest posterior mean equal-cell loss.
8. Retrospectively score regret on the full WB archive; report source provenance and bootstrap uncertainty.
9. **Prospective only:** use selected predictor in a service design/orchestration workflow; monitor drift and trigger periodic reselection when justified.

**Implemented vs envisaged.** Steps 1–3 and WB generation exist across upstream PRAISE experiments; steps 4–8 are integrated *offline* by the B1 replay harness and its source matrix. Step 9 is a target architecture, not observed system behavior.

## 7. Architecture-to-experiment evidence map

| Architecture claim | Existing supporting artifact | What remains unshown |
|---|---|---|
| Multiple competing prediction methods can estimate composed-service outcomes | upstream M1/M2/M3 provenance and verified 7×12 archive | independent fresh-world transfer and actual service selection consequences |
| Evaluation can be allocated adaptively under finite budget | [B1 consolidated report](B1_CONSOLIDATED_SCIENTIFIC_EVIDENCE_V0_1.md) and [five-policy figure](figures/b1_five_policy_regret_vs_budget_ci_v1.svg) | resource/time-based efficiency and external generality |
| Acquisition of informative conditions adds value | [two-stage controlled study](B1_CONTROLLED_CONDITION_SELECTION_RESULTS_2026-11-06.md) and [matched seven-policy figure](results/controlled_condition_ablation_v1/b1_controlled_seven_policy_regret_vs_budget_ci_v1.svg) | robust inference under provider–graph interactions; no original joint-action component isolation |
| A selected predictor can be operationalized in a deployed orchestrator | none in current B1 evidence | adapter API, integration demonstration, online drift/feedback and governance |

## 8. Specific architectural gap to close for a workshop

A reviewer should be able to distinguish *method selection* from *service composition*. The workshop paper must show (i) a clear input/output decision at this layer, (ii) an exact mapping from provider disclosures to candidate predictors, (iii) which components have actual executable code, and (iv) quantitative evidence for which system decision changes under a limited evidence budget. A deployment demonstrator is desirable but **not a precondition for a carefully scoped offline systems-methodology workshop paper**.

Before freezing Figure 1 for a paper, audit the actual repository code paths implementing each upstream provider-interface and M-method pairing. Do **not** draw arrows suggesting a production end-to-end service where the integration only exists as independently executed components and retrospective CSV adapters.

## 9. Next A1 actions

- Audit the exact I×M compatibility matrix against source manifests/scripts, avoiding inference from labels alone.
- Provide one worked example: graph G_PARSEQ with a concrete admissible query, three candidate predictors, one warm-start condition, one additional budget action and terminal predictor recommendation; use actual archived values if published, otherwise mark the example schematic.
- Decide and explicitly define the **system user** (service designer, validation engineer or orchestrator) and the **moment of selection** (offline validation before deployment vs online adaptation). The current evidence supports an *offline validation engineer's method recommendation*.
- Prepare an architecture figure suitable for a 6–8-page workshop paper after the implementation audit.
