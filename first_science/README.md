# PRAISE first scientific experiment

This directory contains immutable-by-convention implementation checkpoints for the first PRAISE tau=(I,M) experiment.

- `phase0/`: early frozen mechanics/probe checkpoint retained for provenance.
- `phase1/`: **frozen Step-0 white-box benchmark**. Physical benchmark construction, SLA-native admissibility-region selection, shortlist stability calibration, and final untouched N=100 confirmation.
- `phase2/`: **frozen I1 information technology**. Provider-local SLA-compliance surface contract, fresh private provider-acquisition corpus, deterministic exact-card materialization interface, and validated corpus fingerprints.
- `phase3/`: **(I1,M0)** analytic/topology-aware composition. Begins from the frozen Phase-2 I1 and must not alter it.
- `phase4/`: **(I1,M1)** minimum-information lifting plus native composed simulation. Begins from the same frozen I1.
- `phase5/`: locked comparative tau analysis, if/when needed.

The intended dependency direction is one-way:

`phase1 white-box target -> phase2 I1 [FROZEN] -> phase3 (I1,M0) / phase4 (I1,M1) -> phase5 comparison`

A frozen phase is not edited to implement the next phase. Later phases may consume scientific outputs and stable accounting utilities from earlier checkpoints without silently redefining them.
