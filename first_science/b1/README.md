# PRAISE B1: experiment and evidence registry (v0.1, 2026-10-16)

**Purpose:** prepare a neutral internal technical report about what the PRAISE `tau=(I,M)` program actually designed, executed and learned. This is an **evidence inventory**, not a new scientific result or a rewritten CAiSE paper.

## Registry and audit

- [evidence_registry_v0_1.json](evidence_registry_v0_1.json): versioned machine-readable entries E01–E12, including scope, method variant, evaluation role, reported numerical outcomes, artifact paths, and limitations.
- [inventory_local_evidence.py](inventory_local_evidence.py): read-only audit of on-laptop results, manifest metadata and file hashes. It does **not** execute the simulator or change frozen results.
- The latest supplied old-paper starting point is `praise_caise_workshop_note_v11_45(1).pdf` (26 pp., pilot-oriented). It is a **historical evidence source**, not the authority for later Phase-5 or Phase-6 claims. This PDF is not added to GitHub automatically.

## Critical scientific distinctions

1. **Target metric:** `sigma_G(A,H;rho) = Pr[c_G(A,H)>=rho]`, cumulative compliance among *decided* requests. A request is decided upon completion or latency-deadline failure. Unresolved requests are excluded; zero-decided-request convention is compliance 1. This is **not** first-passage survival.
2. **E02 pilot vs E06 broad battery:** pilot M3 production MAE ~0.0304 (single parallel graph, N200 WB) is a historical, condition-specific result. Broad Phase-5 eligible-battery M3 FULL343 MAE 0.121890 (N1000 WB) retains aggregate ranking over M1/M2 but demonstrates substantial residual errors, particularly in nontrivial Mid/Stress queries. Neither contradicts the other.
3. **Eligibility:** planned 4 provider worlds × 4 graphs = 16 physical cells; **12 eligible** (P1/P3/P4), **4 P2 Step-0 failures**. The registered heterogeneous-minus-symmetric contrast is **not estimable**. The later P2/G_PAR induced-region experiment **is a different design**, not a repaired P2 Phase-5 cell.
4. **M3 is version-specific:** the original pilot uses 48 provider candidates and 14 retained joint models. Prospective V2 originally planned Top14, but a documented pre-graph-WB V3b full-support revision propagated all 343 Cartesian joint models. The October 12 induced-region P2 study uses V3b seven candidate models/provider. Do not claim one common unqualified M3 implementation across chapters. The established V3b implementation constructs a Cartesian ensemble of independently fitted provider models, not an optimizer jointly fitted to graph white-box truth.
5. **Different study roles:** registered design ≠ executed evaluation; prospective evaluation ≠ post-hoc diagnostic; development on P4/G_SEQPAR ≠ held-out generalization. Keep method changes and selection evidence dated.
6. **Precision vs fidelity:** graph Monte Carlo SE, finite-provider-support spread, I1 acquisition error and WB-reference error are different quantities. Low numerical error does not establish low approximation error.
7. **Truth firewall:** hidden generator parameters are permitted in retrospective audits only, never as reconstruction input. Uphold the strict PPG firewall.
8. **Documentation defect:** `phase6/checkpoint.json` is an *early-stage* snapshot and does not reflect later Phase-6 development executions. Do not use it alone as current execution-status authority; verify individual local prediction and evaluation manifests.

## Core frozen result, from `phase5/checkpoint.json`

Main Phase-5 V3b Full343 evaluation: 12 eligible physical cells × 15 queries × 37 horizons = 6,660 per fully applicable method.

| Method | MAE | RMSE | Bias | Evaluation points |
|---|---:|---:|---:|---:|
| M0 | 0.418736 | 0.453918 | -0.418079 | 1776 (applicable only) |
| M1 | 0.157015 | 0.225884 | +0.149679 | 6660 |
| M2 | 0.133951 | 0.190453 | +0.100937 | 6660 |
| M3 FULL343 | **0.121890** | **0.180806** | +0.065105 | 6660 |

These are **checkpoint-reported** numbers. Their primary local CSV and manifest files must still be rehashed and reconciled before final B1 sign-off. M0 coverage differs, so it is not a like-for-like aggregate error comparator.

## Source authority hierarchy

- **A. Frozen execution contracts and hash-verified primary local manifests/CSV:** authoritative for exactly what ran and how outcomes were computed.
- **B. Frozen checkpoint and signed-off mechanism closure notes:** useful summaries, but reconcile against A.
- **C. Later research-plan narratives and user-reported terminal output:** informative, mark their provenance and verify local files.
- **D. Historical manuscript prose and figures:** candidate technical material, never silently carry claims forward after a later contradicting or broader experiment.

If two sources disagree, **do not average or silently reconcile**. Record an explicit issue referencing both paths; investigate chronology, changed method definitions, changed SLA boundary, changed reference bank and metric scope.

## Local verification, without simulations

On the PRAISE laptop (from repository root):

```bash
python first_science/b1/inventory_local_evidence.py
```

Outputs are placed under `first_science/b1/local_audit/` (not committed):

- `local_inventory_v0_1.json`: exact directory presence, file counts and byte counts for all registered result roots;
- `local_manifest_hashes.csv`: relative paths, sizes and SHA-256 for discovered JSON manifest files;
- `missing_evidence_paths.csv`: source and local evidence roots absent on disk.

This is an inventory **only**. It does not prove that every SHA recorded *inside* a manifest matches its referenced CSV or ledger. That is a separate integrity-validation pass.

## Issues to resolve before drafting the internal report

| Issue | Action |
|---|---|
| Phase-4 pilot and Phase-5 V3b labels | Attach method-version/algorithm/seed provenance to every figure and table |
| Phase-5 V2 registered Top14 versus V3b FULL343 | Explicitly describe pre-graph-WB change and its justification |
| Complete Phase-5 results coverage | Verify P2 Step-0 exclusions and exactly 12 × 15 × 37 records per full method |
| Phase-6 study completion / variant results | Verify all prediction and matched-evaluation manifests, and distinguish development from held-out evidence |
| P2 diagnostics | Cross-reference frozen M1/M2/M3 predictions and recent privileged truth audits without merging populations |
| Simulator additions | Inventory actual YAFS/AICon changes separately before claiming engineering novelty |
| Original manuscript `v11_45` | Mark statements valid only in pilot; audit cost accounting and uncertainty claims before reuse |
| Report writing | Build a per-claim evidence table and flag unknowns; do not create missing evidence by new simulations |

## Immediate scope of Step 1

This registry is **v0.1, not yet fully locally verified**. Completion of Step 1 requires importing local manifest hashes, checking the actual Phase-5/Phase-6 output row counts, recording missing evidence without replacement, and freezing the reviewed registry as v1.0. Only then should the old manuscript be edited.
