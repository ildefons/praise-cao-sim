# PRAISE B1 verification review: v0.2

**Review date:** 2026-10-16  
**User-provided audit archive:** `praise_b1_verification_v0_2.zip`  
**Archive SHA-256:** `edf9ae76f829c3d24198abc5da39e002af941fe6a10761df727618b74cb952ff`

## Outcome

The first local result verification yielded **375 PASS, 1 FAIL, 9 INFO, 0 SKIP**.

- All **233** JSON-manifest SHA-256 values still match the earlier file inventory.
- **30** selected manifest-to-result output hashes match.
- All **6** tested expected frozen-stage statuses match.
- Additional registered reconstruction provenance roots exist (`phase3/results`, `phase5/results/03_reconstruction_v3/P2`, `phase5/results/03_reconstruction_v3b/P2`).
- Phase-5 primary evaluation recomputed from `pointwise_primary_joined.csv` matches `primary_metrics.csv` and the checkpoint for all four methods, with expected H60..240, 12 physical cells, 15 queries per cell and 37 horizons/query for fully applicable methods.
- Phase-6 P4/G_SEQPAR six-way evaluation recomputed from 3,330 saved pointwise rows matches each of the archived method summaries.
- P2 true-parameter audit reproduces six provider/bank metric comparisons, confirms generating parameters lie within frozen bounds, and verifies 42 unique ±20% sensitivity configurations.

### Recomputed Phase-5 results

| Method | Count | MAE | RMSE | Bias |
|---|---:|---:|---:|---:|
| M0 | 1,776 | 0.418735706 | 0.453917914 | -0.418079226 |
| M1 | 6,660 | 0.157015315 | 0.225884455 | +0.149678679 |
| M2 | 6,660 | 0.133950984 | 0.190453032 | +0.100937493 |
| M3_FULL343 | 6,660 | 0.121889894 | 0.180805909 | +0.065105468 |

**These metrics describe the 12 Step-0-eligible Phase-5 physical cells**, not all 16 planned cells. M0 coverage is unequal. This verifies the stored pointwise evaluations, not the raw simulator event semantics.

### Recomputed Phase-6 P4/G_SEQPAR results

| Method | Count | MAE | RMSE |
|---|---:|---:|---:|
| I1STRONG_M2 | 555 | 0.091780781 | 0.113897658 |
| I2AFS_M2 | 555 | 0.094754288 | 0.118256757 |
| I2B_M2 | 555 | 0.102096296 | 0.136174716 |
| I2BVAR_M2 | 555 | 0.157305372 | 0.220862752 |
| I2BHIER_M2 | 555 | 0.094294094 | 0.116950470 |
| I2BV4_M2 | 555 | 0.108538739 | 0.153535911 |

### One failure: B1 audit method-label mapping, not established scientific inconsistency

Failed check:

```
P2_INDUCED recomputation:
ValueError('Missing or nonfinite scoring values for M1_V3B')
```

Root cause: in `evidence_registry_v0_1.json`, E09 method keys intentionally include version identifiers (`M1_V3B`, `M2_V3B`, `M3_FULL343_V3B`), but the saved P2 comparison CSV has `method` labels `M1`, `M2`, `M3_FULL343`. v0.2 passed the versioned keys directly to the CSV filter, returning no rows. Consequently **P2 induced-region recomputation was not performed**; it must not be counted as passing.

Fix committed as new, separately named, `verify_local_evidence_v0_3.py` (original v0.2 and its archived output remain intact). v0.3 maps the names explicitly and adds query/horizon uniqueness checks. It must be executed against the local archived evidence to resolve this failure.

## Remaining limits

- 30 declared result hashes verified, but not every hash in all 233 manifest files; this is not exhaustive file-integrity certification.
- Metrics computed from frozen pointwise CSVs, **not independently reconstructed from per-trajectory event ledgers**.
- Historical Phase-4 pilot metrics have not yet been independently reconciled with local primary CSVs, including changing M3 support/weighting and budget conventions.
- Phase-6 six-way retrospective/development outcomes have been verified numerically on the studied cell, not on held-out worlds.
- Full scientific method-version chronology and simulator code-execution equivalence still need documentation and audit.

**Current status:** B1 registry **v0.1 remains provisional**. No v1.0 freeze until P2 v0.3 rerun and the historical pilot/provenance issues are handled.
