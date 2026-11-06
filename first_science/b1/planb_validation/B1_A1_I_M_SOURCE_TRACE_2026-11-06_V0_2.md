# A1 source trace — completed B1 provider-information ↔ prediction-method mapping (v0.2)

**Date:** 6 November 2026  
**Status:** SOURCE-TRACED FOR ALL SEVEN B1 PREDICTOR VARIANTS; IMPLEMENTATION CONTRACTS CHECKED. This closes the **B1-specific I×M question**, not the whole PRAISE interface compatibility matrix.  
**Supersedes for B1:** the narrower first-pass [evidence inventory](B1_A1_IMPLEMENTATION_EVIDENCE_AUDIT_2026-11-06_V0_1.md).  
**No new simulation:** this is source tracing only.

## 1. Key conclusion

**All seven B1 predictors were constructed with public-I1 provider evidence. No B1 candidate uses an I2a or I2b provider disclosure.** The I5 white-box evidence is used as a reference **after** the predictions are frozen; it is not an input to model reconstruction, scoring, weight selection or blind graph prediction.

The seven names correspond to a set of *concrete method variants* under **I1**, not a factorial combination of seven I×M pairs. In particular, the labels M1, M2 and M3 designate different algorithms for reconstructing/propagating public-I1 provider information; the Top14/Top1 families change model selection, weighting and/or allocated graph trajectory support, not the provider-information interface.

**Evidence strength:** the relevant repository runners explicitly declare and implement a public-I1 boundary, and the B1 matrix aggregation checks hashes and method IDs from the resulting archived evaluations. This is a source-contract and provenance conclusion; it does **not** constitute an independent runtime instrumentation audit proving that every line executed exactly as intended.

## 2. Exact seven-method trace

| B1 method ID | Information interface | Provider reconstruction / model selection | Graph-composition estimator | Evidence source and decisive implementation |
|---|---|---|---|---|
| **M1** | **I1** public rho-conditioned cards | Single selected/rank-1 provider model per provider | One joint graph surrogate for each eligible cell | [V3 provider reconstruction](../../phase5/run_phase5_provider_reconstruction_v3.py), [full-support graph prediction](../../phase5/run_phase5_graph_prediction_v3b_fullsupport.py) |
| **M2** | **I1** public cards | First three selected provider models per provider | 3×3×3 = 27 joint graph members, equally weighted | [V3 provider reconstruction](../../phase5/run_phase5_provider_reconstruction_v3.py), [full-support graph prediction](../../phase5/run_phase5_graph_prediction_v3b_fullsupport.py) |
| **M3_FULL343** | **I1** public cards | Seven provider candidates per provider; behavioral/KL-based weights | 7×7×7 = 343 weighted joint members, frozen full-support allocation | [V3 provider reconstruction](../../phase5/run_phase5_provider_reconstruction_v3.py), [full-support graph prediction](../../phase5/run_phase5_graph_prediction_v3b_fullsupport.py) |
| **ORIGINAL_TOP14_B1400** | **I1** public cards | Original-pilot-style 48-candidate I1 per-provider reconstruction, I1-based lambda CV and joint support rule; stored original-style highest-weight 14 | Fixed B=1400 graph trajectories with Top14 joint support | [original-style policy transfer](../retrospective_m3/run_pilot_m3_policy_transfer_v1.py), [public-only core](../retrospective_m3/_pilot_m3_policy_transfer_core_v1.py), [B1 archive builder](b1_budget_comparison_v1.py) |
| **ORIGINAL_TOP1_B1400** | **I1** public cards | Same original-style I1 candidate/weight family, highest-weight joint model | B=1400 graph trajectories for Top1 | Same original-style source and archive builder |
| **FIXED_CV_TOP14** | **I1** public cards | Reuses the original-style frozen public-I1 candidate banks and world-specific lambda CV; fixes support size to 14 and renormalizes weights | B=1400 graph trajectories with Top14 | [fixed-CV runner](../retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py), [original-style source](../retrospective_m3/run_pilot_m3_policy_transfer_v1.py) |
| **FIXED_CV_TOP1** | **I1** public cards | Same frozen public-I1 candidates/CV; fixes Top1 model | Independent B=1400 graph-trajectory propagation | Same fixed-CV runner |

**Important subtlety:** the original-style and fixed-CV methods are different reconstruction/selection/allocation variants within the I1/M3 family. The fixed-CV runner explicitly **reuses frozen source candidates and selected lambda** rather than introducing an I2b information interface, and explicitly says it is not a successful implementation of the full adaptive 99.9%-mass policy. Do not call it that policy in a publication.

## 3. Source → evidence lineage and protected boundaries

The trace in the repository follows:

