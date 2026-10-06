# Phase-5 provider reconstruction V3b selection freeze

**Freeze date:** 2026-10-06

V3b changes only how the already-generated V3 provider candidates are selected for M1 and M2. It does not regenerate candidates and it does not run any provider or graph simulation.

The change was motivated before any graph prediction or final graph white-box evaluation. It is not claimed prospective relative to the observed V3 local reconstruction results.

## Frozen rule

Each provider has seven independently generated V3 candidates. All seven were already evaluated on the same fresh N=100 local rescore bank.

Rank the seven candidates by ascending common-N100 reconstruction RMSE to the public I1 behavior. Use candidate ID only as a deterministic tie break.

- M1 uses rank 1.
- M2 uses ranks 1, 2, and 3 with equal provider weights, producing 3^3 = 27 joint models.
- M3 is unchanged: all seven candidates retain their already-frozen Jeffreys-KL Gibbs weights. The full support remains 7^3 = 343 and the nested Top1, Top3, and Top14 joint readouts remain unchanged.
- M0 is unchanged.

The independent N=100 replay bank remains diagnostic only and cannot affect selection. Behavioral-centroid distance and parameter diversity also remain diagnostics only.

## Interpretation

This yields a nested comparison:

point estimate (M1) -> small equal-weight set of the best reconstructions (M2) -> full evidence-weighted reconstruction distribution (M3).

The design therefore measures the effect of uncertainty representation without deliberately inserting poorer or maximally separated reconstructions into M2. If the best reconstructions are similar, that is evidence of effective local identifiability. If they are behaviorally similar but parametrically different, that is evidence of inverse-problem ambiguity.
