# PRAISE B1: Local runtime/provenance verification review (2026-10-16)

**Uploaded archive:** `praise_b1_runtime_provenance_v0_1.zip`  
**Archive SHA-256:** `558531ab1a9a3a5748c2dc505eab5fa99739260d3300bcd1fb2ef9c6546d618e`  
**Contents:** `runtime_provenance_v0_1/summary.json`, `provenance_checks.json`, `runtime_fingerprint.json`.  
**Origin:** user executed `first_science/b1/audit_runtime_provenance_v0_1.py` on the research machine. No simulations and no changes to frozen scientific files.

## Result

**94 PASS, 0 FAIL, 0 WARN, 5 INFO**. Inspected all 99 enumerated checks and confirmed those counts from the included JSON records. Four INFO entries describe archived smoke availability and one describes current local source commit identification; INFO is *not* historical-runtime proof.

| Audited feature | Result |
|---|---|
| Installed YAFS source files | All four source files exist; expected PRAISE API/controller code markers present |
| Global prediction freeze | Frozen status, complete=true, final_WB_read=false |
| Cell coverage | **12 eligible predictions + 4 registered P2 Step0 gate failures**, no overlap |
| Prediction-manifest hash links | **12/12** prediction cell SHA-256 values match the global freeze manifest |
| WB linkage | **12/12** final-WB cell manifests match the **same global prediction-freeze SHA-256** |
| WB eligibility | Same 12 physical cells as the frozen prediction set |
| Stage chronology | Global prediction freeze timestamp **before earliest final-WB cell start** |
| Evaluation stage | Frozen deterministic evaluation manifest exists and status matches |
| Smoke manifests | Four present, with frozen PASS statuses recorded; all four explicitly `scientific_evidence=false` |

### Timestamp ordering, UTC

- Global blind-prediction freeze: **2026-10-07 19:26:06.705195+00:00**.
- Earliest final-WB cell start: **2026-10-07 19:51:50.124009+00:00**.
- Reported gap: **25 min 43.419 seconds**.

This is strong *artifact-level evidence of correct recorded separation* between completed blind-prediction freezing and the final white-box evaluation, with verified 12/12 prediction hashes and 12/12 WB backlinks. It does not establish a formal information-flow security proof or guarantee no earlier unrecorded WB inspection occurred.

### Recorded non-scientific smoke manifests, UTC

| Smoke type | Frozen PASS status | Timestamp |
|---|---|---|
| Four-graph Phase5 V2 smoke | `FROZEN_PHASE5_ENGINEERING_SMOKE_PASS_V2` | 2026-10-06 09:41:37 |
| Mandatory supplement | `FROZEN_PHASE5_MANDATORY_ENGINEERING_SMOKE_COMPLETION_PASS_V2` | 2026-10-06 09:41:38 |
| V3b graph adapter | `FROZEN_PHASE5_V3B_GRAPH_ADAPTER_SMOKE_PASS` | 2026-10-06 18:56:10 |
| V3b FULL343 adapter | `FROZEN_PHASE5_V3B_FULLSUPPORT_GRAPH_ADAPTER_SMOKE_PASS` | 2026-10-06 19:21:50 |

**Important:** the earlier `PHASE5_ENGINEERING_SMOKE_COMPLETION_AND_SEQUENCING_DEVIATION_2026-10-06.md` remains authoritative: some registered smoke tests were completed after the I1/Step0/M1/M2 scientific steps. The presence of frozen PASS manifests on October 6 does not retroactively restore the intended preregistered test ordering.

## Local currently installed runtime

The audit resolves YAFS directly from the original development checkout `/home/ildefons/praise/aicon/src/yafs/src/yafs`.

- Local parent AICon Git HEAD: `6eabfa70531e7091e777a0946ffa967721c0f538`.
- Public AICon main HEAD during review is **the same commit**; that commit was made **2026-09-02 09:16 UTC**, before the October scientific runs.
- Four currently installed YAFS files were SHA-256 fingerprinted:

| Source | Local SHA-256 |
|---|---|
| `application.py` | `0f50e3b146ced9b2da7cffbfc9f6f4b05aaf3e6e229ac0f2803d7a5d9bdc249f` |
| `core.py` | `09bcb493f312ae9706eb0e09808345286646287ea87a0f1b8097fcfcff3ba41f` |
| `stats.py` | `106feca7278b23eb0986a54a0045f2eac03ccf53397a115d27020e70982f8fc2` |
| `distribution.py` | `d8dee9f01885e5fe69154760d93c67807f7fbee6d768a8e3d87b54033e84775a` |

Python **3.10.20**, NumPy **1.26.3**, pandas **2.3.3**, SimPy **4.1.2**, NetworkX **3.4.2**, Optuna **5.0.0**, SciPy **1.15.3** were recorded for **the current audit environment**. These values must **not** be retrospectively assumed to be the complete original frozen-run environment.

### What is and is not established for AICon

The checked parent Git HEAD matching the public September 2 AICon source is useful: it identifies a concrete revision of the dependency that can be retrieved. However, the script **does not check local Git dirty status** or compare working-tree bytes to Git blobs at that commit, and no contemporaneous Oct7 package/environment lock is provided. It therefore does not prove that the imported YAFS files were identical to AICon HEAD at the time of the original run. Historical dependency provenance is **partially resolved**, not fully attested.

Likewise the current PRAISE checkout commit in the audit is `d016871161dfac151431b8cc6427db02114ab6d6`, reflecting ongoing B1 documentation. It is not the earlier scientific execution commit. Later Oct10 PRAISE graph-simulator source changes remain a documented reason not to equate today's HEAD with original frozen execution.

## Scientific interpretation and sign-off

- **Source audit:** completed; modified runtime and bounded three-provider graph compiler/executor inspected, with explicit narrow scope.
- **Selected artifact chain:** independently verified at archive level, including all 12 prediction hashes, all 12 WB backlinks, prediction-before-WB UTC timestamps and final evaluation status.
- **Engineering tests:** frozen smoke manifest statuses and non-scientific flags verified; original sequencing deviation still explicitly disclosed.
- **Exact bitwise reproducibility:** **not certified**. Requires a contemporaneous source/lockfile record or replay against the specific frozen PRAISE commit and confirmed AICon working tree; these are not prerequisites for a transparent internal technical report.
- **Raw-ledger output fidelity:** not reconstructed from raw YAFS request events; earlier audits verified saved pointwise numerical results.

**Substep 2.5 is CLOSED at the bounded source + manifest provenance level.** Preserve the remaining AICon historical-pin and raw-ledger limitations, without treating them as evidence that validated saved results are numerically wrong.

**Next action:** Substep 2.6, design the exact **retain / revise / replace** blueprint for each historical manuscript section, equation, table and figure, and map the Phase5/Phase6/P2 material into the B1 internal report before beginning prose edits.
