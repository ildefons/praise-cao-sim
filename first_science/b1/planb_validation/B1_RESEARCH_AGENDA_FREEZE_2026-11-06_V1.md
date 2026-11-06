# PRAISE Plan B — Research agenda and decision gates (frozen v1)

**Date:** 6 November 2026  
**Status:** FROZEN RESEARCH ROADMAP / NOT AN EXPERIMENTAL PROTOCOL OR APPROVAL TO RUN SIMULATIONS  
**Scope:** Fixed-budget sequential validation and best-predictor identification for composed-service performance predictors.  
**Repository branch at adoption:** `praise-identifiability-feasibility`.

## Purpose and scientific starting point

Preserve the agreed research options, their priorities, stopping conditions, and publication choices so that subsequent work can return to the plan without redefining objectives retrospectively.

The baseline is the verified **7 predictors × 12 conditions** historical PRAISE archive (3 Step-0-eligible provider worlds P1/P3/P4 × 4 composition graphs). Each predictor–condition MAE is a single, nonrepeatable, finite-matrix observation. The decision target remains selection of the predictor with the lowest **equally weighted mean MAE across all 12 conditions**, with **terminal simple regret** as the primary performance metric. Existing action-count budgets are `B = {10, 15, 20, 30, 40}`. The original four-policy B1 design, supplementary one-step joint-action KG benchmark, and separately labeled two-stage KG/Top2 adaptive-versus-uniform condition-selection comparison retain their separate identities and frozen evidence.

The 6 November two-stage comparison provides **retrospective, conditional** evidence of an adaptive-condition advantage: across-budget uniform-minus-adaptive regret +0.002121 for two-stage KG (95% within-archive bootstrap [0.001281, 0.002960]) and +0.001980 for two-stage Top2 ([0.001202, 0.002819]). It does **not** establish independent-world generalization, novelty, equal-runtime improvements or a causal component effect for the original joint-action algorithms. [Detailed evidence and figures](B1_CONTROLLED_CONDITION_SELECTION_RESULTS_2026-11-06.md).

## Seven research directions, frozen priority order

| Priority | Direction | Question and expected deliverable | Gate / limitation |
|---|---|---|---|
| **1** | **Literature and theoretical novelty audit** | Formulate the precise finite, structured, nonrepeatable arm–condition identification problem; compare closest established KG, BAI, stratified/structured optimal design and multi-task methods; identify a defensible gap, or record that none exists. | **Before any new algorithm is claimed.** Existing methods must not be renamed as novel. |
| **2** | **Misspecification robustness** | Determine where the current additive independent-per-arm Gaussian surrogate fails, e.g. provider–graph interactions, residual correlations, non-Gaussian outcomes or misleading uncertainty. Use frozen archive diagnostics and controlled alternative models first. | Keep allocation policy, terminal objective and inference changes disentangled; retrospective diagnostic cannot certify broad robustness. |
| **3** | **Independent provider-world generalization** | Test preselected algorithms on newly sampled physical provider worlds, retaining clearly defined graph conditions, Step-0 eligibility and stratified coverage. Estimate world-level uncertainty and failure frequency. | Require prospective world-generator contract, attrition rule, cost feasibility, power/precision plan and policy freeze **before** expensive simulation. New world replicates, not repeated allocation sequences, determine generalization uncertainty. |
| **4** | **Strong established competitors** | Benchmark appropriate versions of BayesGap, UGapE, Top-Two Thompson Sampling, elimination and structured optimal experimental design where their assumptions fit finite nonrepeatable matrix observations. | Verify fair adaptation, same information and budget; exclude inapplicable algorithms with a documented reason. |
| **5** | **Method development** | After a demonstrated gap, consider decision-aware condition choice, model-robust allocation or multi-step Knowledge Gradient; assess improvement in terminal simple regret and/or a defensible theoretical property. | No post-hoc algorithm tuning on the same historical 7×12 archive as if it were confirmatory. Candidate method and comparisons must be frozen prior to independent-world evaluation. |
| **6** | **Compute-cost and operational validation** | Replace equal measurement counts with measured or defensibly estimated time/compute costs per predictor–condition evaluation; compare final decision quality under equal resource budgets. | Separate marginal evaluation cost, shared initialization, fixed setup and parallel makespan; unknown costs remain unknown. |
| **7** | **Structure, transfer and theory** | Exploit provider × graph structure, cross-predictor correlations and graph/provider descriptors where legally available; seek informative theorems, counterexamples, sample-complexity or robustness bounds. | Distinguish any claimed contribution from contextual bandits, linear/structured BAI, multi-task BO and classical experimental design; do not add complex models without an identifiable benefit. |

**These are priority rankings, not a strict chronological waterfall.** In particular, world-generalization design and cost planning can proceed while the literature audit runs, but costly execution waits for design and resources to be justified. Robustness analysis and established-method adaptations may inform the choice of a new method. A theoretically important gap may motivate moving priority 7 earlier, with an explicitly recorded decision.

