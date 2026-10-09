# Phase-6 I2b hierarchical variability-weight audit v1 (2026-10-09)

## Purpose

Audit a corrected variability weighting for the frozen I2b temporal-pair representation.

The previous global variability weighting normalized V_w over all 630 windows of a provider. That changed the relative importance of SLA regions and lags in addition to reweighting start intervals. The present audit isolates the intended change: preserve equal importance across SLA regions and lags, and use observed temporal variability only to redistribute weight across start horizons within each (region, lag) block.

This is a public-provider-information audit only. It performs no provider simulation or reconstruction and reads no graph prediction, graph white-box result, final white-box result, or hidden provider parameter.

## Frozen temporal support

The already frozen I2b temporal sampling is unchanged:

- stride s = 10 s;
- lags D = {20,30,40,50,75,100,150,200} s;
- five SLA regions;
- the same canonical valid start horizons and anonymous same-trajectory public pairs.

## Hierarchical weighting

For window w=(A,H,Delta), define temporal variation energy

    V_(A,H,Delta) = (1/N) sum_j [c_j(A,H+Delta)-c_j(A,H)]^2.

For each fixed SLA region A and lag Delta, normalize only across valid start horizons H:

    q_(H | A,Delta) = V_(A,H,Delta) / sum_H' V_(A,H',Delta).

Then assign

    omega_(A,H,Delta) = (1/5) (1/8) q_(H | A,Delta).

Thus every SLA region retains total mass 1/5 and every lag retains total mass 1/8. Only the distribution of weight over start horizons within each (A,Delta) block is changed.

If a complete (A,Delta) block has zero temporal variation energy, use equal weight across its valid start horizons. This fallback is fixed prospectively and does not use any reconstruction or graph outcome.

## Diagnostics

For every provider report:

- maximum single-window weight;
- top-10, top-25 and top-50 window mass;
- effective number of windows 1/sum omega_w^2 and fraction of 630;
- windows needed to reach 50%, 80% and 90% mass;
- minimum and maximum block-level effective start-horizon count;
- exact region mass and lag mass checks;
- deterioration versus improvement energy shares;
- deterministic endpoint-shuffle sensitivity under equal-lag I2b-v1, global-variability I2b-v2, and hierarchical-variability weighting.

## Interpretation rule

The audit is descriptive. No graph-derived threshold is used. The hierarchical scheme is structurally usable if it preserves exact region and lag masses, remains sensitive to destroyed temporal pairing, and does not collapse onto a tiny number of windows.

## Provenance

The weighting idea is development-informed by the failure pattern observed on P4/G_SEQPAR. Therefore any later P4/G_SEQPAR evaluation is development evidence only. If this method is retained, topology-level confirmation must use graph structures not used to define this weighting.

## Upload convenience

The runner creates one ZIP containing all audit outputs and the manifest.
