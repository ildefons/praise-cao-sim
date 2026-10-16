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

## Audit progression (2026-10-16)

The user-run v0.1 inventory was received and reviewed:

- 12/12 registry entries had all their registered source/result paths.
- 31/31 registered source files and 17/17 registered result roots were present.
- 233 JSON manifest files were SHA256-fingerprinted, with no skipped hash and no missing registered path.
- Inventory by phase: Phase1 1, Phase2 5, Phase4 50, Phase5 88, Phase6 89.
- Phase5 manifest-name coverage includes 16 Step-0 confirmations, 12 eligible graph prediction manifests, 12 white-box cell manifests, final freeze, deterministic evaluation and bootstrap.
- **Caution:** This is not exhaustive result coverage. The initial 17 registered roots omit some reconstruction provenance, particularly Phase3 results and Phase5 `03_reconstruction_v3` and `03_reconstruction_v3b`. These are explicitly checked in the next verification pass and must be added to the final registry. The old `phase6/checkpoint.json` is a stale snapshot.
- **Caution:** Hashing a manifest does not check any hashes declared *inside* it, nor does it verify CSV row counts, mean errors or WB/prediction joins.

Run the next, still non-simulation audit from the repository root:

```bash
git pull
conda activate praise-cao
python first_science/b1/verify_local_evidence_v0_2.py
```

It checks the original 233 manifest snapshot hashes, selected manifest-output hash links (size capped at 32 MB per file), current freeze statuses, reconstruction provenance directories, and independently recomputes the saved Phase5/Phase6/P2 prediction metrics from joined CSVs. It also checks the P2 true-parameter and sensitivity tables. It writes only to `first_science/b1/local_audit/verification_v0_2/`.

Bundle the verification output for review:

```bash
cd first_science/b1/local_audit
zip -r ~/praise_b1_verification_v0_2.zip verification_v0_2
```

**No scientific data or predictions are modified.** A PASS means the indicated persisted artifact or metric agrees under the audit definition. SKIP means the item was not independently checked, not that it passed. The B1 registry is not yet v1.0 until all reported mismatches and coverage gaps are reviewed.

### v0.2 verification review (2026-10-16)

Review of the user-uploaded verification archive found **375 passes, 1 audit label-mapping failure, 9 informational statuses and no skips**. All registered manifest snapshots and the selected output hashes matched. The Phase-5 and Phase-6 results were independently recomputed from saved pointwise joins and matched the frozen evaluation tables. The P2 evaluation was **not** checked because the v0.2 verifier filtered the method column using versioned registry IDs (`M1_V3B`) rather than the CSV method IDs (`M1`). See [verification review](VERIFICATION_REVIEW_2026-10-16.md).

The corrected next pass is a new script, preserving v0.2 intact:

```bash
cd ~/praise/praise-cao-sim
git pull
conda activate praise-cao
python first_science/b1/verify_local_evidence_v0_3.py
cd first_science/b1/local_audit
zip -r ~/praise_b1_verification_v0_3.zip verification_v0_3
```

Do not claim B1 v1.0 evidence validation until v0.3 and the outstanding historical pilot/provenance reconciliation are reviewed.

### v0.3 local verification closed (2026-10-16)

The uploaded v0.3 report has **399 PASS, 0 FAIL, 9 INFO, 0 SKIP**. The formerly unverified P2 induced-region results now match the saved numerical tables and the registry. The result is documented in [v0.3 verification review](VERIFICATION_REVIEW_V0_3_2026-10-16.md). The Phase-5 battery and Phase-6 six-way saved metrics were also confirmed.

**Next, reconcile the historical pilot**, not a new scientific simulation. On the PRAISE laptop:

```bash
cd ~/praise/praise-cao-sim
git pull
conda activate praise-cao
python first_science/b1/verify_phase4_pilot_v0_1.py
cd first_science/b1/local_audit
zip -r ~/praise_b1_phase4_pilot_verification.zip verification_phase4_v0_1
```

The script independently scores the pilot and the Stage-B M3 mechanism ablation from archived CSVs, checks their saved metrics and manifest hashes, and writes only to the local B1 audit directory. Keep the v0.1 registry provisional until this check and method chronology are reconciled.

## Core evidence registry v1.0 (2026-10-16)

The major pilot-to-battery evidence audit is now closed **at the saved-results verification level**. The original chronological registry v0.1 remains immutable; the reviewed successor is [`evidence_registry_v1_0.json`](evidence_registry_v1_0.json).

- Initial source/result presence: 31/31 source files, 17/17 data roots; 233 manifest fingerprints.
- v0.3 current evidence checks: **399 PASS, 0 FAIL** (Phase5 broad results, Phase6 six-way comparisons, P2 induced-region and provider truth/sensitivity).
- Phase4 pilot + post-hoc Stage-B: **60 PASS, 0 FAIL**, independently recomputed from archived pointwise comparison tables and checked manifest-file hashes; see [Phase4 review](PHASE4_VERIFICATION_REVIEW_2026-10-16.md).
- The [method and evidence chronology](METHOD_VERSION_CHRONOLOGY_2026-10-16.md) distinguishes M2-G1/G2, M3-v4 Top14 pilot, Phase5 V2->V3b FULL343, Phase6 I2 development and the independent P2 induced-region study.

