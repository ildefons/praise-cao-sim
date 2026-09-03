# PRAISE first scientific experiment

This directory contains immutable-by-convention implementation checkpoints for the first PRAISE I1-M0/M1 experiment.

- `phase0/`: early frozen mechanics/probe checkpoint retained for provenance.
- `phase1/`: **frozen Step-0 white-box benchmark**. It contains the physical benchmark construction, SLA-native admissibility-region selection, shortlist stability calibration, and final untouched N=100 confirmation. New information technologies and composition methods must not be implemented here.
- `phase2/`: **Step 1 information + composition workspace**. It starts with the minimal provider information technology `I1`, followed by `(I1,M0)` and `(I1,M1)` experiments against the fixed Phase-1 white-box target.

The dependency direction is intentionally one-way:

`phase1 frozen benchmark -> phase2 I1/M0/M1`

A frozen phase is not edited to implement the next phase. Later phases may consume scientific outputs and stable accounting utilities from earlier checkpoints without silently redefining them.
