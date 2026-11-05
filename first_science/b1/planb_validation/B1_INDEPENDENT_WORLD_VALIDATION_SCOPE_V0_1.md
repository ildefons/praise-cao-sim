# PRAISE B1 — Independent-world validation: feasibility and design scope (v0.1)

**Status:** design scoping only; **NOT FROZEN FOR EXECUTION**, no new simulations authorized.  
**Trigger:** successful B1 WB robustness screen, [result freeze](B1_WB_ROBUSTNESS_RESULT_FREEZE_2026-11-05.md).  
**Hard constraint:** no alterations to the seven frozen predictor variants, `b1_budget_comparison_v1.py` selection policies, Gaussian prior/terminal estimator, original five budgets `{10,15,20,30,40}`, or the prespecified mean-regret primary comparison.

## What constitutes genuinely independent confirmation?

The independent sampling unit is a **newly generated provider-world configuration**, defined by an independent draw of the underlying provider parameters/dynamics (and appropriate independent stochastic seeds) from an **explicitly frozen world-generation distribution**. Fresh WB or predictor trajectory seeds with the same provider configurations **do not** create independent worlds.

The existing B1 controller assumes exactly three world-category columns and four graph columns in the design matrix; an individual *12-cell validation battery* should therefore preserve three explicit provider-world roles analogous to `P1/P3/P4` and four frozen composition graphs, for exactly **84 algorithm×cell outcomes per battery**. The names/roles must be justified as a **prospectively sampled** world population rather than reusing the same three physical P1/P3/P4 instances. If the frozen categories cannot be mapped validly to newly sampled worlds, the new study cannot claim a transfer of this exact policy without changing the model; this is a **design blocker** and should be resolved before execution.

**Independence:** worlds in one battery may share common environmental settings and the four graphs; statistical inference must recognize this hierarchy. Multiple random selection replays of one battery do not provide independent world samples. The top-level validation unit for confirmatory comparisons should be the **independent validation battery** (a fresh triple of eligible worlds), with paired allocation runs inside the battery and cluster/battery-level uncertainty analysis.

## Proposed confirmation question

> On genuinely new provider-world batteries, does the **unchanged** budget-aware Top2 policy reduce expected terminal simple regret compared with the unchanged balanced-coverage baseline, averaged equally over budgets B=10,15,20,30,40?

Compute each new battery's **independent complete-reference algorithm means** over its twelve cells. The best method may change from battery to battery: the validation question is whether the *selection rule* transfers, not whether `M3_FULL343` stays best. Report all four frozen controls, all five budgets, regret and winner-selection rates. Primary estimand: paired mean `Top2−balanced` terminal regret across budget-conditional episodes, then averaged across **independent batteries**. Its uncertainty must be computed over the truly independent batteries (not 555 points, trajectories, 240 replay episodes or graph cells). Report world/battery heterogeneity; do not substitute bootstrap-over-sequences intervals for confidence over new worlds.

## Required pre-execution gates

1. **World generator / eligibility.** Define the probability distribution for each provider role and any constraints, including how the frozen Phase-5 Step-0 eligibility check operates on new draws. Specify outcomes for ineligible draws and failure to obtain 12 eligible cells without outcome-guided cherry picking. Freeze random sampling seeds and generation manifest; prevent leakage of hidden parameters/WB values to acquisition policies.
2. **Archive-independent provenance.** Freeze public I1 cards, candidate generation (including original-style and fixed-CV rules), graph execution/sampling budgets per method, the 15×37 scoring grid and independent WB trajectories. Predictions and seven-method labels must have the same meanings as the development study. Avoid sharing stochastic trajectories with the decision estimator when independence is needed.
3. **Computational feasibility.** Audit real marginal work for **all seven** algorithms, I1 reconstruction/search and WB reference, including cached/reusable setup and provider-world sharing; do not infer method-specific costs from Phase-II's bundled M1/M2/M3 elapsed time. The historical Phase-II 12-cell prediction bundle was about 23.94 hours and WB about 17.57 hours, before all costs of original-style and fixed-CV variants. These are *historical reference figures, not estimates of the fresh seven-method battery*. Calculate an evidence-backed cost per independent 12-cell battery, then determine affordable number of independent batteries.
4. **Statistical sample size.** Prespecify a minimal meaningful regret improvement and battery-level uncertainty strategy. If variance is unknown, perform a separately labeled, independently seeded **sizing pilot** with no policy changes, then freeze the confirmatory sample size **before accessing confirmatory results**. Do not claim a predetermined exact battery count based only on 12 archived cells.
5. **Locked analysis.** Preserve the five budgets, common initial seven evaluations on a starting cell, identical acquisition/terminal estimator, outcome definitions and single primary aggregate contrast. Check algorithm×cell completeness and reference quality before unblinding the comparative scores. Correct only independent implementation errors under logged change control; no posthoc policy tuning.
6. **Feasible stop/go decision.** If full independent seven-method 84-action batteries are too expensive, **do not** silently replace the validation target with a five-method or smaller graph population and call it the same confirmatory test. Either defer, negotiate a *new labeled study with a new estimand*, or publish the limited retrospective claim honestly.

## Proposed staged workflow (not authorized execution)

**V0: cost and world-generation audit** → **V1: freeze independent battery protocol and sample size / separately identified sizing pilot** → **V2: generate and score independent complete 84-cell validation batteries** → **V3: replay frozen B1 policies and report per-battery paired regret, confidence intervals and failures**.

No simulations, commitments or claims of generalization are made here. **Continuation under newly allocated budget remains deferred** until after independent-world validation has been evaluated.
