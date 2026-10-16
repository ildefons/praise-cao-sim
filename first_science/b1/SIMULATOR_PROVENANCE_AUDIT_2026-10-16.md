# PRAISE B1: Substep 2.5, Simulator and Experimental Provenance Audit

**Date:** 2026-10-16
**Status:** Source and frozen-contract review complete; local installed-runtime/manifest timeline audit is pending.
**No new simulations or changes to frozen scientific data.**

## Source basis and evidence levels

- PRAISE repository: examples/praise_*_probe/main.py; Phase3 m1_graph_simulator_v2.py; Phase4 G1/G2 variants; Phase5 phase5_graph_ast_v2.py, phase5_graph_simulator_v2.py, phase5_runtime_v2.py; Phase5 smoke, tests, execution contracts and scientific stage runners.
- Separate AICon repository, current public main: src/yafs/src/yafs/application.py and core.py, containing modified YAFS PRAISE APIs and controller implementation. Current main at review time: 6eabfa70531e7091e777a0946ffa967721c0f538. **Not proven to be the installed source at the October scientific freeze.**
- Existing B1 Step1: source/result inventory, 233 archived manifest fingerprints, 399-pass numerical evaluation verification, 60-pass pilot Stage-B check, 132-pass V3b model-support check, 22 archived display files.
- Validation levels: source implementation established; smoke design and documented PASS stages identified; stored numerical result reconciled; original runtime revision, every raw ledger and complete transitive dependency closure not independently reproduced.

## 1. Implemented architecture

| Layer | Source | Supported scope |
|---|---|---|
| DES substrate | Modified YAFS/AICon | SimPy/Sim, per-message routing and service, queueing and fixed physical links |
| Composition registration | AICon yafs/application.py | add_service_module_praise, set_composition_output_praise; branch identifiers, depends_on, validation against duplicates/self-dependency and missing branches |
| Runtime join/dependency controller | AICon yafs/core.py | Controller completion events; activate dependent siblings only when predecessor completions of the same request/scope have arrived; maintain composition_path frames across nested invocations |
| Initial native graph | phase3/m1_graph_simulator_v2.py | Three provider branches, all-required parallel composition, FCFS stochastic Gamma-like service demands, fixed source/Fpre/provider/Fpost physical substrate |
| Graph stress variants | phase4/m2_g1_graph_simulator.py, m2_g2_graph_simulator.py | Fixed public network/graph variants; reuse native composition mechanics |
| Frozen Phase5 AST compiler | phase5/phase5_graph_ast_v2.py | Pure compiler of sequence and parallel_all over exactly three unique provider leaves; reject repeats, unknown leaves and cycles; exact graph dependency sentinels |
| Frozen Phase5 executor | phase5/phase5_graph_simulator_v2.py | One controller executing compiled three-provider dependencies on an otherwise fixed physical embedding; deterministic arrival source and Gamma/deterministic service-time distributions |
| Ledger and SLA scoring | phase3/m1_graph_simulator_v2.py; phase1/sla_compliance_analysis.py | Extract top-level LCQ outcomes and apply decided-request deadline/cumulative-compliance semantics |
| Scientific method engines | Phase3/4, Phase5 V3/V3b FULL343 | Provider-I1 fitting and native graph simulation of one, 27, or 343 joint reconstructed models, weighted curve integration |
| Scientific registration | phase5_runtime_v2.py and frozen stage scripts | Named seed banks, SHA manifests, Step0 eligibility, reconstruction freezes, prediction freeze, WB lock and evaluation |

### Four scientific graph structures

Exactly these maps are asserted by phase5_graph_ast_v2.py:

- G_PAR: A(), B(), C().
- G_SEQ: A(), B(A), C(B).
- G_SEQPAR: A(), B(A), C(A).
- G_PARSEQ: A(), B(), C(B).

These are **logical execution dependencies**, not four independent physical infrastructure topologies. The physical network remains a Source/Fpre/three-provider/Fpost star-like embedding with fixed placements. The nested-looking logical AST is flattened to one composition controller in the Phase5 experiment. Independent examples/praise_nested_composition_probe and praise_dependency_scope_probe exercise genuine scoped nesting in the runtime, but the Phase5 evaluation does **not** evaluate arbitrary recursively deployed nested controllers, repeated provider leaves, dynamic reconfiguration, retries or graph cycles.

### LCQ and modeling limits

- The top-level ledger assigns completed-request latency as Fpost completion minus initial Fpre emission; completed-request cost accumulates per-stage service duration times node COST; quality is minimum native trace qos. Unfinished requests remain distinguishable.
- Phase5 messages are constructed with LinearQoS(L=0,R=1). The quality coordinate exists but active quality variability is **not established** by the inspected provider family. Verify empirical Q dispersion from native traces before claiming rich three-axis degradation.
- Physical node WATT values are zero in the inspected graph constructors. **No meaningful energy/sustainability experiment** is established by this battery, even though energy remains a broader CAO motivation.
- The management network is instantiated with an empty acting agent list. The experiment is **offline performance prediction of composition**, not runtime agent planning, active-inference control or dynamic AICon orchestration.
- The hidden provider worlds and reconstructions use related one-server FCFS/Gamma process families; misspecification, faults, physical relocation and real production cloud/edge workloads are not experimentally tested here.

