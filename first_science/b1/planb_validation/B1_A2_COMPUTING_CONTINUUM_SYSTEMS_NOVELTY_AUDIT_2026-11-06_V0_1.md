# A2 — Computing-continuum systems novelty audit (draft v0.1)

**Date:** 6 November 2026  
**Status:** INITIAL SYSTEMS-LEVEL RELATED-WORK ASSESSMENT — **CONDITIONAL GO** for a properly scoped workshop submission; not an exhaustive systematic review or a full-conference acceptance assessment.  
**Companion:** [A1 end-to-end architecture](B1_A1_SYSTEM_ARCHITECTURE_DRAFT_2026-11-06_V0_1.md).  
**Scope boundary:** This is separate from [G1 algorithmic BAI novelty audit](B1_G1_NOVELTY_GAP_AUDIT_2026-11-06_V1.md). Systems integration can constitute a contribution without a new BAI theorem, but must be compared against existing systems.

## 1. Which existing research question is ours?

**PRAISE task:** Given a portfolio of composition-level *prediction methods*, provider disclosure constraints and a finite validation budget, choose **which predictor to use** based on selectively acquired evidence of accuracy across provider-world × composition-graph scenarios.

**Not the same tasks:** (i) choose a service instance, (ii) choose a workflow composition, (iii) allocate infrastructure resources, (iv) predict individual service QoS with one fixed model, (v) adapt deployment to latency. Those are highly relevant neighbors but answer different downstream decisions.

**Most defensible candidate systems contribution:** a reproducible **validation-management layer** between partial provider evidence / service graph models and a subsequent autonomic provisioning decision. This layer exposes an explicit predictor portfolio, scarce nonrepeatable validation actions, and a system-level recommendation rather than assuming the QoS predictor is predetermined.

This is a *candidate* differentiation, not a proof that no similar system exists.

## 2. Closest systems literature

**Source quality rule:** These are traceable publisher/venue papers, not generic related-work headings. Where a feature is not reported in the accessible article/abstract, say **“not established from this source”**, not “does not exist.” A complete novelty claim needs a full-text check and backward/forward citation search.

