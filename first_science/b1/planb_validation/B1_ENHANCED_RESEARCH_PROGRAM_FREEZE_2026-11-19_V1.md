# PRAISE Plan B — Enhanced applied-validation research program (freeze v1)

**Frozen on:** 19 November 2026

**Status:** FROZEN RESEARCH PROGRAM / DESIGN INTENT — **NOT EXECUTED**, **NOT A PREREGISTERED CONFIRMATORY STUDY**, **NOT AUTHORIZATION FOR NEW SIMULATIONS**

**Primary goal:** Strengthen the applied-methodology contribution of *Budget-Aware Method Validation in the Computing Continuum*, with particular attention to computing-continuum structure, robustness of allocation decisions, and practical evaluation costs.

**Relationship to existing plans:** Addendum to [the 6 November research roadmap](B1_RESEARCH_AGENDA_FREEZE_2026-11-06_V1.md) and [the dual-track systems agenda](B1_DUAL_TRACK_RESEARCH_AGENDA_2026-11-06_V1.md). Neither document nor any prior protocol, policy, predictor, reference or result is superseded.

## 1. Scientific purpose, in plain language

Our current experiments ask which predictor to recommend after inspecting only part of a finite set of possible validation results. They show that **decision-focused allocation of those observations can reduce terminal simple regret** on the studied computing-continuum domain. They do not yet isolate whether the *provider-world × composition-graph structure* itself makes validation better, whether the acquisition advantage survives changes in the intended operating-condition distribution, or whether fewer revealed outcomes correspond to fewer real computational resources.

The enhanced program therefore freezes three complementary investigations, in priority order:

1. **Structural information sharing:** Does the crossed-factor model improve selection, relative to models that share no information or allow interactions?
2. **Operating-domain robustness:** Do the policies remain competitive when the target-domain condition weights change, and policy acquisitions are rerun for that target?
3. **Computational-cost validity:** Are the acquisition benefits preserved when evaluation costs, including reusable and shared costs, are accounted for using defensible measurements?

These are scientific tests, not commitments that the current additive surrogate, Knowledge Gradient (KG), or adaptive condition selection must win. Null or adverse results are valuable and must remain reportable.

## 2. Frozen scientific baseline and evidence boundaries

**Candidate methods:** Seven previously frozen public-I1 composed-service prediction variants.

**Conditions:** Three eligible provider worlds P1/P3/P4 crossed with four composition graphs G_PAR, G_PARSEQ, G_SEQ and G_SEQPAR; 12 conditions and **84 distinct method–condition observations**.

**Existing scoring:** One condition-level MAE aggregates 555 related query–horizon points. The default target is the **equal-weight average of the twelve MAEs**, with terminal simple regret relative to the best method on the complete fixed matrix.

**Action contract:** A policy reveals one previously unseen method–condition MAE per action, with no repeat within an episode, no access to private world parameters or unrevealed reference cells, and the same seven-method common-condition initialization charged to the budget.

**Two fixed archives:**

- **Historical development archive:** The original composite seven-method accuracy evidence.
- **Fresh-reference archive (internal identifier `B0001`):** Frozen predictions scored against an independently seeded and audited white-box reference on the **same provider worlds and graphs**. It is a fresh reference, **not a new set of provider worlds**.

**Existing policy evidence:** Nine frozen acquisition policies, kept distinct: Random, Balanced, Informed, original joint-action Top2, original joint-action KG, and matched two-stage KG/Top2 adaptive/uniform condition selectors. Budgets are **10, 15, 20, 25, 30, 35, 40, 45, 55, 65, 70, 75, 80**. The extended replay uses 12 starting conditions × 20 repetitions = **240 terminal episodes per policy/budget/archive**, with 2,000 stratified episode-bootstrap draws, and two figures with the common regret-axis range [0, 0.025]. See [the thirteen-budget extension](results/b1_nine_policy_13_budget_extension_v1/README.md).

**Observed limitations that motivate this program:**