1. **Build public I1 provider cards:** [Phase-5 I1 v2](../../phase5/run_phase5_i1_v2.py) creates region and sigma evidence with disjoint provider-local N=100 banks, materializes public cards and deletes transient private native traces. The same public cards are reused across the four graph structures.
2. **Build public-I1 M1/M2/M3 candidates:** [Phase-5 V3 provider reconstructor](../../phase5/run_phase5_provider_reconstruction_v3.py) loads public cards via \`_load_public_card\`, evaluates fresh candidate banks on public I1, ranks the seven models, selects M1 and M2 subsets, and weights the M3 family; its module contract explicitly forbids Step-0 WB values, graph predictions, final graph WB or private generating parameters.
3. **Propagate on graph, still blind:** [Phase-5 FULL343 graph prediction](../../phase5/run_phase5_graph_prediction_v3b_fullsupport.py) states it consumes frozen public I1 cards, frozen Step-0 eligibility/query definitions and frozen V3b reconstructions/weights, and does not read private I1 traces or final WB evidence. It emits M1, M2 and M3_FULL343 prediction artifacts.
4. **Alternative original-style I1/M3 branch:** [original-style transfer runner](../retrospective_m3/run_pilot_m3_policy_transfer_v1.py) constructs provider candidates and computes its 5-fold CV weights on public I1; [candidate/graph engine](../retrospective_m3/_pilot_m3_policy_transfer_core_v1.py) loads the same public-I1 card contract; predictor outputs precede retrospective WB comparison.
5. **Fixed-CV Top14/Top1 branch:** [fixed-CV runner](../retrospective_m3/run_fixed_cv_top1_top14_battery_v1.py) reuses the original-style I1 candidate banks/CV and simulates restricted fixed supports, with a prediction freeze before any WB reference is opened.
6. **Reference comparison (held separate):** [Phase-5 evaluation](../../phase5/run_phase5_evaluation_v3b_fullsupport.py) explicitly describes itself as the first code joining previously frozen blind predictions to the untouched N=1000 final WB reference. Original-style and fixed-CV evaluation stages follow their respective prediction freezes.
7. **Retrospective B1 matrix:** [frozen archive builder](b1_budget_comparison_v1.py) reads the three evaluation groups and uses the distinct method IDs, 12-condition completeness, N=555 per physical cell, SHA-256 source checks and published-mean guards; the decision policies then operate only on revealed aggregate MAEs.

This is **I1 → selected candidate method/variant → blinded composition prediction → later independent WB evaluation → archived per-cell error → offline finite-budget method selection**.

## 4. What the I×M matrix really looks like

**B1 demonstrated comparison:**

| Information interface | M0 analytic | M1 | M2 | M3 and variants |
|---|---|---|---|---|
| **I1** | Implemented upstream, **not in B1 seven** | **B1** | **B1** | **B1:** FULL343; original Top14/Top1; fixed-CV Top14/Top1 |
| **I2a** | Not assessed by B1 | Not assessed by B1 | Evaluated separately in Phase 6, **not B1** | Not assessed by B1 |
| **I2b** | Not assessed by B1 | Not assessed by B1 | Evaluated separately in Phase 6, **not B1** | Not assessed by B1 |
| **I5 / WB** | Evaluation reference, not a competing ordinary input | Evaluation reference | Evaluation reference | Evaluation reference |

Cells marked “not assessed by B1” are **not assertions that the codebase lacks such combinations**. They are outside the current seven-predictor archive and would require separate source checks before being presented as available.

## 5. Paper-safe statement

> In our evaluated prototype, seven prediction-method variants were instantiated using the same public-I1 provider-disclosure contract. They range from a single reconstructed provider model to ensemble and weighted joint-support composition predictors. A blinded graph-prediction stage produces candidate compliance estimates, which are subsequently compared with independent white-box simulation references. Our budgeted validation layer then chooses which archived predictor–world–graph accuracy observations to reveal and recommends one method for the defined domain. I2a and I2b are separate upstream interface studies, not inputs to the evaluated seven-method selection experiment.

## 6. Architecture implications and closure

- Draw a **single solid I1 interface** entering the seven-method portfolio. Do **not** draw solid I2a/I2b lines into the existing B1 selector or imply B1 chose between disclosure levels.
- Show M0 as upstream context / optional analytic method, outside B1's seven candidates.
- Show I5/WB on the **evaluation/reference side**, separated from public evidence and only joined **after prediction freeze**.
- Group method variants under M1, M2 and M3 (FULL343, original-style Top14/Top1, fixed-CV Top14/Top1), not as seven different interface types.
- Present the actual B1 selection layer as **offline replay of historical cell-level MAEs**, not live graph recomputation.
- Label the final selection as **one predictor across the 12-cell domain**; per-request online routing is not implemented.

**Verdict:** **A1 B1-specific provider-information trace COMPLETE.** Full upstream I×M coverage across all PRAISE experiments remains outside this task. No blocking source ambiguity remains for a truthful systems-paper description of the seven evaluated B1 predictors.
