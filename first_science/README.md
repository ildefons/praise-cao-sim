# PRAISE first scientific experiment

This directory contains immutable-by-convention checkpoints for the first PRAISE `tau=(I,M)` program.

## Current next-stage source of truth

The completed I1/M0/M1/M2/M3 work is the **development pilot**. The next scientific stage is the Phase-5 prospective recoverability battery **V2**, frozen before scientific execution:

- human protocol: `PRAISE_PROSPECTIVE_RECOVERABILITY_BATTERY_PROTOCOL_V2_2026-10-02.md`
- executable configuration: `phase5/config_phase5_recoverability_battery_v2.json`
- seed/evidence registry: `phase5/config_phase5_seed_registry_v2.json`
- method-instantiation contract: `phase5/config_phase5_method_instantiation_v2.json`
- execution/artifact contract: `phase5/config_phase5_execution_contract_v2.json`
- human analysis contract: `phase5/PRAISE_PHASE5_PROSPECTIVE_ANALYSIS_CONTRACT_V2_2026-10-02.md`
- machine-readable analysis contract: `phase5/config_phase5_analysis_addendum_v2.json`

V1 Phase-5 files remain immutable provenance. V2 supersedes them before any Phase-5 scientific execution.

Historical pilot design/source of truth:

`PRAISE_I1_M0_M1_M2_M3_PILOT_DESIGN_2026-09-23.md`

Historical M3 weighted-sampling design:

`PRAISE_I1_M3_WEIGHTED_SAMPLING_PLAN_2026-09-23.md`

## Checkpoints

- `phase0/`: early mechanics/probe provenance.
- `phase1/`: frozen white-box pilot benchmark.
- `phase2/`: frozen I1 information representation and acquisition semantics.
- `phase3/`: M0/M1 contracts and pilot freeze artifacts.
- `phase4/`: completed M2/M3 development, fixed-graph sigma-regime experiment, robustness/support audits, and final pilot evidence.
- `phase5/`: prospective 4-provider-world x 4-graph recoverability battery V2.

The scientific dependency is one-way:

`pilot provenance -> Phase-5 V2 freeze -> engineering smoke -> I1 acquisition -> method-free query calibration -> frozen provider reconstructions -> blind graph prediction -> global prediction freeze -> fresh WB N=1000 -> predeclared analysis -> secondary mechanism analyses -> theory`

A frozen phase is not edited because a later result is inconvenient. Reopen only for a concrete implementation/scientific defect and version the correction explicitly.

Prediction quality, ambiguity diagnostics, applicability, Monte Carlo precision, computational cost, signed bias, false-accept/false-reject direction, topology sensitivity, and workload-shift diagnostics remain first-class outputs.

The strict PPG firewall remains in force throughout.
