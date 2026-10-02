# Phase 5: prospective recoverability battery

This directory contains the **new confirmatory battery**, separate from the completed development pilot.

## Source-of-truth order

1. `../PRAISE_PROSPECTIVE_RECOVERABILITY_BATTERY_PROTOCOL_2026-10-02.md` — human scientific contract.
2. `config_phase5_recoverability_battery_v1.json` — exact machine-readable battery constants.
3. `config_phase5_seed_registry_v1.json` — exact stochastic-evidence banks and algorithmic RNG controls.
4. `config_phase5_method_instantiation_v1.json` — how M0/M1/M2/M3 are instantiated on new provider worlds without graph-WB tuning.
5. `config_phase5_execution_contract_v1.json` — canonical IDs, stage order, output paths, manifests, and table schemas.
6. `PRAISE_PHASE5_PROSPECTIVE_ANALYSIS_ADDENDUM_2026-10-02.md` and `config_phase5_analysis_addendum_v1.json` — analysis-only commitments for directional bias and topology sensitivity. They do not change the frozen scientific design.

Code should read these files rather than duplicate battery constants in scripts.

## Execution order

`I1 -> Step0 calibration -> Step0 confirmation -> provider reconstruction freeze -> blind graph predictions -> prediction hash freeze -> final WB N=200 -> analysis -> theory`

No final-WB result may alter a method, provider world, graph, query, weighting rule, support rank count, or simulation budget.

## New physical design

- Provider worlds: P1=(330M,0), P2=(330M,0.15), P3=(360M,0), P4=(360M,0.10).
- Graphs: G_PAR, G_SEQ, G_SEQPAR, G_PARSEQ.
- Workload: W0, period 0.2 s, fixed.
- Queries: 5 rho values x Easy/Mid/Stress = 15 per physical cell.
- Physical cells: 16.
- Total query cells: 240.
- Final WB: N=200 per physical cell.
- Methods/readouts: M0, M1, M2, M3-Top1, M3-Top3, M3-Top14.

## Implementation guardrails

- Preserve existing sigma semantics.
- Preserve the strict PPG firewall.
- Do not special-case provider identity using hidden truth.
- Any search-bound expansion must be triggered only by public-I1 local evidence and follow the Phase-5 method contract.
- M3 Top14 is a **fixed rank count** in this battery; retained mass is reported, not used to change K.
- Top1 and Top3 are nested readouts from the Top14 member ledgers, not separate graph runs.
- A scientific result is never a reason to repair a frozen method.
- The analysis addendum predeclares a reference-only trajectory-cluster bootstrap for signed bias and a topology-sensitivity analysis. Neither can feed back into methods.
- SLA-component violation flags should be derived from the existing top-level L/C/Q ledger. Parallel-join controlling-child logging is passive and non-blocking; if it cannot be exposed without changing simulator semantics, record NOT_AVAILABLE.

Every executable stage must emit a manifest containing config hashes, input hashes, code commit, exact seeds, output hashes, and completion status.
