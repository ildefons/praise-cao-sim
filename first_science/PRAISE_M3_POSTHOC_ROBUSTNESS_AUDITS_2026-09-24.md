# PRAISE/CAO M3 post-hoc robustness audits

**Date:** 24 September 2026  
**Status:** analysis-only follow-up to the closed M3-v4 pilot.

These audits respond to reviewer-facing robustness questions without reopening,
retuning, or repairing M0, M1, M2, or M3.

## Audit R1: finite fresh-WB reference noise

Question: can the observed M2-to-M3 MAE improvement be explained by sampling
noise in the fresh N=200 white-box reference?

Procedure:

1. Reuse the closed fresh-WB ledger, seeds 38000..38199.
2. Resample the 200 white-box trajectories as clusters with replacement.
3. Use the same bootstrap multiplicities for all 15 queries and all horizons.
4. Recompute the white-box sigma surface for every bootstrap replicate.
5. Keep all M1/M2/M3 predictions fixed.
6. Recompute H=60..240 MAE for M1, M2, M3-B1400, and M3-B2000.
7. Primary paired quantities:
   - Delta1400 = MAE(M2)-MAE(M3-B1400)
   - Delta2000 = MAE(M2)-MAE(M3-B2000)
8. Report point estimate, bootstrap mean/median, percentile 95% interval, and
   P(Delta>0), for the whole battery and separately for G0/G1/G2.

Interpretation boundary: this isolates finite-reference sampling noise only. It
is not a joint confidence interval over method Monte Carlo noise, model
uncertainty, or method construction.

No new white-box or graph simulation is run.

## Audit R2: public-I1-only lambda sensitivity

Question: is the frozen lambda=30 operating point a sharp or fragile choice, and
how sensitive is the 99.9% retained support size to lambda?

Procedure:

1. Reuse the frozen blocked-CV table over the predeclared lambda grid.
2. Reuse the already simulated public-I1 candidate energies.
3. For every frozen lambda, report:
   - held-out Bernoulli KL and MSE;
   - provider ESS and maximum weights;
   - joint ESS and maximum joint weight;
   - cumulative mass of top 3 and top 14 joint hypotheses;
   - K_99.9, the minimum number of joint hypotheses retaining 99.9% mass.
4. Do not evaluate alternative lambdas on any graph white-box result.
5. Do not change lambda=30 regardless of this post-hoc audit.

For every lambda>0, multiplying the same candidate energies by a positive
scalar preserves the joint energy ranking. Lambda changes concentration and
K_99.9, not the ranking of joint hypotheses.

## Explicit non-actions

- Do not rerun M3 graph prediction.
- Do not rerun M2.
- Do not generate a larger fresh-WB pilot bank before seeing Audit R1.
- Do not change lambda, candidate support, retained-mass threshold, graph
  allocation, budgets, or query battery.
- Do not use graph-WB MAE to perform lambda sensitivity.
- Preserve the PPG firewall.

After R1/R2 are read, decide whether any additional pilot-only robustness
simulation is scientifically necessary before freezing the multi-graph
generalization protocol.
