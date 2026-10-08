# Phase-5 V3b FULL343 frozen evaluation adapter

**Frozen:** 2026-10-08

The prediction battery, final white-box battery, and mechanical final-WB audit are now complete. Before reading any prediction curve against the final reference, this file maps the already frozen V2 analysis contract onto the V3b/FULL343 implementation that was itself frozen before end-to-end graph truth was opened.

No performance result is used to define this adapter.

## Primary methods

The primary comparison is:

- M0, scored only where it is operationally applicable;
- M1, the best single common-rescore reconstruction per provider;
- M2, the equal-weight 3-per-provider / 27-joint-model ensemble;
- M3_FULL343, the complete frozen 343-joint-model evidence-weighted distribution.

M3_TOP1, M3_TOP3 and M3_TOP14 remain secondary nested diagnostics. They are not substitutes for FULL343.

## Primary window and metrics

Only H=60,65,...,240 s is used for the primary error summaries.

For each method, report MAE, RMSE, signed bias, maximum absolute error, and the already registered finite-reference-noise-adjusted RMSE.

Summaries are required for ALL, provider world, graph, regime, rho, provider-world x graph, graph x regime, provider-world x regime, and rho x regime.

## Decision analysis

At beta=0.9 (primary) and beta in {0.8,0.95} (secondary), a method accepts when sigma_hat >= beta.

A WB point is decision-resolvable only when its Wilson 95% interval lies entirely on one side of beta:

- certain accept: lower bound >= beta;
- certain reject: upper bound < beta.

Points whose WB interval crosses beta are excluded from decision scoring.

## Method-specific diagnostics

M0 reports applicability counts and operational coverage. No value is imputed where M0 is NOT_APPLICABLE.

M2 reports its finite-portfolio range width, whether the final WB lies inside that range, and distance outside the range. This range is descriptive reconstruction spread, not a confidence or credible interval.

M3_FULL343 has zero support-truncation error by construction. Its plug-in MC SE and conservative MC SE bound are reported. Top1/Top3/Top14 are diagnostics only.

## Topology contrast

The registered within-world contrast remains

Delta_P^M = MAE_M(P,G_SEQ) - MAE_M(P,G_PAR).

It is estimable for P1, P3 and P4.

The registered heterogeneous-minus-symmetric contrast is **not estimable** because all P2 cells failed the prospective Step-0 gate. No P4-only replacement is permitted.

## Reference bootstrap

The registered 10,000-replicate joint trajectory bootstrap is deliberately staged after the deterministic evaluation is frozen. It quantifies finite N=1000 WB-reference uncertainty only and keeps all method predictions fixed.
