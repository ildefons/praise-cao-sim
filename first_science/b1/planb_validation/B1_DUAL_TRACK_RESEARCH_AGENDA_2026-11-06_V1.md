# PRAISE Plan B — Dual-track research agenda: systems first, algorithmic innovation in parallel

**Date:** 6 November 2026  
**Status:** FROZEN STRATEGIC ADDENDUM v1 — supersedes the *priority interpretation* in the earlier roadmap, not its evidence, protocol freezes or seven research directions  
**Primary outcome:** Route A — a computing-continuum **systems/methodology contribution**, with a workshop-quality release as the first external target and a stronger applied conference paper if evidence supports it.  
**Secondary outcome:** Route B — an independently defensible **algorithmic/theoretical innovation**, explored in parallel under strict bounded effort and novelty gates.  
**Execution status:** roadmap only. No new simulations or policy parameters authorized by this document.

## 1. Positioning and contribution claims

The project is **not** primarily a competition to invent a replacement for Knowledge Gradient or best-arm identification. It addresses a computing-continuum systems question:

> How can a provider/service-composition system use limited validation evidence to **choose among heterogeneous compliance/performance-prediction methods**, while accounting for multiple provider worlds, graph compositions, different evidence/disclosure interfaces and the cost of evaluation?

The *candidate contribution* is an end-to-end **system-level decision and validation architecture** connecting (a) provider evidence/disclosure, (b) graph composition and compliance-performance estimation, (c) candidate predictors and their empirical uncertainty, (d) allocation of scarce validation measurements across predictor × world × graph conditions, and (e) a final method-selection recommendation. Our historical implementation and frozen 7×12 matrix establish a reproducible **offline sequential-validation prototype**, not a deployed production autonomic middleware or online SLA guarantee. The paper must say which components are executed, which are replayed, and which are proposed.

**What can already be said:** the original B1 heuristic was evaluated on a shared historical archive; supplementary one-step KG, and controlled two-stage adaptive-versus-uniform condition selection, yield conditional evidence about budgeted method selection. Full numerical scope and conditions remain in the frozen evidence.  
**What cannot yet be claimed:** generalization to new independent provider worlds, lower real elapsed compute cost, end-to-end online deployment, fundamental BAI novelty or calibrated confidence guarantees.

A computing-continuum workshop or an applied conference may legitimately value architecture, systems-level problem integration, reproducible evaluation, and evidence of practical utility, even with established selection algorithms. Venue selection and exact claim strength must nevertheless follow an actual call-for-papers and peer-review standard, not presumed acceptance.

## 2. Track A — PRIMARY: integrated systems contribution

**A1 — Define the system-level research problem and architecture (immediate).**

Deliver a coherent architecture diagram and interface table specifying what each subsystem consumes and emits: provider information I1/I2a/I2b/I5 (distinguishing actually used interfaces from future support), candidate predictor M0/M1/M2/M3 variants (distinguishing admissible seven-method comparison from the full methodology), graph G, admissibility A, target σ_G(A,H;ρ), validation-reference provenance, offline decision policy, predicted regret/quality, and selection output. Define exactly what the selection layer sees when it requests one predictor–condition outcome. Explain how the chosen method would be used by a consumer/orchestrator without claiming a deployment that has not happened.

**A2 — Close the *systems*, not only algorithmic, novelty audit (immediate; parallel with A1).**

Compare against closest computing-continuum **QoS/SLA prediction, performance-model selection, autonomic service composition, orchestration, portfolio selection, and model selection** systems. For each, record whether it (i) compares alternative prediction methods, (ii) allocates validation across heterogeneous worlds/graphs, (iii) handles partial provider disclosure, (iv) optimizes a final system-level predictor choice under a budget, and (v) exposes measurable costs and reproducibility. Avoid claiming no prior system exists until checked. Produce one paragraph of genuine system-level differentiation and one paragraph of limitations.

**A3 — Consolidate present evidence into workshop-ready paper (near term).**

Construct a concise claim–evidence table and systems-focused manuscript. Reuse *only* verified figures, policies and reference labels: original four-policy B1, one-step KG supplement, two-stage adaptive/uniform study. Main comparisons should use paired intervals where relevant. Separate the earlier provider-modeling work (M0–M3) from the new validation-allocation decision. Clarify which costs are atomic evaluation counts; report no computed-time savings as demonstrated. The publication unit should be a **systems workflow + controlled retrospective evidence + reproducible artifacts**, not a fabricated new algorithm.

