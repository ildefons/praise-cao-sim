# Phase-6 I2b-v4 mean-range reconstruction freeze (2026-10-10)

I2b-v4 is **a richer public information interface** than I2b-v3. I2b-v3 exposed
anonymous same-trajectory endpoint pairs only; the within-segment maximum-minus-minimum
cannot be inferred from those pairs. The new public statistic is the aggregate
mean across the existing 100 trajectories of each trajectory's maximum-minus-minimum
compliance sampled on the established 5-second grid within each segment.
No individual trajectory values or cross-window linkages are publicized.

Only the *weights* of the existing bivariate endpoint energy V-statistic change.
Candidate models are **not** matched on their predicted internal ranges, and the
new public aggregate does not enter the score as a separate target loss.
This isolates the weighting effect conditional on a new public aggregate.

For each region A, lag Delta, and start H, let
V(A,H,Delta) = N^{-1} sum_j (max_{t in [H,H+Delta]} c_j(A,t)
                             - min_{t in [H,H+Delta]} c_j(A,t)).
Weights are omega = (1/5)(1/8) V / sum_{H'} V within each (A,Delta) block.
Zero-total blocks use prospectively specified equal-start weighting.
The five SLA regions and eight lags retain equal outer mass.

The existing 64 Sobol + 192 TPE search and fresh top-24 rescore (N=100), seeds,
parameter domains, Top-3/provider and equal-weight 27 joint models are unchanged.

The public mean range was materialized in the P4-only results/35 feasibility audit.
Reconstruction reads only public endpoint pairs, public mean-range weights and
public provider metadata/parameter domains, not any Phase-5 private provider ledger.

P4/G_SEQPAR informed v4 after observing previous development performance.
All P4/G_SEQPAR outcomes remain development evidence, never confirmation.
The PPG mechanism/data/code firewall continues to apply.