## 2. Test and engineering validation taxonomy

| Probe/stage | What its code is designed to check | Strength and limitation |
|---|---|---|
| examples/praise_composition_probe | Basic all-required join registration, branch completion, one output | Concrete integration probe, not exhaustive formal concurrency verification |
| examples/praise_dependency_barrier_probe | Dependent branch waits for sibling completion barriers | Demonstrates a particular schedule/probe |
| examples/praise_dependency_scope_probe | Reused local branch IDs in outer/inner controllers must not corrupt invocation scope | One explicit nested-scope adversarial test |
| examples/praise_nested_composition_probe | Runtime nested composition behavior | Does not show Phase5's fixed 3-provider battery uses arbitrary nested controllers |
| phase5/test_phase5_runtime_v2.py and neighboring tests | Contract IDs, 16-cell enumeration, AST maps, seed separation, unsupported graph rejection | Tests present; B1 has not independently rerun all unit tests |
| phase5/run_phase5_smoke_v2.py | All four graph ASTs on throwaway 99-million+ seeds, deterministic replay with same seed, basic SHA/manifest/global freeze checks | Mandatory original smoke but did not cover every registered engineering clause before first science |
| phase5/run_phase5_mandatory_smoke_completion_v2.py | Actual checkpoint/resume, M3 nested readings, allocation checks, LHS-MSE diagnostic, complete/incomplete global-freeze control | Executed **after** early scientific I1/Step0/M1/M2; cannot retroactively satisfy pre-execution ordering |
| phase5/run_phase5_graph_prediction_v3b_adapter_smoke.py | Native graph interface with real reconstructed provider bank | Non-scientific small smoke, not performance validation |
| phase5/run_phase5_graph_prediction_v3b_fullsupport_adapter_smoke.py | All 343 candidate IDs resolve; allocation and sentinel ranks 1,2,3,14,343; short native smoke | Not full 343-member/240-second exhaustive replication of the scientific run |

These are **validated/tested scopes**, not claims of proof for arbitrary composition semantics. Archived smoke PASS is reported in previous closure notes; local statuses/timestamps have not been independently reconciled in this Substep 2.5.

## 3. Scientific provenance and firewall

The originally registered V2 chain is:

engineering smoke -> published I1 evidence freeze -> Step0 calibration -> Step0 confirmation/eligibility -> provider reconstruction -> blind prediction -> global prediction freeze -> final white-box N1000 -> evaluation -> WB-reference bootstrap.

- Public I1 is a disclosure **produced from provider-private evidence**. This private acquisition is allowed to the publisher but not the reconstruction consumer. The I1 card and associated public surfaces are the consumer input.
- Step0 uses **dedicated white-box calibration/confirmation seeds** to select nondegenerate SLA query regions and determine physical-cell eligibility. Step0 WB is an allowed *experiment-design input*, **not** the embargoed final-WB reference.
- The registered 16 physical world-by-graph cells became 12 eligible (P1/P3/P4 across four graphs) and four P2 gate-failures. P2 was not repaired or replaced after the gate.
- The initially registered V2 provider methods were changed to V3 seven independent fit runs, V3b common-N100 RMSE selection, and M3 FULL343 support. Final FULL343 revision followed a pregraph retained-mass audit (Top14 mass P1=.551984, P3=.961909, P4=.866545), *not* graph WB accuracy, according to the frozen preexecution contract. These are documented **method-development changes**, so a fully unchanged original prospective methodology must not be claimed.
- phase5/run_phase5_graph_prediction_v3b_fullsupport.py::_freeze_global enumerates all 16 cells, hashes the 12 eligible cell prediction manifests and records four Step0-failed cells. The returned global status is FROZEN_PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE.
- phase5/run_phase5_final_wb_v3b_fullsupport.py::_unlock_and_eligibility enforces this complete global freeze, confirms the saved prediction-manifest hashes and final_WB_read=false, and only then unlocks N1000 fresh seeds 54000..54999 for each eligible cell.
- Prediction cell manifests include versioned graph/seed contract hashes, frozen query hash, provider-selection manifest hash, code_commit, output SHA256s, simulation budget and firewall flags. Final WB cells record global freeze hash and WB seed provenance. Evaluation preflight requires WB freeze plus separate WB mechanical-audit PASS.

The **existence of these safeguards in code is verified**. No security proof was performed; the complete historical manifest-to-executed-binary chain has not yet been checked. Existing B1 numerical verifications establish stored outputs, not absence of all possible accidental information leakage.

## 4. Non-ideal but important scientific chronology

