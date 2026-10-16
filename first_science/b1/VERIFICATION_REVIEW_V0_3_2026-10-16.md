# B1 evidence verification review: v0.3 (2026-10-16)

**Reviewed archive:** `praise_b1_verification_v0_3.zip`  
**Archive SHA-256:** `e9e6d8a19c2c05b406313a86ff4ec00c11722fd5f435dfab976538a5623e11c0`

## Result

**399 PASS, 0 FAIL, 9 INFO, 0 SKIP.** The sole v0.2 audit-script failure was corrected by an explicit map between registry variant IDs and persisted evaluation `method` names. The original v0.2 report remains intact.

| Checked category | PASS |
|---|---:|
| Original manifest fingerprints unchanged | 233 |
| Selected manifest-declared output hashes | 30 |
| Required completed-stage statuses | 6 |
| P2 induced public-region retrospective comparison | 24 |
| P2 privileged truth and sensitivity | 26 |
| Phase-5 evaluated battery | 38 |
| Phase-6 six-way development comparison | 39 |
| Additional reconstruction provenance roots present | 3 |
| **Total** | **399** |

Nine INFO rows report the nine selected manifest status strings; they are not independent scientific checks.

### P2 induced graph-region comparison independently recomputed

The frozen `matched_survival_curves.csv` has 185 primary H60..240 evaluation points for each of the three compared methods, 5 rho-diagonal regions × 37 horizons. These scores were recomputed from persisted `sigma_hat` and `sigma_wb`, matched against both the frozen `matched_rmse_summary.csv` and versioned B1 registry E09:

| Versioned registry ID | Saved evaluation ID | MAE | RMSE | Bias |
|---|---|---:|---:|---:|
| M1_V3B | M1 | 0.132000000 | 0.153320438 | 0.041491892 |
| M2_V3B | M2 | 0.140583784 | 0.163709849 | 0.137906306 |
| M3_FULL343_V3B | M3_FULL343 | 0.127867436 | 0.148527911 | 0.042632208 |

**Scientific boundary:** This is a separate development experiment on one P2/G_PAR induced region, not a recovery of the four excluded P2 Step-0 cells from the prospective Phase-5 battery. Graph model costs are native and unmatched; the graph admissibility region is shared by M1/M2/M3.

### Broad results consistency

Phase-5 primary comparison (12 eligible cells, 6660 H60..240 points per M1/M2/M3): checkpoint-reported M1/M2/M3 MAEs 0.157015/0.133951/0.121890 were recomputed and checked. The M0 0.418736 aggregate is on only 1776 applicable points, so M0 is not an equally-covered competitor.

Phase-6 P4/G_SEQPAR six-way development (555 points per method): I1STRONG, I2AFS, I2B, I2BVAR, I2BHIER and I2BV4 numerical summaries all reproduced and agreed with archived tables.

The P2 true-parameter audit six comparisons and the 42-configurations sensitivity table also passed.

## Incompleteness and next audit

- **Phase-4 historical pilot** numerical results, manifest chains and nested-support post-hoc Stage-B ablation are not yet independently reconciled against local source CSVs. The prior v11_45 manuscript is a historical pilot document, not the evidence authority for later phases.
- **Raw-ledger fidelity** is not verified: the main passes use archived pointwise/reference CSVs, not independent replay or reconstruction from YAFS event ledgers.
- **Hash scope** covers the original 233 manifest file fingerprints and 30 selected manifest-declared outputs, not every artifact and SHA linkage.
- **Method chronology** must distinguish original 48-per-provider Top14 pilot M3, V3b 7-per-provider FULL343 in Phase-5, and the later P2 induced-region experiment; do not transfer pilot performance to other versions.
- **Registry version** remains provisional v0.1 until historical pilot review and explicit verification-level annotations are incorporated.

The next read-only audit is `verify_phase4_pilot_v0_1.py`, which checks the historical single-graph M3-v4 pilot from `phase4/results/m3_v4_final_evaluation_v1` and the post-hoc cost-matched Stage-B M3 ablation from `phase4/results/m3_posthoc_stage_b_ablation_v1`. It compares their saved pointwise curves with per-method MAE/RMSE/bias and verifies the named manifest-to-output hashes. No simulation is required.
