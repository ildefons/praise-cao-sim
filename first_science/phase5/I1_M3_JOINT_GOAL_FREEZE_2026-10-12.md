# Frozen scientific goal: joint graph admissibility and survival reconstruction

**Status:** GOAL_FROZEN
**Date:** 2026-10-12
**Scope:** Next I1-M3 consolidation and testing track. This is a scientific objective freeze, **not** an implementation, metric, algorithm, or benchmark-protocol freeze. Existing Phase-4 and Phase-5 contracts and results remain unchanged.

## Primary task

Given only the independently disclosed provider offerings and the public composition specification,

\[
I_1=\{(A_p,\sigma_p^{I1})\}_{p\in\{A,B,C\}},\qquad G,
\]

reconstruct **both**:

1. the graph-level admissibility/SLA region \(\widehat A_G\); and
2. the graph-survival function \(\widehat\sigma_G(\widehat A_G,H)\).

The target mapping is

\[
\boxed{(I_1,G)\longmapsto (\widehat A_G,\widehat\sigma_G).}
\]

A predictor that is *given* \(A_G\) and outputs only \(\sigma_G(A_G,H)\) does **not** by itself fulfill this goal. The previously frozen Phase-5 M3 graph-prediction procedure is of that latter form. The missing graph-region inference component must be stated and tested explicitly, not presumed already implemented.

## Entrepreneur/information boundary

- Providers independently determine and publish their respective \(A_p\) and \(\sigma_p^{I1}\). The graph entrepreneur cannot choose, retroactively alter, or force their regions to agree.
- The reconstruction method must not use generating provider parameters, private provider traces, Step-0 white-box outcomes, or graph white-box reference outcomes.
- Do not impose equality or artificial constraints among reconstructed provider parameters. Heterogeneous, reasonable existing generating worlds are preferred for the initial development demonstration.
- Preserve the exact disclosed I1 survival estimand; do not replace historical cumulative-compliance I1 with first-violation survival without explicitly creating and labeling a separate interface.

## Rho-conditioned graph admissibility: reference and prediction

In the established PRAISE I1 methodology, admissibility regions are indexed by a **region-content level** `rho_region`. The existing provider-region implementation in `phase2/i1_rho_conditioned_region.py` fits a GMM to completed (log L, log C) samples, draws a joint L/C sample, and extracts nested minimum-area, origin-anchored L/C rectangles containing at least the requested mass. In the current benchmark Q is constant.

Apply the **same explicitly specified rho-conditioned region-extraction semantics**, adapted to completed **graph-level** performance observations, to obtain

\[
A_G^{WB}(\rho_{region})=R_{\rho_{region}}(T_G^{WB}),\qquad
\widehat A_G^{M3}(\rho_{region})=R_{\rho_{region}}(\widehat T_G^{M3}).
\]

Thus the graph region is **not an arbitrary externally fixed target or an entrepreneur-imposed admission threshold**. The parameter `rho_region` identifies the intended coverage level; the frozen extraction rule and performance evidence determine the numerical boundaries. Rho alone does not supply numerical latency/cost thresholds without the performance distribution and extraction convention.

The predicted graph-region extractor must consume only I1-compatible reconstructed-model graph evidence, never hidden parameter values or white-box graph evidence. The reference extractor may use only isolated white-box graph evidence. Freeze the common extraction procedure, rho grid, trajectory handling (including completed/unresolved semantics), and evidence separation before the final test.

Keep `rho_region` distinct from `rho_query`: the first specifies the admissibility-region content, while the second is the compliance-fraction threshold for the survival query, e.g. \(\sigma_G(A_G(\rho_{region}),H;\rho_{query})=P(c_G(A_G,H)\ge\rho_{query})\). Do not silently replace that cumulative-compliance estimand by first-violation survival.

The old frozen Phase-5 Step-0 graph query battery is a different procedure, using white-box calibration to choose **evaluation query regions** from a scaled provider-derived family. It is not itself a reconstruction of \(A_G^{WB}(\rho_{region})\), and the new goal must not retroactively relabel it as such.

## Evaluation targets (both mandatory)

1. **Region recovery:** compare \(\widehat A_G\) against \(A_G^{WB}\) using appropriately specified overlap and boundary-discrepancy measures on a frozen common domain.
2. **Survival recovery:** compare \(\widehat\sigma_G\) against white-box \(\sigma_G^{WB}\) using RMSE as the primary scalar error, with MAE and signed bias as secondary diagnostics, on a frozen set of matched, meaningful graph-region/horizon queries.

Since the predicted and reference admissibility regions may differ, specify **before testing** how survival curves are evaluated on a common domain. A low RMSE evaluated only on one region is not evidence of successful joint region recovery.

A weakly identified or unrecoverable result is still a valid scientific outcome; there is no predetermined minimum performance score or entrepreneur-imposed admission threshold.

## M3 and experiment discipline

- Consolidate/reuse the already developed I1 provider-reconstruction and M3 graph-propagation machinery where scientifically valid.
- The region-recovery step is additional and needs an explicit formulation; it cannot be hidden in the existing fixed-\(A_G\) graph simulator.
- Reuse reasonable existing provider-world configurations as development sources without disclosing their hidden parameters to the method; use independent evidence and keep holdout white-box results inaccessible until predictions are frozen.
- Distinguish development/regression demonstrations from independent generalization evidence.
- Maintain the PRAISE PPG firewall: do not import the unpublished GP+DVI mechanism, readiness score, datasets, or previous QR/YOLO/Lidar setup.
- Do not retrospectively redefine the frozen Phase-4/Phase-5 scientific contracts.

## Next two stages

1. **Consolidation:** specify and implement the complete \((I_1,G)\to(\widehat A_G,\widehat\sigma_G)\) pipeline, including the reference-region construction rule and its information firewall.
2. **Testing:** evaluate both region recovery and graph-survival recovery on controlled, reasonable heterogeneous provider worlds; then assess generalization on independent cases.