**A4 — Independent-world validation design and cost gate (before expensive execution).**

Freeze generator strata, Step-0 eligibility, graph coverage, role of newly sampled physical worlds, reference simulation and candidate-method reproduction, attrition policy, sample-size/precision planning and wall/CPU resource accounting. Use earlier PRAISE feasibility/timing audits. Choose a limited *predeclared* shortlist of policies and avoid testing every provisional algorithm on an expensive battery. Decision: GO if computationally feasible and meaningful; otherwise report the workshop scope honestly and defer a full conference claim.

**A5 — Execute and analyze confirmatory systems validation (only after A4 GO).**

Use independent provider worlds as replication units; preserve the prescribed equal-condition selection objective and separate development/confirmatory evidence. Compare selection regret, best-selection frequency and robustness by provider/graph structure; add measured or defensibly costed resource budgets. Avoid treating repeated seeded trajectories or resampled episodes as new worlds. Report failures and attrition.

**A6 — Conference-strength manuscript and packaging (after A3–A5).**

Target a full applied conference paper if A4/A5 and architectural/system-comparator evidence are convincing. Include architecture, frozen policy definitions, uncertainty and reproducibility, real-cost analysis, evaluation scope, threats to validity and closest systems comparisons. A workshop paper may precede this, but conference extension must include substantive new evidence/insight rather than cosmetic expansion.

## 3. Track B — SECONDARY: algorithmic/theoretical innovation

**B1 — Continue the mathematical novelty screen (bounded; in parallel with A1/A2).**

Use the existing G1 audit, and refine the exact fixed-budget, finite, without-replacement predictor–condition selection formalization. Assess the closest contextual/transductive BAI, active model selection, and KG literature. Do **not** claim that factoring `(predictor, condition)` or adapting a standard acquisition to a finite catalogue is itself novel.

**B2 — Identify a consequential failure mode (parallel; cheap synthetic/archive diagnostics).**

Focus initially on additive Gaussian model misspecification (provider×graph interaction, cross-predictor correlated errors, possibly heteroscedasticity) and on calibration of the decision uncertainty. Specify failure cases *before* tuning; distinguish structure mismatch from wrong prior/noise choices. Include simple counterexamples and positive controls. The frozen archive is development evidence only.

**B3 — Design a principled algorithm only after a successful problem gap.**

Promising options include model-robust condition design, regret-directed acquisition under an uncertainty set, or limited-horizon lookahead with no-repeat constraints. All must be compared with strong literature alternatives: joint-action KG, gap-based BayesGap/UGapE where legitimately adapted, and an appropriate structured design. Freeze exact selection equations, terminal estimator, admissibility, tie rules, computational complexity and expected failure modes before performance comparisons. Reject incremental variants with no distinct mechanism or demonstrable effect.

**B4 — Independent algorithmic validation or formal result (conditional).**

Seek a theorem, impossibility/identifiability boundary, or sharp counterexample that is not already known; otherwise require a substantial robust empirical advantage across independent problems, not only historical PRAISE policy tuning. Only then consider a separate algorithmic paper or a named new algorithm incorporated into the systems paper.

**B stop rule:** if no defensible scientific gap survives comparison to closest methods, **archive the theoretical search without delaying Track A**. A negative result is not a failure of the systems research programme.

## 4. Workload, sequencing and checkpoints

**Allocation principle:** protect the majority of research time for Track A. A planning default is **~70% Track A / ~20% Track B / ~10% integration and reproducibility**, to be adjusted only after actual project and compute constraints are assessed. This is a management guideline, **not** a reported measured effort allocation or a commitment of contract hours.

| Stage | Track A (critical path) | Track B (parallel, gated) | Exit artifact |
|---|---|---|---|
| **S0 — Now** | Freeze dual-track scope, reuse frozen 7×12 evidence | Preserve G1 audit and limits | This agenda |
| **S1 — Immediate** | **A1 system architecture + A2 closest-systems novelty** | **B1 formal gap / B2 small misspecification diagnosis** | Systems novelty matrix; architecture/claim–evidence table; bounded algorithmic question |
| **S2 — Workshop-ready** | **A3 write coherent systems paper and package figures/code** | No compulsory new algorithm | Workshop-quality manuscript with accurate retrospective limitations |
| **S3 — Feasibility** | **A4 world+cost protocol and GO/NO-GO** | B3 only if B2 identifies real failure | Frozen independent-world plan and method shortlist |
| **S4 — Stronger evidence** | **A5 independent worlds and resource-cost outcomes** | B4 only if novel and justified | Confirmatory evidence, or documented infeasibility |
| **S5 — Submission decision** | **A6 full conference manuscript** when evidence supports it | Optional standalone algorithmic manuscript | Venue-specific decision and frozen release |

