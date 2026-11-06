# Real archived B1 sequential validation episode

**Provenance:** extracted directly from archived original B1 episode CSVs; not a synthetic story. The full-domain errors below are retrospective evaluator-only quantities, never exposed to acquisition policy.

**Policy:** \`budgeted_top2\` · **Budget:** 15 unique evaluations · **Starting condition:** P1 / G_PARSEQ · **Repetition:** 0.

| Step | Predictor | Provider world | Graph | Revealed cell MAE |
|---:|---|---|---|---:|
| 1 | M1 | P1 | G_PARSEQ | 0.214634 |
| 2 | M2 | P1 | G_PARSEQ | 0.177236 |
| 3 | M3_FULL343 | P1 | G_PARSEQ | 0.144974 |
| 4 | ORIGINAL_TOP14_B1400 | P1 | G_PARSEQ | 0.198697 |
| 5 | ORIGINAL_TOP1_B1400 | P1 | G_PARSEQ | 0.201643 |
| 6 | FIXED_CV_TOP14 | P1 | G_PARSEQ | 0.153043 |
| 7 | FIXED_CV_TOP1 | P1 | G_PARSEQ | 0.141178 |
| 8 | M3_FULL343 | P3 | G_SEQ | 0.116330 |
| 9 | M2 | P3 | G_PAR | 0.098860 |
| 10 | ORIGINAL_TOP1_B1400 | P4 | G_SEQPAR | 0.131200 |
| 11 | M1 | P4 | G_SEQ | 0.190858 |
| 12 | M2 | P4 | G_SEQPAR | 0.120073 |
| 13 | M3_FULL343 | P4 | G_SEQPAR | 0.122670 |
| 14 | M3_FULL343 | P4 | G_PAR | 0.109436 |
| 15 | M2 | P3 | G_SEQ | 0.170681 |

## Terminal choice (policy-available posterior only)

| Predictor | Observations | Posterior mean domain MAE |
|---|---:|---:|
| M1 | 2 | 0.197954 |
| M2 | 4 | 0.144384 |
| M3_FULL343 | 4 | 0.126978 |
| ORIGINAL_TOP14_B1400 | 1 | 0.189492 |
| ORIGINAL_TOP1_B1400 | 2 | 0.166945 |
| FIXED_CV_TOP14 | 1 | 0.158482 |
| FIXED_CV_TOP1 | 1 | 0.150423 |

**Selected predictor:** \`M3_FULL343\`.

## Retrospective audit, inaccessible to selector

**Reference best across 12 cells:** \`M3_FULL343\`.
**Terminal simple regret:** 0.000000000.
**Correct best-method decision:** True.

The example demonstrates an **overall predictor choice for the entire 12-cell domain**, not a per-graph routing decision. No computation-time savings or live deployment are established.