## Eighth item: publication-route decision (strategic gate, not another experiment)

Maintain two possible, complementary scientific outputs:

**Route A — Empirical validation methodology.** Show that adaptive allocation can reduce *real validation effort or cost* while preserving good selection of service-composition predictors across independently sampled provider worlds. Core evidence: strong conventional baselines, independent worlds, honest cost accounting, robustness and reproducibility. Novel algorithm theory is not necessarily required, but applied contribution must be substantive.

**Route B — Algorithmic/methodological contribution.** Precisely identify an unresolved limitation of established finite-budget structured best-arm selection; propose and justify a genuinely new method, with rigorous closest-method comparisons, a theoretical result or counterexample where feasible, and independent-world evidence. PRAISE is the substantive experimental testbed, not a substitute for algorithmic novelty.

**Decision gate:** Choose the route after the novelty audit and first bounded robustness findings; make venue selection only once the contribution type is established. Do not describe Route A as a new algorithm or Route B as validated on new worlds until evidence exists. Both routes can remain open provisionally.

## Work packages and practical checkpoints

**Checkpoint G0 — Historical evidence preservation (already achieved).** Freeze existing policies, scripts, datasets, reports, bootstrap design and plots; distinguish original joint-action KG/Top2 from later matched two-stage ablations. Current positive findings are within-archive development results only.

**Checkpoint G1 — Scientific gap statement.** Produce a concise comparison against closest primary literature: problem definition, claims already solved, irreducible difference (if any), falsifying counterexample, and `GO / REDIRECT / STOP` decision. This is the **next recommended activity**.

**Checkpoint G2 — Cheap robustness stress tests.** Prestate specific model failures being tested and keep condition-weighted target and terminal regret unchanged. Record whether apparent benefits survive or reverse. A negative finding may be scientifically useful and may change the direction of method development.

**Checkpoint G3 — Confirmatory world and cost protocol.** Before any new simulation: freeze generator, eligibility/attrition, sampling unit, controls, algorithm specifications, complete costs and uncertainty plan; calculate whether the planned battery is feasible.

**Checkpoint G4 — Comparative experiment.** Execute only approved policies on independent worlds, preserving train/development versus confirmatory separation; report both action-count and resource-budget outcomes where reliable.

**Checkpoint G5 — Scientific decision and paper framing.** Revisit Route A vs Route B, novelty, generality and evidence strength. Publish null/limited findings accurately; stop or redirect if the proposed claim is not supported.

## Frozen guardrails

1. **Do not rewrite the historical result.** The original four-policy B1 result, original joint KG benchmark, seven-policy reconstruction and controlled two-stage ablation are distinct experiments. Preserve their raw files, code and hashes.
2. **Do not conflate units of replication.** A randomized replay on the same matrix is not a new physical provider-world sample; 555 within-cell query/horizon errors are correlated.
3. **Do not change the decision target implicitly.** Equal-weight mean MAE over the specified eligible conditions remains the baseline; adaptive condition sampling must not redefine it.
4. **Do not assume repeated action availability.** A predictor–condition evaluation can be selected only once per episode.
5. **Do not assume equal computation costs.** Evaluation-count budgets are a methodological abstraction until measured cost results are established.
6. **Do not claim novelty from a strong curve alone.** Compare closest literature and distinguish theoretical contribution from application, model-choice or engineering adaptation.
7. **No unapproved large new-world or simulator battery.** Research-roadmap freeze is authorization to *plan and audit*, not to execute expensive experiments.
8. **Version future decisions explicitly.** Changes to priorities, acquisition rules, reference populations or claims require a dated v2 or addendum, without rewriting this v1.

## Re-entry instructions for future conversations

Start from this file and the [Plan B README](README.md). Recover the last completed checkpoint, review the frozen evidence and ask which gate is next. **Default next task:** G1, the closest-literature and theoretical novelty audit, then G2 cheap robustness characterization before committing to costly G3/G4 independent-world battery.

## Related evidence

- [Consolidated scientific report](B1_CONSOLIDATED_SCIENTIFIC_EVIDENCE_V0_1.md)
- [Full numeric appendix](B1_CONSOLIDATED_NUMERIC_APPENDIX_V0_1.md)
- [Controlled two-stage condition-selection study](B1_CONTROLLED_CONDITION_SELECTION_RESULTS_2026-11-06.md)
- [Literature compatibility audit](B1_LITERATURE_METHOD_COMPATIBILITY_AUDIT_V0_1.md)
- [Fixed-budget BAI literature positioning](B1_FIXED_BUDGET_BAI_LITERATURE_POSITIONING_2026-11-05.md)
- [Independent-world scope](B1_INDEPENDENT_WORLD_VALIDATION_SCOPE_V0_1.md)
- [Independent-world cost source audit](B1_INDEPENDENT_WORLD_COST_SOURCE_AUDIT_2026-11-05.md)

**Freeze semantics:** This file captures the current *strategic decisions and questions*. It does not claim any unperformed experiment, new independent-world evidence, or mathematically proved novelty.