**Mandatory smoke ordering deviation:** phase5/PHASE5_ENGINEERING_SMOKE_COMPLETION_AND_SEQUENCING_DEVIATION_2026-10-06.md explicitly records that all-four-AST smoke was initially incomplete relative to the registered mandatory checklist before scientific I1, Step0, M1 and M2. Supplementary smoke later covered the missing clauses on throwaway non-scientific data. This restores engineering coverage, **not original temporal order**. It must remain in the B1 limitations/provenance account.

**Method changes:** V2->V3->V3b FULL343 revisions were recorded before reading *final end-to-end graph WB* but after earlier public-I1/local-selection evidence had been inspected. Neither a generic posthoc performance repair nor an unchanged preregistered method.

**Source changed after frozen runs:** Git history of phase5_graph_simulator_v2.py contains two later commits exposing optional native/provider rows (14a395aac0f1 and a1630802da44, Oct10), after the early Oct6/7 Phase5 prediction/WB stage. The latest repository version cannot be assumed to be bitwise the one used for those frozen scientific runs. Archived scientific manifests record the PRAISE code_commit to establish *that* version; one must use the corresponding commit for an exact code replay.

## 5. External patched YAFS/AICon dependency gap

The essential branch-dependency/composition API does not live in praise-cao-sim. It lives in the separate AICon YAFS sources. PRAISE README identifies the external substrate but the reviewed tracked repository has **no vendored runtime, explicit dependency revision pin or lockfile**. A PRAISE scientific code_commit is therefore **insufficient by itself** to reproduce the exact underlying controller implementation. The current public AICon main ref listed above is contextual only, not an attestation of the local installed revision at the time of frozen science.

A local read-only audit script, b1/audit_runtime_provenance_v0_1.py, is committed. It records the *currently installed* YAFS application/core/distribution/stats hashes and available Git/package versions; checks the 12+4 blind-prediction freeze -> per-cell manifest hashes -> final-WB chain; reports smoke manifest presence; and labels absent evidence as a warning. **Even a current-source fingerprint is not automatically an archival proof of the October installed code.**

## 6. Claims B1 must not make from these simulations

No empirical evidence here supports generalized claims about arbitrarily nested or cyclic compositions, repeated providers, adaptive placement/migration, decentralized agent negotiation, nonconstant QoS/energy stress, missing/failing providers, real-time runtime orchestration, model-family misspecification, or externally calibrated SLA guarantees. These can remain future-work axes, not validated contributions.

## 7. B1 report reuse recommendations

The simulator chapter should preserve:

1. Extended YAFS controller mechanism and exact API, with external dependency attribution;
2. the bounded three-provider one-controller AST compilation and four logical topologies on fixed physical substrate;
3. Gamma service dynamics, periodic workload, top-level LCQ and decided-request scoring;
4. provider-public information firewall vs calibration-only WB vs final embargoed WB;
5. method and experimental phase revisions, hash/seed/manifest chain, practical checkpoint-resume workflow;
6. both successes and limitations of smoke coverage, source pinning and validation scope.

Suggested neutral wording: **“The testbed implements native deadline-aware request composition with completion-scoped branch dependencies. Four fixed logical graph forms were evaluated against separate final white-box reference trajectories after freezing public provider disclosures and graph predictions. The experiment records subsequent method changes and an engineering-smoke sequencing deviation, and does not yet establish byte-for-byte reproducibility of the external YAFS/AICon runtime.”**

**Step 2.5 verdict:** source/contract audit complete. Historical runtime provenance and exact manifest chronology are *not certified* until the new local read-only snapshot is inspected; these are reproducibility limits, not grounds to reject correctly reconciled saved numerical tables.

### Originality and upstream-diff boundary

This audit verified the presence and operation design of PRAISE-specific APIs in the separate AICon/YAFS source, **not** a line-by-line upstream YAFS versus modified AICon diff, contribution history, patent novelty, or independent authorship. Those require separate git-baseline comparison and are not needed to report the benchmark's implemented features. Naming a capability in B1 should not implicitly claim it was invented in this project.

## Follow-up: archived runtime verification completed (2026-10-16)

See [local runtime provenance verification review](RUNTIME_PROVENANCE_VERIFICATION_REVIEW_2026-10-16.md): **94 PASS, 0 FAIL, 0 WARN, 5 INFO** from the user's archived local source/manifest audit. Twelve of twelve prediction hashes and final-WB cell backlinks matched, while the recorded complete prediction freeze at **2026-10-07 19:26:06 UTC** preceded earliest final-WB run at **19:51:50 UTC**. All four smoke manifests were present and flagged non-scientific. Current YAFS parent Git HEAD `6eabfa7` matches currently public AICon main; working tree cleanliness and historical scientific-run environment are not proven. The original engineering-smoke sequencing deviation remains. **2.5 is now closed at the stated evidence level**, not a formal code/runtime/exact-bitwise replay certification.
