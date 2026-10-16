# B1 evidence inventory review, 2026-10-16

## Uploaded inventory reviewed

Input archive: `praise_b1_audit.zip`  
Archive SHA-256: `653e2d21b26ccf1950c7441c16fa00675d3426e769f9d4475c16cb963a66c654`

The audit records:

- Registry items: **12**.
- Registered source documents present: **31/31**.
- Registered local data roots present: **17/17**.
- Missing registered paths: **0**.
- Discovered JSON manifests hashed: **233/233**.
- Manifests by phase: Phase1 **1**, Phase2 **5**, Phase4 **50**, Phase5 **88**, Phase6 **89**.
- Phase5 discovered 16 Step0 confirmation manifests, 12 eligible-cell prediction manifests and 12 final-WB cell manifests, alongside battery-level freezes, evaluation and bootstrap.

**Scientific interpretation:** A satisfactory preservation/discovery check, *not* independent verification of predicted survival, numerical results, hash chains or raw event semantics. The initial registry does not exhaustively cover all reconstruction result roots; particularly Phase3 and Phase5 V3/V3b reconstruction directories must be added before v1.0.

## Independent six-way Phase6 recheck

The previously supplied `i2bv4_six_way_matched_evaluation_bundle.zip` was also available and independently checked.

Bundle SHA-256: `ac7efd696eff9aaa0eeb6ea10212537f1a24fa82874c60c9e7b281fd7c07e0b6`

- Manifest status: `PHASE6_I2BV4_SIX_WAY_MATCHED_EVALUATION_COMPLETE`.
- Saved pointwise evidence: 6 methods x 555 query/horizon points = 3330 rows.
- MAE/RMSE/bias recomputed directly from `pointwise_joined.csv`; all agree to numerical precision with the archived `metrics.csv`.
- SHA-256 of `pointwise_joined.csv`, `metrics.csv`, `decision_beta090.csv`, `paired_summary.csv`, `per_query_metrics.csv` all match the respective values inside `evaluation_manifest.json`.

| Variant | MAE | RMSE | signed bias |
|---|---:|---:|---:|
| I1STRONG_M2 | 0.091780781 | 0.113897658 | -0.022734535 |
| I2AFS_M2 | 0.094754288 | 0.118256757 | +0.011841375 |
| I2BHIER_M2 | 0.094294094 | 0.116950470 | -0.026634434 |
| I2B_M2 | 0.102096296 | 0.136174716 | +0.052636837 |
| I2BV4_M2 | 0.108538739 | 0.153535911 | +0.079527728 |
| I2BVAR_M2 | 0.157305372 | 0.220862752 | +0.154651518 |

**Boundary:** This directly verifies the supplied six-way saved evaluation and manifest integrity, not raw-simulator replay or cross-world generalization.

## Next verification step

`verify_local_evidence_v0_2.py` performs read-only snapshot SHA verification, checks selected manifest-declared output hashes, and independently recomputes Phase5, Phase6 and P2 result summaries from locally archived tables. It leaves all frozen scientific artifacts unchanged. Inspect failures and skipped checks before upgrading the registry to v1.0.