**B1 core registry v1.0 is a reviewed evidence index, not an exhaustive simulator integrity certificate.** Raw ledgers, ancillary experimental branches, all simulation extensions, full manifest transitive-hash coverage and the latest graph-conditioned/joint-parameter tracks still require dedicated inventory before being described as fully verified. Report missing or incomplete evidence honestly; no further simulator experiments are needed to start the manuscript claim audit.

**Next task:** audit the old pilot-oriented manuscript `praise_caise_workshop_note_v11_45(1).pdf` section-by-section against the verified core registry. Preserve scientific definitions and mathematical sections after implementation-level consistency checks; explicitly update the abstract, interpretation, limitations and summary to reflect the completed Phase5 battery and subsequent diagnostics.

## Manuscript audit 2.3b: implementation-level M0–M3 definitions

[Method-definition source audit](METHOD_DEFINITION_SOURCE_AUDIT_2026-10-16.md) is complete at the **contract/code inspection level**, including historical Phase4 M2/M3, registered Phase5 V2, executed Phase5 V3b FULL343, P2 induced-region and matched Phase6 M2-family designs.

Main caveats recorded:

- M0 same-rho product is a restrictive *predictor*, not an SLA certificate.
- Phase4 M2 portfolio explicitly excludes the M1 anchor; Phase5 V3b M2 includes M1's per-provider RMSE-rank-1 models.
- V3b ranks candidates by I1 fit without a hard I1 compatibility gate. Do not describe all selected candidates as proven “compatible”.
- M3 pilot Top14 from a 48/provider candidate bank differs from Phase5 V3b FULL343 from seven fits/provider; Phase5 M3_TOP1 is not definitionally equivalent to M1.
- Gibbs/model support, Monte Carlo numerical error, and model-to-truth accuracy must remain separate.
- Phase6 I1strong-vs-I2 variations change provider information **and** reconstruction loss, even where search and graph simulation budgets are matched.

To check the V3b *actual local frozen selections* against the method rules without new simulations:

```bash
cd ~/praise/praise-cao-sim
git pull
conda activate praise-cao
python first_science/b1/verify_method_support_v0_1.py
cd first_science/b1/local_audit
zip -r ~/praise_b1_method_support_v0_1.zip method_support_v0_1
```

Upload the ZIP for review. The check includes all P1–P4 provider selection banks, 27/343 joint weight supports, and P1/P3/P4 full-support B1400 allocation. It writes only under `b1/local_audit`. **The source-level audit is complete; the local identity checks are not yet verified by this reviewer.** No frozen experiment is changed.

### Completed V3b method-support evidence audit (2026-10-16)

The user-run [frozen method-support audit](METHOD_SUPPORT_VERIFICATION_REVIEW_2026-10-16.md) reports **132 PASS, 0 FAIL**, checking all P1–P4 provider selections, the M2 27-member and M3 343-member product supports and eligible P1/P3/P4 M3 B1400 greedy allocations. This closes Step **2.3b at saved-selection/contract consistency level**. It does not rerun search or simulation; latent model adequacy remains unknown. Next: **Step 2.3c, uncertainty mathematics**.


## Substep 2.3c closed: uncertainty mathematics

The [uncertainty-mathematics audit](UNCERTAINTY_MATHEMATICS_AUDIT_2026-10-16.md) identifies which results are exact (finite-mixture truncation, MC variance algebra, expectation-based noise decompositions), which are conditional/approximate (Wilson, paired bootstrap, normal intervals, budget scaling), and which are merely exploratory (model spread to truth error, deployment admission). **No new simulations or manuscript changes.** The main pending work is **Step 2.4, numerical tables and figures**, followed by simulator/provenance Step 2.5.

## Substep 2.4: all manuscript tables and figures audited (2026-10-16)

The complete [table/figure audit](TABLES_FIGURES_AUDIT_2026-10-16.md) inspects **Tables 1–4 and Figures 1–3** in the historical 26-page PDF. The main pilot saved metrics are previously verified. Important corrections: Table2 mixed prospective and retrospective stages, M0/other-method reference denominators differ, Fig1 matched-B Top1/Top3 are not Table2's operational B100/B300 readouts, Fig2's nondominated set excludes an internally reported dominating Top1 point, Fig3 is a numerical-width extrapolation not accuracy, and Appendix A cites a nonexistent Table2 MC-width column.

**Remaining numerical-signoff boundary:** complete ancillary local CSV checks (Table2 operational Top1/Top3, all per-regime and decisions, Table4 parameters/public-I1 fits, numerical width/source tables) before claiming every historical display value independently verified. The new [read-only collector](collect_display_sources_v0_1.py) packages just existing small source artifacts; it does not rerun scientific experiments.

Run on the original research laptop, from repository root:

```bash
git pull
python first_science/b1/collect_display_sources_v0_1.py
```