| Work | Established contribution | Overlap with PRAISE | Main differentiation / caveat |
|---|---|---|---|
| **Pozas García et al. (2023), “Location-aware scalable service composition,” Software: Practice and Experience** ([DOI](https://doi.org/10.1002/spe.3260)) | Composition heuristics/genetic methods plus empirically learned **decision tree selecting the most suitable composition algorithm by scenario**, reflecting no universal winner. | **Very close algorithm-portfolio SYSTEMS idea**: selecting an algorithm for a continuum service-composition problem. | Its *selected object* is a **service-composition optimization algorithm**, not a composition-performance predictor. Its decision tree is trained from benchmark results; finite-budget *sequential selection of validation cells* is not established as part of its main reported method. **Cannot claim “first to select methods for continuum services.”** |
| **Stupar & Huljenic (2023), “Model-based cloud service deployment optimisation method for minimisation of application service operational cost,” Journal of Cloud Computing** ([DOI](https://doi.org/10.1186/s13677-023-00389-8)) | Context metamodel, QoS/cost prediction models, evaluation of multiple ML methods, deployment-cost optimization under SLAs. | Strong integration of service prediction, model comparison and deployment decisions. | Final system decision is *deployment*, not finite-budget recommendation of one composition predictor; requires careful review to rule out automated surrogate/model selection mechanisms. |
| **“Equilibrium in the Computing Continuum through Active Inference” (2024), FGCS** ([DOI](https://doi.org/10.1016/j.future.2024.05.056)) | Collaborative edge intelligence for SLO assurance, learning causal environment relations, transferring/combining models and adaptive offloading. | Heterogeneous models, SLO-driven decisions and continuum architecture. | Focus is decentralized control and SLO satisfaction; finite costly **validation budget to choose a composition predictor** is not established by available abstract. **Potentially close systems comparator** for architecture. |
| **Bonilla et al. (2026), “A framework for the predictive monitoring and data quality assurance in the cloud continuum,” Journal of Cloud Computing** ([DOI](https://doi.org/10.1186/s13677-026-00881-x)) | EdgeGuard agent with predictive monitoring of multiple metrics, data quality and continuum infrastructure, evaluated on heterogeneous devices. | Prediction and feedback integration across continuum tiers. | Monitoring and anomaly/preventive control rather than choosing among competing composition-level prediction methods. **System maturity comparator**: PRAISE should not claim a deployed monitoring loop based only on replay. |
| **Aalikhani et al. (2026), “Dynamic cloud manufacturing service composition based on runtime QoS prediction,” Computers & Industrial Engineering** ([DOI](https://doi.org/10.1016/j.cie.2025.111701)) | Predictive process monitoring plus dynamic service selection with runtime QoS prediction and a networked-lab case study. | Connection of prediction to actual composition decisions. | Selects service/resources, not predictors through a finite offline validation campaign; comparison places pressure on our end-to-end *systems* claims. |
| **“Service Selection under Uncertainty” (2025), Computers & Operations Research** ([DOI](https://doi.org/10.1016/j.cor.2024.106847)) | Calculates probabilities of SLA violations and optimizes cloud service selection under uncertainty, with DP, ILP and heuristic algorithms. | **Very close SLA-probability/uncertainty domain**. | Different selected object (services rather than prediction methods); independently important precedent for using probabilistic SLA composition and service-selection algorithms. Do **not** claim novel SLA violation probability as such. |
| **“Hybrid based QoS-aware selection of web services compositions” (2026), FGCS** ([DOI](https://doi.org/10.1016/j.future.2025.108007)) | Architecture for composition selection, formal graph patterns, probabilistic relations and quality aggregation. | Close to the service-graph and uncertainty layer. | Selects the **service composition**, not which competing estimator of its behavior to validate and use; composition-model fidelity is an important architectural baseline. |
| **Mao et al. (2024), “QoS prediction of cloud services by selective ensemble learning on prefilling-based matrix factorizations,” Concurrency and Computation** ([DOI](https://doi.org/10.1002/cpe.8282)) | Selectively ensembles multiple predictor models to estimate incomplete service QoS tables. | **Very close predictor portfolio** intuition and missing QoS data. | Combines prediction-model estimates, not budgeted evaluation of *composition-prediction* alternatives across world×graph cases. **Cannot claim the basic notion of selecting predictors is new.** |
| **“A two-phase learning approach integrated with multi-source features for cloud service QoS prediction” (2025), Frontiers of Engineering Management** ([DOI](https://doi.org/10.1007/s42524-025-4038-x)) | Prediction of QoS from sparse, multi-source cloud-service data. | Partial evidence and model choice in QoS domain. | Main objective is predicting missing service QoS; not a finite-budget meta-validation system (from source's reported method). |
| **Kossen et al. (2021), “Active Testing: Sample-Efficient Model Evaluation,” ICML** ([proceedings](https://proceedings.mlr.press/v139/kossen21a.html)) and **Hara et al. (2024), “Active Model Selection”** ([journal](https://link.springer.com/article/10.1007/s10994-024-06603-1)) | Active acquisition of evaluation evidence to compare/select predictive models. | **Closest methodological precedent for the validation layer itself**. | PRAISE needs to justify its *systems-specific* contribution via provider information, composed graph conditions, WB reference, concrete costs, feasibility and architecture, not claim active predictor evaluation as a new idea. |
| **“Service composition in dynamic environments: a systematic review” (2022), Journal of Systems and Software** ([DOI](https://doi.org/10.1016/j.jss.2022.111290)) | Taxonomy of dynamic service composition under uncertainty. | Establishes strong depth of QoS/SLA composition prior art. | Broad survey, not an implemented competing system; use to bound claims and backtrack closer composition-prediction studies. |
| **“The computing continuum: From IoT to the cloud” (2024), Internet of Things** ([DOI](https://doi.org/10.1016/j.iot.2024.101272)) | Unified view/reference architectures of endpoint–edge–cloud resource and communication systems. | Contextual reference architecture. | Cannot claim a new overall continuum architecture; our layer would *plug into* a continuum architected elsewhere. |

## 3. Explicit systems-feature comparison (evidence-aware)

Here a ✓ means explicitly supported by the cited paper's central description; ◐ means related or partial; — means **not established in the reviewed source**, not confirmed absence.

| Work | QoS/SLA composition | Multiple predictive or optimization methods | Selection among *methods* | Active finite-budget validation of method × condition | Graph/provider disclosure heterogeneity | Closed-loop continuum deployment |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Pozas García et al. 2023 | ✓ | ✓ | ✓ (composition **optimizer**) | — | ◐ | — |
| Stupar & Huljenic 2023 | ✓ | ✓ | ◐ (method comparisons) | — | ◐ | — |
| Active Inference continuum 2024 | ◐ | ✓ | ◐ (transfer/combination) | — | ◐ | ✓ (control architecture; implementation varies) |
| Bonilla et al. 2026 EdgeGuard | ◐ | ◐ | — | — | ◐ | ✓ (monitoring system) |
| Aalikhani et al. 2026 | ✓ | ◐ | — (selects services) | — | ◐ | ✓ (dynamic service-composition approach) |
| Service Selection under Uncertainty 2025 | ✓ | ✓ (optimization formulations) | — (selects services) | — | ◐ | — |
| Hybrid QoS-aware compositions 2026 | ✓ | ✓ (selection/aggregation tools) | — (selects compositions) | — | ◐ | — |
| Mao et al. 2024 SEL-PFMF | — (individual cloud QoS) | ✓ | ✓ (prediction ensemble) | — | ◐ | — |
| Kossen 2021 / Hara 2024 | — (generic model evaluation) | ✓ | ✓ (predictors) | ✓ (active tests; **different observation semantics**) | — | — |
| **PRAISE current prototype** | ✓ (upstream graph compliance prediction) | ✓ (7 frozen predictors) | ✓ (offline *global* predictor) | ✓ (7×12 no-repeat archive replay) | ◐ (several interface studies; not all connected in B1) | **No** (not demonstrated) |

**Interpretation caveat:** This is a qualitative architecture checklist, not a numerical benchmark or confirmed negative assertion about feature absence. Full methods of high-risk comparators, especially Pozas García, Stupar/Huljenic and active-inference continuum work, should be checked before writing the final paper's comparative claims.

## 4. Where a defensible systems contribution might lie

Candidate positioning:

> We introduce a **budget-aware validation and predictor-selection layer** for composed-service performance estimation in the computing continuum. Instead of assuming a fixed composition-level performance predictor, the layer treats alternative prediction methods as a portfolio, exposes provider-world and composition-graph scenarios as admissible validation conditions, and allocates limited reference-backed evaluations to select a predictor for the target domain. We provide a reproducible offline prototype and evaluate the quality of the final selection against a full historical WB reference.

This paragraph is deliberately more modest than “first autonomic predictor-selection system for the continuum.” Its novelty would need to rest on **system-specific requirements, the integration contract and evaluation**, not a new acquisition score.

**Credible differentiation relative to closest systems:** selection of a *performance prediction method* (not service/resource/composition), conditioned on composed graph structure, partial provider evidence and explicit reference-backed validation budget.

**Distinct from mathematical novelty:** best-arm identification and value-of-information procedures are established. The proposed contribution is their transparent integration into the *service-composition prediction* lifecycle, accompanied by empirically verified tradeoffs.

## 5. The main threats and claims that should be excluded

1. **Closest systems threat:** Pozas García et al. (2023) already select a composition algorithm with a decision tree learned from empirical comparisons. The paper must explicitly acknowledge this as near prior art, not conflate selecting a prediction method with inventing portfolio algorithm selection.
2. **Method-selection threat:** active testing and active model selection already allocate test samples to compare models. Explain precisely what changes when evaluating composition-level service performance, provider disclosure conditions and expensive per-method graph simulations.
3. **Architectural maturity:** the current B1 result is **offline archive replay**, not an integrated live autonomic provisioning system. Do not draw a deployment controller as implemented.
4. **Validation scope:** 3 historical provider worlds × 4 graph patterns; no independently sampled new worlds. Policy episode bootstraps do not estimate cross-world generalization.
5. **Cost scope:** validation budget counts distinct matrix evaluations, **not** measured wall time, trajectory cost or energy.
6. **Comparative strength:** the original B1 heuristic beats selected controls in archive and one-step KG is a strong reference; a full conference paper may demand stronger systems alternatives and cost-aware results.
7. **Input scope:** I1/I2a/I2b/I5 each has a distinct evidence contract, and the 7 predictor variants in B1 are not representative of every interface-method combination.
8. **Outcome mismatch:** lower final predictor selection regret need not imply measured improvement in live service provision, SLA attainment, or carbon/energy performance.

## 6. Workshop and conference readiness criteria

**Workshop path — CONDITIONAL GO for preparation:**
- A clear and accurate *architecture for the offline selector*.
- Explicit provider information ↔ predictor compatibility and access to reference evidence.
- Quantitative frozen matrix and policy results with paired uncertainty.
- Honest distinction between implemented replay and proposed live-system adapter.
- Direct acknowledgment of at least the highest-risk neighbors above.

**Applied full conference path — FURTHER EVIDENCE REQUIRED:**
- New provider-world sampling / external generalization, or comparably compelling independent evidence.
- Credible evaluation of actual computational/runtime/resource costs.
- An implementation story beyond disconnected scripts, or carefully justified scope as a system validation method.
- Comparison with the most relevant systems and model-selection alternatives.
- Reproducibility and threat analysis suitable for journal/conference standards.

**Algorithmic-methodology route:** remains conditional per G1 and the frozen dual-track agenda; these A2 results do not establish algorithmic novelty.

## 7. Immediate joint A1/A2 follow-up decisions

- **Implementation audit:** Which I×M pairings are implemented and evidence-backed? Determine from actual source scripts and manifests; do not rely only on narrative descriptions.
- **System boundary:** choose the primary end user and unit of recommendation. Current evidence supports an offline validation engineer choosing one predictor for a fixed domain; future per-graph/per-SLA routing needs separate evidence.
- **Closest-system deep reads:** Pozas García et al. 2023, Stupar/Huljenic 2023, Active Inference CC 2024, and Hara et al. 2024 (and any predecessor discovered in their cited literature).
- **Worked architecture trace:** show a single feasible graph with provider evidence, three candidate prediction outputs, sampled validation, terminal method recommendation; use actual frozen data when available, clearly mark schematic quantities.
- **Workshop skeleton:** problem → interfaces/predictor portfolio → budgeted validation architecture → evidence → limitations, then confirm submission window/venue.

## 8. A2 verdict

**CONDITIONAL GO for a systems-oriented computing-continuum workshop paper**, subject to accurate architectural scope, an implementation audit and direct acknowledgement of portfolio/model-selection systems in prior literature. This is a plausible, distinguishable *applied systems* contribution, not a guaranteed novel end-to-end autonomy platform. **Full conference strength remains unproven** pending generalization, cost accounting and a stronger connected prototype narrative.

Do not replace the earlier BAI G1 REDIRECT decision: it correctly constrains **new-algorithm claims**, but it is not the systems-paper judgment.

## Bibliographic access notes

Primary DOI/venue links above are supplied to permit verification. Some publisher full texts are restricted; conclusions for those studies are limited to abstract, publisher highlights and available textual summaries. Do not claim exhaustive knowledge of their internal architecture without a full-text read. No new experimental results or synthetic examples were generated in this audit.