- The same additive per-method Gaussian surrogate is used by all existing policies; their relative performance **does not isolate** the benefit of sharing provider/graph effects.
- The leading fresh-reference methods M1 and M3 are nearly tied on the equally weighted domain. In P1/G_PAR, M3 is worse by 0.296267 MAE; over the other eleven conditions it is better by approximately 0.026152 MAE on average. The implied M1/M3 ranking switches when the P1/G_PAR weight is roughly **8.11%**, with the other eleven sharing the residual weight equally, versus the current **8.33%**. This threshold is a **post-hoc diagnostic**, not a new result to be confirmed on the same data.
- White-box trajectory uncertainty, notably the unresolved M1/M3 reference ranking, is not fully propagated through sequential acquisition. Episode-bootstrap intervals are conditional on each frozen matrix.
- One revealed MAE is currently one budget unit; actual runtime, CPU, energy and reusable reference-generation costs are **not** measured by the replay budget.

The original nine-policy results, source hashes, figures, reference ledgers and reference audits remain **immutable baselines**. No new model or weighting is to be substituted silently into those historical curves.

## 3. Experiment E1 — Is structured sharing actually useful?

### Question and proposed controlled comparison

For a fixed predictor $a$ and condition $c=(w,g)$, compare three **performance surrogates** used by an otherwise fixed acquisition/terminal-decision procedure:

| Arm | Model | What evidence transfers? |
| --- | --- | --- |
| **A — Independent cells** | Separate regularized latent loss $f_{a,c}$ for each of 12 cells | Observing one cell does not directly update another cell. |
| **B — Additive sharing (current)** | $f_a(w,g)=\alpha_a+u_{a,w}+v_{a,g}$ | Observations inform other cells through shared world and graph effects. |
| **C — Interaction-aware sharing** | $f_a(w,g)=\alpha_a+u_{a,w}+v_{a,g}+h_{a,w,g}$ with a regularized interaction | Allows transfer through shared factors while representing exceptional world–graph combinations. |

Use the **same candidate set, condition domain, acquisition budgets, initial observations, no-repeat rule, terminal objective, policy seed/starting-condition design and loss matrices**. The primary minimal comparison is **original-style joint-action KG under A/B/C**; retain Random and/or Balanced as coverage controls under consistently defined terminal estimators. Any extension to Top2 or all nine policies requires a separately frozen, bounded execution plan. Do not present a new-model replay as an unchanged run of the original nine policies.

### Essential fairness and validity conditions

1. **Match prior predictive scales.** The models have different parameterizations and capacities. Fix or systematically vary mean, marginal prior variance, residual/working noise and reasonable interaction shrinkage before outcome comparisons; do not let a favorable prior accidentally masquerade as the advantage of a factorization.
2. **Specify the posterior and acquisition equations for each model.** In particular, compute the domain-average posterior mean and prospective variance reduction from that model's covariance; do not reuse the additive formula mechanically when its assumptions differ.
3. **Preserve the finite-catalogue setting.** One MAE per method–condition entry is available within an episode; do not assume repeated simulator observations merely because the working likelihood has a residual variance.
4. **Use the existing two archives only as retrospective exploratory evidence.** Both matrices and their influential cells are already known to the investigators. Priors/model choices cannot be presented as prospectively selected independently of those observations.
5. **Diagnose misspecification and stability.** In addition to policy regret, examine leave-one-condition prediction errors, the P1/G_PAR influence, residual interactions and sensitivity to reasonable prior scales. Posterior credible intervals must not be called empirically calibrated without an appropriate calibration test.

**Primary endpoint:** Mean terminal simple regret at each budget and the equal-weight thirteen-budget descriptive aggregate, with paired policy contrasts and existing episode-bootstrap conventions. **Secondary:** reference-best selection frequency, regret tails, cross-condition predictive accuracy and uncertainty diagnostics; report all thirteen budgets, including low-budget risks and high-budget saturation.

**Interpretation gate:** If B beats A, report evidence for useful sharing **on these fixed matrices**. If C beats B, report evidence that interactions matter and the current additive approximation may be too restrictive. If A matches or exceeds B/C, weaken the claim that the crossed-factor surrogate itself adds value, while retaining any independently supported decision-focused allocation result.

## 4. Experiment E2 — Robustness to the intended operating domain

### Target and comparisons

For a declared target weight vector $p=(p_c)_{c\in\mathcal C}$, with $p_c\geq0$ and $\sum_c p_c=1$, define

$$
\mu_a(p)=\sum_{c\in\mathcal C}p_cY_{a,c},\qquad
r_B(p)=\mu_{\widehat a_B(p)}(p)-\min_a\mu_a(p).
$$

