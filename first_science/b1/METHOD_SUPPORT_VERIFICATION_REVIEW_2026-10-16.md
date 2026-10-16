# PRAISE B1 Substep 2.3b: Frozen V3b method-support verification review

**Date:** 2026-10-16  
**Input:** user-uploaded `praise_b1_method_support_v0_1.zip`  
**Input SHA-256:** `c1f0a4d35d3308fbe80f2e6e7dbad1bb5fce9d95f8a6ecdd6561111982817395`  
**Audit script:** `first_science/b1/verify_method_support_v0_1.py`  
**Verification type:** read-only reconciliation with existing frozen CSVs, **not** model optimization or graph simulation.

## Result

**132 PASS; 0 FAIL.** The archive contains `method_checks.csv` and `summary.json`, whose aggregate counts agree.

| World | PASS | Scope |
|---|---:|---|
| P1 | 34 | 3 provider candidate sets, M2/M3 supports, M3 graph allocation |
| P2 | 30 | 3 provider candidate sets, M2/M3 supports; no graph allocation (Step0 gate failed) |
| P3 | 34 | As P1 |
| P4 | 34 | As P1 |
| **Total** | **132** | |

### Verified operational definitions

1. Each provider/world V3b quality bank contains seven distinct candidate identifiers.
2. M1 selects the lowest common-N100 I1 rescore-RMSE candidate per provider.
3. M2 retains the top three quality-ranked candidate IDs per provider **including the M1 rank-1 candidate**, with equal per-provider weight 1/3.
4. M3 retains the same seven candidates as V3 and preserves the frozen per-provider Gibbs weights, normalized to one.
5. Each world's M2 joint support contains exactly the 3×3×3 Cartesian combinations at 1/27 each.
6. Each world's M3 joint support contains exactly the 7×7×7 Cartesian combinations, and every joint weight matches the product of the three archived provider weights. The support is ranked by descending product weight; the Top14 archive equals the corresponding prefix.
7. For eligible worlds P1, P3, P4, the M3 FULL343 allocation covers all 343 ranks, assigns at least one graph trajectory per model and a total of **1400**; the independent greedy allocation reconstruction exactly reproduces the saved trajectory counts. The archived seed-start formula also matches the frozen rank/stride convention.

### Scientific interpretation

- The **methods we describe are consistent with the archived selections**. This resolves the narrow v0.1 method-definition verification gate.
- In Phase5 V3b, M1 is nested in M2's *provider-model support*, unlike the historical Phase4 diversity-selected M2, whose contract states that the M1 anchor is excluded.
- M3's Top1 is **not definitionally M1**: it selects by KL-Gibbs product weight, whereas M1 selects provider candidates by I1 rescore RMSE.
- No hard I1 *compatibility/accuracy* threshold was introduced by the V3b model-selection algorithm. It is more accurate to say “public-I1-fitted model candidates.”
- Reproducing a numerical allocation or product-weight table is not evidence that its model family, search strategy, or numerical estimator generalizes or reliably predicts hidden provider behavior.

### Verification boundaries

- No Optuna search was rerun and no YAFS/AICon trajectories were generated or replayed.
- The audit checks retained weights against **their original frozen V3 weight table**, but does not recompute the KL energies and `lambda=30` from the original public-I1 pointwise observations.
- The check validates model-selection identity and support arithmetic, **not** simulator-level SLA accounting or prediction accuracy; prior audits separately verified saved pointwise prediction/reference metrics.
- The registered Phase5 V2 alternative methods, Phase4 pilot support, Phase6 variants and the additional P2 retrospective experiments have separate historical contracts. The 132 passes refer specifically to the archived Phase5 V3b selection/full-support pipeline.

## B1 status

**Substep 2.3b: CLOSED at frozen-source and archived-selection level.** See `METHOD_DEFINITION_SOURCE_AUDIT_2026-10-16.md` for the definitions and editorial disposition.

**Next:** Substep **2.3c**, examining uncertainty mathematics, the precise status of truncation bounds versus truth error, Monte Carlo precision under nested reuse, finite portfolio ambiguity intervals, and the operational meaning of threshold admission decisions. This is a mathematical and source audit; it requires no new scientific simulations.
