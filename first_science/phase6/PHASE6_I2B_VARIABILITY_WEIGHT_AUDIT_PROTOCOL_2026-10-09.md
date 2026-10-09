# Phase-6 I2b variability-weight audit v1 (2026-10-09)

## Purpose

Test a data-derived alternative to the equal temporal-window weighting used by I2b-v1.

The hypothesis is that temporal windows should contribute in proportion to how much temporal variability they actually contain, rather than all windows receiving equal importance.

This is a provider-only public-information audit. It performs no provider simulation or reconstruction and reads no graph prediction, graph white-box result, final white-box result, or hidden provider parameter.

## Frozen temporal support

The audit does not alter the already frozen I2b temporal sampling:

- stride s = 10 s;
- lags D = {20,30,40,50,75,100,150,200} s;
- canonical valid start horizons from the frozen I2b-v1 representation.

Only the aggregation weight is under study.

## Window variability measure

For public temporal window w=(A,H,Delta) with N=100 anonymous same-trajectory pairs, define

    delta_j,w = c_j(H+Delta) - c_j(H)

and temporal variation energy

    V_w = (1/N) sum_j delta_j,w^2.

This is the second moment of temporal displacement, not Var(delta). A window in which all trajectories undergo the same large change therefore still has large V_w.

Define provider-specific normalized weights

    omega_w = V_w / sum_w' V_w'.

The normalization is over all 630 frozen temporal windows of one provider. No graph or reconstruction outcome enters these weights.

## Diagnostics

For every provider, report:

- maximum single-window weight;
- top-10, top-25 and top-50 window mass;
- effective number of windows 1/sum omega_w^2 and its fraction of 630;
- number of windows required to accumulate 50%, 80% and 90% of total weight;
- total weight by lag;
- total weight by SLA region;
- decomposition of variation energy into deterioration and improvement components.

Also reuse the deterministic endpoint-shuffle control from the I2b-v1 energy benchmark. Report the original equal-lag energy response and the proposed variability-weighted response. This is only a sensitivity sanity check and is not used to tune the weights.

## Decision principle

The weighting is considered structurally usable only if it does not collapse onto a very small number of windows and if temporal-pair sensitivity remains positive across providers.

No numerical concentration threshold is frozen in advance. The audit exposes the concentration profile for scientific inspection before any I2b-v2 reconstruction is defined.

## Upload convenience

The runner creates one ZIP containing all audit outputs and the manifest.