The **uniform twelve-condition target** remains the historical primary baseline. For sensitivity work, freeze before execution a small, interpretable family of alternatives, including:

1. **Single influential-cell tilt:** Vary the P1/G_PAR weight around its observed near-8.11% M1/M3 boundary, redistributing the remainder equally across the other eleven cells. This is a transparent targeted diagnostic, not independent confirmation.
2. **Provider-world mixtures:** Change the relative prevalence of P1, P3 and P4 while retaining the four graph types within each world under an explicitly stated rule.
3. **Composition-graph mixtures:** Change the relative prevalence of PAR, PARSEQ, SEQ and SEQPAR while retaining a stated world weighting.
4. **Optional realistic scenarios:** Include nonuniform world–graph mixtures only if grounded in a documented external usage case; do not select weights to favor a preferred policy.

### Required methodological distinction

**Rerun each acquisition path for each new target.** For target-dependent selectors, replace the posterior mean of the uniform domain with the appropriately weighted target (for a linear surrogate, $v(p)=\sum_c p_cx_c$), recompute KG or other objective-dependent acquisition scores, and make the corresponding terminal recommendation. Random/Balanced may retain their selection mechanics but must apply the same weighted terminal decision target. Keep initialization, available observations, episodes, seeds and budgets controlled. Any fixed-recommendation rescoring is a separate descriptive diagnostic and **does not substitute** for the new target-aware policy replay.

**Primary endpoint:** Policy-versus-Balanced terminal-regret contrast and full regret curves under each frozen weight scenario. **Secondary:** winning-method changes, KG-versus-Top2 comparisons, adaptive-versus-uniform behavior, and sensitivity near the known M1/M3 ranking boundary.

**Interpretation gate:** A policy that remains effective across several plausible targets provides evidence of **target-definition robustness within the known worlds**. A reversal identifies a dependence on the application-domain weighting; it does not prove that a different method would be superior in newly sampled physical worlds. Avoid treating numerous reweightings as independent environmental replications.

## 5. Experiment E3 — Are there real computational savings?

### Stage C1: Cost provenance and feasibility first

Inventory **measured or faithfully reconstructable** execution costs, separating:

| Cost component | Likely sharing / accounting question |
| --- | --- |
| Public-I1 provider evidence construction | Once per world or provider description? Already available or acquired on demand? |
| Candidate provider-model reconstruction | Once per method/world, or repeated across graph compositions? |
| Graph-level prediction | Once per method × world × graph, possibly across shared query sets? |
| White-box reference generation | Once per world × graph, shared across predictors scored against it? |
| Error scoring and storage | Incremental per method × condition; what can be reused? |

Collect recorded wall-clock time, CPU time, hardware configuration and, if reliable, energy measurements. Distinguish **offline archive-replay cost** (where all entries already exist) from a **prospective validation workflow** that must first produce reference evidence. A reference created once may have a large fixed cost and negligible marginal cost for a second predictor on the same condition; these cases must not be conflated. Prior timing audits warn that some predictor stages are bundled rather than separately timed; do not invent allocations for unavailable component-level measurements.

### Stage C2: Cost-aware replay only after a credible cost contract

If C1 yields trustworthy costs, specify a path-dependent incremental cost $\Delta C(a,c\mid\mathcal H_t)$ that reflects already constructed shared artifacts, set budgets in real resource units, and compare policies under the **same cumulative-cost stopping rule**. A heuristic such as KG benefit divided by incremental cost may be tested, but it is not globally optimal by construction; document its edge cases (zero marginal cost, fixed setup costs, incomplete actions, and parallelism).

**Primary endpoint:** Terminal simple regret at matched **realized measured or credibly reconstructed total resource budgets**. **Secondary:** total validation outcomes, time/CPU/energy by stage, shared-cost savings and the gap between outcome-count and resource-budget rankings.

**Interpretation gate:** If trustworthy component costs cannot be extracted, stop at a descriptive cost architecture and feasibility audit. Clearly label any illustrative cost scenario as a **synthetic sensitivity analysis**; do not claim measured computational savings or an executed online orchestration service.

## 6. Sequencing, gates and decisions

