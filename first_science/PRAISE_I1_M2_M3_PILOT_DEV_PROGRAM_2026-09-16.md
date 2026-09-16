# PRAISE pilot development program: I1-M2-M3

**Status:** active development roadmap inside the current pilot program.  
**Date:** 16 September 2026.

This document is the implementation/development companion to `PRAISE_I1_M0_M1_M2_M3_PILOT_DESIGN_2026-09-16.md`. It does not redefine frozen Phase 1, I1, M0, or M1-v2.

## 1. Development objective

Continue the pilot while holding provider disclosure fixed at frozen I1:

`(I1,M0) [frozen] -> (I1,M1) [frozen] -> (I1,M2) -> (I1,M3)`.

The near-term purpose is not to complete the final tau battery. It is to learn which integration mechanisms are worth carrying forward and to establish a standard evaluation/cost protocol before the experiment grows.

## 2. M2 development sequence

### M2-A: recover the local inverse landscape

Inputs:

- frozen public I1 cards;
- existing M1-v2 search-trial tables for A/B/C;
- M1 confirmation/replay diagnostics;
- no graph-level WB information for candidate selection.

Tasks:

1. define a public-I1-only compatibility score relative to local reconstruction loss;
2. identify parameter-diverse candidates with comparable local fit;
3. quantify parameter-space spread/ridges and local-prediction similarity;
4. write a deterministic candidate-selection manifest before graph composition.

Output:

- per-provider compatible candidate set;
- provenance and reconstruction metrics;
- frozen candidate-selection rule for the identifiability diagnostic.

### M2-B: graph identifiability diagnostic

Compose multiple compatible A/B/C candidate combinations through the native simulator.

Primary question:

`Do local-I1-equivalent lifts imply materially different graph sigma predictions?`

Do not use graph WB to choose combinations. Use either a deterministic factorial/subsample design or a predeclared random-combination seed scheme.

Record:

- graph sigma per combination;
- between-combination spread;
- decomposition by provider candidate where possible;
- formal and empirical computational cost.

Decision:

- large spread -> inverse non-identifiability is a first-order issue;
- small spread with common saturation -> current latent surrogate family is insufficient.

### M2-C: ensemble predictor

If non-identifiability is supported, define the smallest ambiguity-preserving ensemble rule.

Candidate outputs:

- ensemble mean sigma curve;
- median sigma curve;
- central prediction intervals/quantiles;
- ensemble dispersion;
- calibration/coverage diagnostics against fresh WB conditions.

The ensemble weighting rule must be derived from public I1 reconstruction information only.

### M2-D: computational-budget sweep

Before fresh graph WB evaluation, lock a small set of M2 compute budgets. The budget variable may be ensemble size, posterior sample count, graph trajectories per member, or another directly countable quantity.

For each budget record:

- prediction metrics;
- uncertainty/coverage metrics;
- formal simulation counts;
- wall-clock, CPU, and memory cost.

This creates the first explicit accuracy-cost frontier for the tau battery.

## 3. M3 development sequence

M3 begins only after the static M2 mechanism is understood.

M3 remains within the I1 pilot. It should use the same information schema, potentially delivered as successive I1-compatible snapshots, not a richer latent-state disclosure.

### M3-A: dynamic scenario contract

Define one controlled nonstationary provider/workload scenario and a public update schedule. Lock the hidden physical change process separately from the public I1 update process.

### M3-B: incremental integration

Implement an updateable M2-derived state so that new public I1 information can modify the compositor belief without rebuilding every component from scratch.

Measure:

- update latency;
- number/fraction of ensemble components recomputed;
- time to recover predictive accuracy after change;
- transient sigma error;
- update computational cost.

### M3-C: dynamic budget frontier

Vary a predeclared update budget, for example update frequency or number of refreshed ensemble members, and estimate the trade-off between adaptation quality and computational cost.

## 4. Standard tau evaluation record

Every new scientific tau run should produce one machine-readable evaluation manifest with these sections.

### Scientific identity

- `information_representation`;
- `integration_method`;
- graph/topology id;
- workload id;
- rho support;
- horizon support;
- git commit;
- contract hashes;
- seed banks.

### Prediction quality

At minimum:

- sigma MAE;
- sigma RMSE;
- signed bias;
- maximum absolute error.

For ensemble/interval methods add:

- interval width;
- empirical coverage;
- calibration error or another predeclared interval-quality statistic.

### Admissibility-region quality

When a method predicts/induces a region:

- Jaccard/J_A;
- componentwise boundary error as appropriate.

Always retain same-region diagnostics when needed to separate probability-integration error from region mismatch.

### Formal computational cost

At minimum:

- optimizer evaluations;
- local simulation trajectories;
- graph simulation trajectories;
- ensemble members/samples;
- graph-member combinations;
- processed requests/events when available;
- dynamic updates and reused/recomputed components for M3.

Also report conceptual categories:

- `C_build`;
- `C_query`;
- `C_update` for dynamic methods;
- retained model/ensemble state size.

### Empirical computational cost

For new scientific runs prefer `/usr/bin/time -v` and store:

- elapsed wall time;
- user CPU time;
- system CPU time;
- peak resident set size;
- host/hardware identifier;
- relevant runtime/software versions.

Do not compare wall times from different machines without identifying the hardware context.

## 5. Implementation conventions

- Keep M2/M3 code separate from frozen M1 code paths where practical.
- Reuse stable simulator/accounting utilities rather than copying semantics.
- Do not mutate frozen M1 result files to create M2 ensembles.
- Store selected M2 candidate sets and ensemble rules in explicit contracts/manifests.
- Any graph-WB file must be opened only after the prediction artifact that it evaluates has been materialized.
- Preserve raw enough intermediate artifacts to reproduce sigma and cost calculations, while respecting the provider-information firewall.

## 6. Suggested directory progression

The exact directory names are not frozen, but a clean progression is:

- `phase3/`: frozen M0/M1 pilot baselines and their provenance;
- `phase4/`: I1-M2 identifiability and ensemble composition;
- `phase5/`: I1-M3 dynamic integration;
- later phase(s): information-axis experiments such as latent-state-enhanced sigma, I2, I3.

Do not create later phases merely to satisfy this naming convention. Create them when their contracts are ready.

## 7. Current priority queue

1. Archive/freeze current M0/M1 evidence and cost information that is already trustworthy.
2. Build M2-A from existing M1-v2 trial landscapes, without rerunning expensive searches unless a concrete data gap appears.
3. Run the graph identifiability diagnostic with predeclared combinations and cost instrumentation.
4. Decide ensemble versus richer latent-family M2 based on that diagnostic.
5. Freeze the first M2 definition and evaluate it on a fresh graph/WB condition.
6. Only then specify the first dynamic M3 scenario.
7. Revisit the information axis after the I1 method sweep, including the privacy-preserving latent-state sigma idea.

## 8. Pilot success criterion

The pilot succeeds even if no single method is universally superior. The useful outcome is a defensible map of the trade-offs among:

- provider disclosure;
- predictive reliability;
- admissibility-region fidelity;
- ambiguity/uncertainty handling;
- computational build/query/update cost.

The pilot should tell us which tau cells deserve the time required for the later, broader PRAISE battery.
