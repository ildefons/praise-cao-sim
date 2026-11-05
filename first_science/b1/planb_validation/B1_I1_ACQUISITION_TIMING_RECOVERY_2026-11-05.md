# B1 I1 acquisition timing recovery — local terminal evidence (2026-11-05)

**Status:** supplementary historical timing evidence; not an independent-world cost estimate and not a modification of B1 v1.

## Recovery source

The user executed a **read-only** Python extraction of `python_wall_seconds` from:

`first_science/phase5/results/01_i1/{P1,P3,P4}/i1_{region,sigma}_evidence_manifest.json`.

The values below are transcribed from the resulting terminal output. The underlying six I1 manifest files were **not uploaded** or separately rehashed in this review. These figures therefore carry *local user-reported manifest provenance*, not an independently verified source-file fingerprint.

| World | Region acquisition (s) | Sigma acquisition (s) | Combined (s) | Combined (min) | Combined (h) |
|---|---:|---:|---:|---:|---:|
| P1 | 275.682001279 | 267.565283077 | 543.247284356 | 9.0541 | 0.150902 |
| P3 | 324.175162513 | 359.204497613 | 683.379660126 | 11.3897 | 0.189828 |
| P4 | 311.072630671 | 306.602570828 | 617.675201499 | 10.2946 | 0.171576 |
| **Sum** | **910.929794463** | **933.372351518** | **1844.302145981** | **30.7384** | **0.512306** |

Each region/sigma acquisition phase consumes its own bank of 100 complete-world trajectories. The three providers' public-I1 data come from the same per-world simulation executions, and their durations must **not** be multiplied by three. The extracted numbers time acquisition corpora only, not the total I1 pipeline (public-card construction, parsing, writing metadata and any unrecorded overhead).

## Historical stage-duration bookkeeping update

The previously audited 12-cell stage-duration subtotal **excluding I1 acquisition** is:

- Phase-II M1/M2/M3 combined prediction: **23.941684 h**.
- Step-0 calibration: **2.775012 h**.
- Step-0 confirmation: **3.749752 h**.
- Final WB: **17.567355 h**.
- **Subtotal: 48.033803 h** (sum of per-stage wall durations, not project makespan or CPU-hours).

Add the newly recovered **0.512306 h** of I1 region/sigma acquisition for P1/P3/P4:

**Updated sum of measured historical stage durations: 48.546109 h** (rounded using prior audited stage figures).

This is **still incomplete** and is **not** a fresh seven-method battery cost. Outstanding unpriced or non-isolated work includes I1 public-card materialization, provider-local V3/V3b reconstruction, the 48-candidate original-style and fixed-CV banks, all four original/fixed-CV Top14/Top1 graph prediction variants, failed-world attrition, shared setup and I/O. Some stage durations are wall times measured for parallel work and are not additive as an actual end-to-end clock time.

## Feasibility conclusion

- Historical I1 **region/sigma acquisition timing recovered** for three existing eligible worlds.
- **NO-GO** for independent-world execution remains: no prospective physical-world generator or eligible-world sampling law; not yet a defensible full seven-method runtime price or statistical battery count.
- Continue a read-only archival-log search for original-style and fixed-CV graph stages and provider preparation. Do not rerun any simulation or alter the frozen seven methods, acquisition strategy, budgets or prior results.
