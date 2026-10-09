# Phase-6 I2b-v3 hierarchical variability-weighted energy loss freeze (2026-10-09)

## Decision

Freeze I2b-v3 as the hierarchical variability-weighted version of the already frozen I2b temporal-joint reconstruction objective.

For every public temporal window w=(A,H,Delta), define

    V_(A,H,Delta) = (1/N) sum_j [c_j(A,H+Delta)-c_j(A,H)]^2.

For each fixed SLA region A and lag Delta, normalize only across valid start horizons:

    q_(H|A,Delta) = V_(A,H,Delta) / sum_H' V_(A,H',Delta).

Then

    omega_(A,H,Delta) = (1/5)(1/8) q_(H|A,Delta),

and the reconstruction loss is

    L_hier(theta) = sum_(A,Delta,H) omega_(A,H,Delta) E_hat(P_obs,P_theta),

where E_hat is the already frozen empirical two-dimensional energy V-statistic.

If an entire (A,Delta) block has zero temporal variation energy, q is frozen to equal weight across valid starts in that block.

## What changes relative to I2b-v1 and I2b-v2

I2b-v1 used equal lag means and equal windows within each lag. I2b-v2 normalized temporal variation globally over all 630 windows, which unintentionally changed the relative importance of SLA regions and lags. I2b-v3 preserves exactly 1/5 total mass per SLA region and exactly 1/8 total mass per lag. Only start horizons within each fixed (region,lag) block are reweighted by observed temporal variability.

## Pre-reconstruction audit

The public-only audit passed for all P1-P4 providers. There were no zero-variation blocks. Across the 12 providers, the largest single-window weight was about 0.0213, mean effective window count about 192, and minimum effective window count about 90.2 out of 630. Region and lag mass invariants held to floating-point precision. Deterministic endpoint-shuffle sensitivity remained positive for all providers.

## Frozen reconstruction architecture

The provider parameter domains, 64 Sobol plus 192 TPE search, N=25 search CRN bank, top-24 fresh N=100 rescore, top-3/provider support and 27 equal-weight joint M2 models are unchanged from the matched I1-strong, I2AFS, I2b-v1 and I2b-v2 controls.

## Provenance

The hierarchical weighting design was motivated after inspecting the P4/G_SEQPAR development failures of I2b-v1 and global-weight I2b-v2. Therefore P4/G_SEQPAR cannot serve as confirmatory evidence for I2b-v3. It may be used only as the designated development cell. If I2b-v3 is retained after development, topology-level evidence must be obtained on graph structures not used to define this weighting.

## Firewall

The frozen weights use only each provider's public I2b target pairs. No candidate reconstruction quality, graph prediction, graph white-box value, final white-box value, private I1 ledger, or hidden provider parameter enters the weights.