Upload `first_science/b1/local_audit/display_sources_v0_1/praise_b1_display_source_evidence_v0_1.zip`. The bundle has an included/missing/skipped manifest so gaps remain visible. No scientific evidence file is altered.

Next after this ancillary check: **Step 2.5, simulator extensions and research provenance**, followed by Step 2.6 report reuse blueprint.

## Substep 2.4 local display archive reconciled (2026-10-16)

Reviewed [the uploaded 22-source archive](TABLES_FIGURES_SOURCE_RECONCILIATION_2026-10-16.md): **22/22 collector hashes matched; 13/13 selected source-manifest output hashes matched**. Original M0–M3 errors, Wilson reference-certain decision percentages (481/555 and M0 274), all Table3 matched-B Top3 per-regime curves, and Table4 parameter/I1 loss values reproduced. Figure2 N200 WB-bootstrap ranges match; Figure3 M1 Wilson width and **clipped** M3 normal bands reproduce manuscript width anchors.

Narrow residual archival gaps: operational Top1 B100/Top3 B300 actual first-100 member estimates and M2 B2700 shared-seed MC width have not been independently recomputed because the requested collector omitted their source-level arrays. Keep these as **not independently checked**, not as numerical contradictions. The 2.4 display/source audit is sufficiently complete to begin **Step 2.5, simulator infrastructure and provenance**. No new simulations are needed.

## Substep 2.5: Simulator extensions and experimental provenance (2026-10-16)

The [source/contract audit](SIMULATOR_PROVENANCE_AUDIT_2026-10-16.md) separates the modified AICon/YAFS composition runtime, Phase5 three-provider AST-to-dependency compiler, fixed physical graph executor, native LCQ ledger accounting, engineering-smoke tests, global prediction/WB freeze protocol, and remaining external-dependency reproducibility risk. The checked Phase5 graphs change logical dependencies on one fixed physical embedding; genuine nested runtime examples exist separately. No active control agents or energy-stress results were established by the core battery. The registered Oct6 mandatory-smoke sequencing deviation remains explicitly disclosed. Oct10 optional trace additions also mean current graph-simulator source need not be byte-identical to frozen run code.

**Remaining independent check:** run the new [read-only installed-runtime and manifest-chain audit](audit_runtime_provenance_v0_1.py) on the original laptop:

```bash
cd ~/praise/praise-cao-sim
git pull
conda activate praise-cao
python first_science/b1/audit_runtime_provenance_v0_1.py
cd first_science/b1/local_audit
zip -r ~/praise_b1_runtime_provenance_v0_1.zip runtime_provenance_v0_1
```

Upload that ZIP. It does not run any YAFS simulation, and fingerprints the currently installed modified YAFS sources without claiming they match the historic Oct6–8 runtime automatically. The source audit is complete; archived environment/timestamp provenance remains provisional until review. Next is **Substep 2.6, preservation and B1 rewrite blueprint**.

## Runtime provenance local verification closed (2026-10-16)

The uploaded [runtime provenance review](RUNTIME_PROVENANCE_VERIFICATION_REVIEW_2026-10-16.md) records **94 PASS, zero FAIL or WARN, five INFO**. All 12 archived prediction-cell manifest hashes match the globally frozen prediction manifest; each of the 12 WB cell manifests references this freeze; all 4 P2 Step0 exclusions remain documented; prediction freeze was recorded at **2026-10-07 19:26:06 UTC**, before earliest final-WB start at **19:51:50 UTC**. Four archived engineering smoke PASS manifests were found, all non-scientific. **The original smoke ordering deviation still exists.** Current installed patched YAFS resolves to AICon HEAD `6eabfa7` (Sep2) and four source files are SHA256 fingerprinted, but the checker did not attest historical Oct7 environment or clean Git working tree. Therefore Step **2.5 closes at documented source and manifest-provenance level**, not exact bitwise replay; continue to **2.6 manuscript preservation/rewrite blueprint**.


## Step 2.6: source-to-report preservation blueprint complete (2026-10-16)

The original 26-page manuscript `praise_caise_workshop_note_v11_45(1).pdf` has been mapped in [the detailed blueprint](MANUSCRIPT_PRESERVATION_BLUEPRINT_V0_1_2026-10-16.md) to a comprehensive **B1 internal technical record**. A 53-row [migration traceability matrix](MANUSCRIPT_MIGRATION_MATRIX_V0_1.csv) maps each historic chapter, Eq (1)–(12), appendices A/B/C, Tables 1–4, Figures 1–3, and requested new Phase5/Phase6/P2 displays to report destinations and evidence gates. The existing mathematically supported content is retained with scope qualifiers; the pilot-centered abstract, interpretation, conclusion and operational “assurance” claims are replaced. Existing pilot displays remain historical, with a restricted/repaired Pareto frontier and provenance labels.

**No manuscript, frozen experiment or source PDF was modified.** Next is **Step 2.7, audit sign-off and drafting authorization**; verify source coverage, 68-entry claim-ledger disposition and outstanding evidence caveats, then start a new `b1/report/` document rather than altering the old CAiSE pilot source.
