# Phase 5: prospective recoverability battery

This directory contains the **confirmatory battery**, separate from the completed development pilot.

## Current source of truth: V2

V2 was frozen on 2 October 2026 **before any Phase-5 scientific execution**. V1 files remain immutable provenance.

1. `../PRAISE_PROSPECTIVE_RECOVERABILITY_BATTERY_PROTOCOL_V2_2026-10-02.md` — human scientific contract.
2. `config_phase5_recoverability_battery_v2.json` — exact machine-readable battery constants.
3. `config_phase5_seed_registry_v2.json` — exact stochastic-evidence banks and algorithmic RNG controls.
4. `config_phase5_method_instantiation_v2.json` — M0/M1/M2/M3 instantiation plus the secondary common-bank scoring diagnostic.
5. `config_phase5_execution_contract_v2.json` — canonical IDs, stage order, global prediction freeze, output paths, manifests, and schemas.
6. `PRAISE_PHASE5_PROSPECTIVE_ANALYSIS_CONTRACT_V2_2026-10-02.md` and `config_phase5_analysis_addendum_v2.json` — prospective directional, mechanism, precision, and secondary-analysis commitments.

Code should read the V2 files rather than duplicate constants in scripts.

## Execution order

`engineering smoke -> I1 -> Step0 calibration -> Step0 confirmation -> provider reconstruction freeze -> blind graph predictions -> global prediction freeze -> final WB N=1000 -> primary analysis -> secondary mechanism analyses -> theory`

No final-WB trajectory may be generated or opened before the battery-level global prediction-freeze manifest covers all 16 physical cells as either prediction-frozen or `GATE_FAILED_STEP0`.

## Physical design

- Provider worlds: P1=(330M,0), P2=(330M,0.15), P3=(360M,0), P4=(360M,0.10).
- Graphs: G_PAR, G_SEQ, G_SEQPAR, G_PARSEQ.
- Workload: W0, period 0.2 s, fixed.
- Queries: 5 rho values x Easy/Mid/Stress = 15 per eligible physical cell.
- Physical cells before Step-0 exclusions: 16.
- Final WB: N=1000 per eligible physical cell.
- Primary readouts: M0, M1, M2, M3-Top1, M3-Top3, M3-Top14.
- Secondary scoring diagnostic: LHS-MSE Top1 versus matched N=100 LHS-KL Top1.

## V2 execution implementation

The first execution layer is now present:

- `phase5_runtime_v2.py`: V2 config/status validation, canonical IDs, seed-disjointness checks, SHA-256/provenance helpers, M3 rank-1 diagnostic-prefix assertion, and global prediction-freeze validation.
- `phase5_graph_ast_v2.py`: pure compiler from the four frozen graph ASTs to native PRAISE branch dependencies.
- `phase5_graph_simulator_v2.py`: generic native simulator shared by the four graph structures. Sequence is implemented with the existing PRAISE branch-dependency controller; the physical embedding remains the frozen Source/Fpre/provider/Fpost topology.
- `test_phase5_runtime_v2.py`: pure contract/AST tests.
- `run_phase5_smoke_v2.py`: mandatory non-scientific smoke using only the 99,000,000+ throwaway seed range and `phase5/smoke/`.

From the repository root, the first commands are:

```bash
cd first_science/phase5
pytest -q test_phase5_runtime_v2.py
python run_phase5_smoke_v2.py --reset
```

The smoke executes every graph twice on the same throwaway seed and requires deterministic replay equality. It also verifies contract/seed integrity, provider-interarrival extraction when supported by the installed trace schema, output hashing, the M3 rank-1 N>=100 assertion, and battery-level global prediction-freeze bookkeeping.

Smoke outputs are **not scientific evidence** and must never be copied under `results/`.

## Frozen AST-to-controller mapping

The four ASTs are compiled to these native branch dependencies:

- G_PAR: A(), B(), C().
- G_SEQ: A(), B(A), C(B).
- G_SEQPAR: A(), B(A), C(A).
- G_PARSEQ: A(), B(), C(B).

The compiler asserts these exact maps against the frozen graph IDs before execution.

## Important V2 clarifications

- Step-0 failure is **cell-level exclusion**, never query reselection or repair.
- The hidden worlds remain inside the same one-server FCFS Gamma family searched by M1-M3. Model-family misspecification is an explicit follow-up axis, not part of this battery.
- M3 Top14 remains fixed at K=14 and B=1400. Top1/Top3 are nested readouts with unmatched effective graph-MC budgets.
- Top1/Top3/Top14 use one plug-in weighted Bernoulli MC variance family, plus the conservative worst-case bound.
- The topology mechanism has directional predeclared contrasts: SEQ-minus-PAR and the P2/P4 versus P1/P3 contrast.
- Passive diagnostics include SLA violation component, parallel controlling child when available, and provider interarrival statistics.
- Hidden-truth I1 scoring, M3 support-warning analysis, and the public-sigma card bootstrap are registered now but run only after the primary battery is frozen.
- The strict PPG firewall remains in force.
- A scientific result is never a reason to repair a frozen method.

Every executable scientific stage must emit manifests containing V2 config hashes, including the analysis-contract SHA-256, exact seeds, code commit, input/output hashes, and completion status.
