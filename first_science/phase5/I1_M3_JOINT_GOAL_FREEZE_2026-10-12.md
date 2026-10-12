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

The method must construct \(A_G\) from public I1 provider regions and public graph topology, rather than take an arbitrary query boundary as its sole input. Existing M1/M2 forward-composition rules supply that step; M3 predicts survival on the same induced region.

## Entrepreneur/information boundary

- Providers independently determine and publish their respective \(A_p\) and \(\sigma_p^{I1}\). The graph entrepreneur cannot choose, retroactively alter, or force their regions to agree.
- The reconstruction method must not use generating provider parameters, private provider traces, Step-0 white-box outcomes, or graph white-box reference outcomes.
- Do not impose equality or artificial constraints among reconstructed provider parameters. Heterogeneous, reasonable existing generating worlds are preferred for the initial development demonstration.
- Preserve the exact disclosed I1 survival estimand; do not replace historical cumulative-compliance I1 with first-violation survival without explicitly creating and labeling a separate interface.

## Rho-conditioned graph admissibility: inherited M1/M2 semantics

**Clarification 2026-10-12:** Preserve the established I1-M1 and I1-M2 forward-composition workflow. Provider regions `A_p(rho_region)` are constructed by the existing I1 provider-card procedure and disclosed externally. The graph entrepreneur composes these public regions through `G` using the existing topology-aware boundary algebra, including public fixed-stage terms, to obtain **one public, induced graph region**:

\[
A_G^{I1}(\rho_{region})=\operatorname{Compose}_G(\{A_p(\rho_{region})\}).
\]

For supported operators the latency, cost and quality boundaries follow the established `sequence` (sum L, sum C, min Q) and `parallel_all` (max L, sum C, min Q) rules, plus explicitly modeled fixed terms.

This is the graph admissibility region for the pilot, shared by M1, M2, M3 and white-box evaluation. **Do not reconstruct a separate graph region from graph-level simulated observations** or imply that a differently estimated white-box region must be compared with the public induced region.

Predict graph survival on that exact region, with the existing cumulative-compliance estimand:

\[
\widehat\sigma_G^{M3}(A_G^{I1}(\rho_{region}),H;\rho_{query})
\quad\text{vs}\quad
\sigma_G^{WB}(A_G^{I1}(\rho_{region}),H;\rho_{query}).
\]

Keep `rho_region` (public provider-region construction) separate from `rho_query` (compliance fraction in survival). The historic experiments use the same-rho diagonal when specified.

The phrase `A_G^WB` should **not** be used here to imply a new graph-level white-box GMM extraction step. The graph-level white-box evidence supplies the reference survival *on the shared public region*. The graph region is a public I1-derived composition, not a separately estimated latent target. This corrects the provisional implementation plan while preserving the broader frozen target of graph-level region and survival from I1.

The former Phase-5 Step-0 scale-calibrated graph-query battery is an additional experimental design; it is not the direct same-rho induced-region pilot.

## Evaluation targets

1. **Graph-region construction:** verify that `A_G^{I1}(rho_region)` is computed correctly and consistently from public provider offerings and public graph topology, using the same implementation/rules for all methods. This is a deterministic contract test, **not region-recovery accuracy against a different WB target**.
2. **Graph-survival prediction:** compare M3 against graph white box and, where appropriate, M1/M2 under the **identical induced graph region**, common `rho_query` and horizons. RMSE is primary; MAE and bias secondary.

A poor result is still valid scientific evidence. Do not change the region or method after viewing reference survival to improve agreement.

## M3 and experiment discipline

- Consolidate/reuse the already developed I1 provider-reconstruction and M3 graph-propagation machinery where scientifically valid.
- Reuse the existing public-I1 forward boundary composition for \(A_G(\rho)\), as in M1/M2. Do not use the experimental graph-ledger GMM extractor for this primary pilot.
- Reuse reasonable existing provider-world configurations as development sources without disclosing their hidden parameters to the method; use independent evidence and keep holdout white-box results inaccessible until predictions are frozen.
- Distinguish development/regression demonstrations from independent generalization evidence.
- Maintain the PRAISE PPG firewall: do not import the unpublished GP+DVI mechanism, readiness score, datasets, or previous QR/YOLO/Lidar setup.
- Do not retrospectively redefine the frozen Phase-4/Phase-5 scientific contracts.

## Next two stages

1. **Consolidation:** specify and implement the M1/M2-compatible \((I_1,G)\to(A_G^{I1},\widehat\sigma_G)\) pipeline and its information firewall.
2. **Testing:** verify induced-region construction and evaluate graph-survival recovery on controlled, reasonable heterogeneous provider worlds; then assess generalization on independent cases.