| Gate | Required output | Decision |
| --- | --- | --- |
| **F0 — Preserve current evidence** | Verify immutable historical/fresh-reference matrices, original nine-policy summaries, thirteen-budget figures, source hashes and provenance. | Halt on unexpected mismatch; never repair by changing frozen source values. |
| **F1 — Specify E1** | Written A/B/C priors, likelihoods, KG posterior/acquisition equations, fairness checks, exact episode design and test assertions. | GO only if comparisons isolate representation rather than accidental prior differences. |
| **F2 — Run and audit E1** | Complete thirteen-budget curves, matched statistics, source/output hashes, failure cases and truthful findings. | Keep B if supported, revise if interactions matter, or reposition if sharing has no measured benefit. |
| **F3 — Specify and test E2** | Frozen scenario/weight table, target-aware acquisition updates, policy histories and contrasts. | Assess robustness across target definitions; do not label these as independent worlds. |
| **F4 — Audit cost sources** | Cost component inventory, measurable units, caches/dependencies, uncertainty and feasibility decision. | GO/STOP on cost-aware replay; do not invent unavailable times. |
| **F5 — Reassess publication claims** | Evidence-to-claim map, limitations, implications for current manuscript and possible future independent-world study. | Choose workshop/full conference/journal route based on actual results, not a guaranteed improvement. |

**Priorities:** E1 first, E2 second, E3 cost audit third. Safe read-only design and cost-source inspection may proceed in parallel. No large simulation or new provider-world generation is authorized by this freeze. Reuse frozen data and scripts where appropriate, without changing the previous reference/policy runs.

**Publication timing:** CCGrid 2027 Track 5 is a possible stretch target, but its near-term abstract/manuscript deadlines are **not** a scientific justification for skipping F1/F3, claiming measured costs, or mislabeling retrospective sensitivity studies as preregistered confirmation. This document is preserved for later return whether or not that submission proceeds.

## 7. Reporting discipline and change control

- **One evidence class at a time:** existing replay episodes are conditional on a fixed $7\times12$ archive; fresh white-box trajectory seeds quantify reference uncertainty; genuinely new provider worlds would be separate environment replicates. Do not pool these units.
- **Do not change predictors or reference outcomes** to favor a surrogate or an acquisition policy. Continue to distinguish original joint-action KG/Top2 from the matched two-stage policies.
- **No post-hoc victory claims:** all new retrospective model/weight/cost comparisons are exploratory on already inspected matrices. New independent worlds, if later approved, need a prospective protocol before data generation.
- **Full curves and uncertainty:** report all thirteen budgets, with identical plot y-ranges within comparisons, explicit weighting, paired episode-level uncertainty and multiple-comparison caveats. Preserve unfavorable cells and runs.
- **Reproducible outputs:** each future gate should produce a versioned design/runbook, tested script(s), hashes/manifests, unchanged baseline identifiers, CSV tables, figures and a short decision note (`GO`, `REVISE` or `STOP`). No silent overwrites or renamed old experiments.
- **Change log:** this v1 is a frozen *research program*, not a fully executable protocol. Before actual execution, freeze exact model priors, interaction shrinkage, scenario weights, seeds, numerical tolerances, resource contracts, policy shortlist and planned contrasts as a dated implementation protocol. Future changes to this program require a new version/addendum, retaining this file intact.

## 8. How to resume the program later

1. Open **this file first** and the existing [6 November roadmap](B1_RESEARCH_AGENDA_FREEZE_2026-11-06_V1.md).
2. Confirm whether **F0** is current and whether a newer approved E1/E2/E3 execution protocol exists.
3. Inspect (do not overwrite) the [nine-policy thirteen-budget evidence](results/b1_nine_policy_13_budget_extension_v1/README.md), [historical/fresh-reference worked evidence](paper_systems/README.md), [raw reference uncertainty audit](B0001_P1_GPAR_RAW_AUDIT_REFERENCE_UNCERTAINTY_RUNBOOK_V1.md), and [original policy design](B1_SEQUENTIAL_VALIDATION_DESIGN_FREEZE_V1.md).
4. **Default next research step:** draft the executable **E1 specification** (A/B/C model priors and controlled KG comparison), review its fairness and falsification conditions, then authorize its retrospective run separately.
5. Keep the current manuscript's established RQ1 finding independent of the unresolved RQ2/RQ3 comparisons until further experiments justify stronger claims.

**Freeze statement:** The questions, priorities, integrity boundaries, control requirements and decision gates above are agreed planning commitments. This document records **no new experiment, no improved result, no new world generalization, no cost savings and no new algorithmic theorem**.