**Avoid coupling traps:** Track A workshop readiness is **not dependent** on solving B3/B4. Conversely, a strong new algorithm can be reported as an optional extension, but its novelty or applicability must not be inferred from success in one archived matrix.

## 5. Decision gates and stopping conditions

**Gate A-W (workshop readiness):** systems problem and architecture understandable without prior PRAISE expertise; a genuinely differentiated systems claim relative to closest architecture literature; experiments reproduce; strengths/limitations accurately described; venue call is aligned. No fresh independent worlds *required by this internal gate*, but retrospective limitations must be unambiguous.

**Gate A-C (full conference readiness):** Gate A-W plus independently sampled physical worlds or equivalently compelling external validation; stronger baselines and uncertainty; credible compute-cost analysis where efficiency is claimed; complete system evidence and failure discussion. If unavailable, prefer a properly scoped workshop result rather than overstating a conference claim.

**Gate B-N (novelty):** explicit preexisting literature limitation + formal target + falsifiable distinction + compelling counterexample or supporting theorem/empirical advantage + fair strong comparators. Failure to meet Gate B-N means do not create a novel-algorithm claim.

**Gate X (shared integrity):** never modify old evidence to improve headline results, merge the original KG with new two-stage KG, treat worlds and replays as same sampling unit, or use unavailable costs as if zero. Commit changes through GitHub in separately versioned files.

## 6. Planned manuscript framing (Route A)

**Working title:** “Budget-Aware Selection of Performance-Prediction Methods for Composed Services in the Computing Continuum” (placeholder; subject to closest-systems audit).

**Core contribution candidates:**
1. A decision-oriented, system-level workflow connecting provider disclosure, composition-level prediction, validation evidence acquisition and method recommendation for service graphs.
2. An explicit, reusable evaluation formulation across predictor × provider-world × composition-graph cells with finite nonrepeatable validation budgets and an equal-cell terminal quality target.
3. Reproducible retrospective evaluation of alternative allocation strategies, with supplementary control of adaptive vs uniform condition selection, honest statistical comparisons and documented failure modes.
4. **Conditional future extension:** independent-world generalization and real compute-cost advantage, only when demonstrated.

**Do not imply:** deployed orchestrator, runtime improvement, SLA guarantees, production-grade API, novel BAI theorem, or measured time savings unless those become real evidence.

## 7. Relation to earlier frozen agenda and next action

The [7-direction research roadmap v1](B1_RESEARCH_AGENDA_FREEZE_2026-11-06_V1.md) remains unchanged: G1 novelty, G2 model robustness, G3 independent-world design, G4 evaluation, G5 publication decision. This addendum **changes scheduling/strategic emphasis**: a system-level novelty screen and workshop-ready architecture/paper are now on the critical path, while algorithmic novelty is a parallel, optional, rigorously gated track. The existing [G1 algorithmic novelty REDIRECT](B1_G1_NOVELTY_GAP_AUDIT_2026-11-06_V1.md) is **not reversed**; its scope is explicitly restricted to algorithmic/BAI originality, not systems-paper viability.

**Immediate next step:** begin **A1/A2 together**: build the end-to-end PRAISE system architecture and a primary-literature matrix of closest computing-continuum systems. In a separate bounded workstream, formulate B2 additive-model robustness diagnostics. Keep the first workshop manuscript viable without B-track success.

## 8. Evidence and governance references

- [Original consolidated scientific report](B1_CONSOLIDATED_SCIENTIFIC_EVIDENCE_V0_1.md)
- [Controlled condition-selection results](B1_CONTROLLED_CONDITION_SELECTION_RESULTS_2026-11-06.md)
- [Prior fixed-budget BAI positioning](B1_FIXED_BUDGET_BAI_LITERATURE_POSITIONING_2026-11-05.md)
- [G1 algorithmic novelty audit](B1_G1_NOVELTY_GAP_AUDIT_2026-11-06_V1.md)
- [World validation scope](B1_INDEPENDENT_WORLD_VALIDATION_SCOPE_V0_1.md)
- [World and compute-cost source audit](B1_INDEPENDENT_WORLD_COST_SOURCE_AUDIT_2026-11-05.md)

**Freeze convention:** future strategic reallocation or new primary claims require a dated v2/addendum; do not overwrite this document or the earlier roadmap.