# Phase-5 V3b FULL343 final-WB reference bootstrap

**Frozen:** 2026-10-08

This file implements the prospectively registered final-WB reference bootstrap after the deterministic evaluation has already been frozen.

It introduces no new method-selection or scientific tuning. Method predictions, Step-0 queries, provider reconstructions, graph definitions and the operational M0 mask remain fixed.

## Resampling

There are 1000 final-WB trajectory indices. For each of 10,000 bootstrap replicates, draw a bootstrap sample of size 1000 with replacement.

Because the same final-WB seed index is reused across eligible physical cells as CRN, the same resampled trajectory-index multiplicities are applied jointly to all 12 eligible cells in each replicate. This preserves within-trajectory dependence across queries and horizons and cross-cell dependence induced by the shared CRN index.

The implementation uses a NumPy PCG64 generator with seed 2026100201 and uniform multinomial count vectors. A multinomial count vector is exactly the count representation of iid trajectory-index resampling with replacement.

## Quantities bootstrapped

For H=60..240 and primary methods M0, M1, M2 and M3_FULL343, recompute the already frozen continuous metrics:

- MAE
- RMSE
- signed bias
- maximum absolute error
- finite-reference-noise-adjusted RMSE

for every registered summary scope. Report the deterministic estimate together with 2.5th and 97.5th bootstrap percentiles.

M0 keeps its already frozen operational-applicability mask. No missing M0 prediction is imputed.

The registered within-world topology contrast Delta_P = MAE(G_SEQ)-MAE(G_PAR) is also bootstrapped for estimable worlds P1, P3 and P4. Delta_het remains not estimable because P2 was excluded by Step-0.

The deterministic Wilson-resolved decision analysis is not redefined in this stage. The prospective contract did not specify how the WB-certain subset should itself vary under resampling, so no post-outcome convention is introduced.
