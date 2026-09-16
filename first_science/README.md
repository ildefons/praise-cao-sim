# PRAISE first scientific experiment

This directory contains immutable-by-convention implementation checkpoints for the first PRAISE `tau=(I,M)` experiment.

Current design/development source of truth:

`PRAISE_I1_M0_M1_M2_DESIGN_2026-09-16.md`

Current frozen state:

- `phase0/`: early mechanics/probe checkpoint retained for provenance.
- `phase1/`: **frozen white-box benchmark**. Physical benchmark construction, admissibility-region calibration, and untouched N=100 confirmation.
- `phase2/`: **frozen I1 information representation**. Rho-conditioned provider-local admissibility regions and sigma surfaces built from independent evidence.
- `phase3/`: **frozen M0 and frozen M1-v2 pilot baselines** over the same public I1. M0 is direct analytic composition. M1-v2 is public-I1-only inverse lifting to native provider surrogates followed by native graph composition.
- M2 is the next method-development stage. It must consume the same frozen I1 initially and must not repair or retune M1.

The dependency direction is one-way:

`phase1 WB [FROZEN] -> phase2 I1 [FROZEN] -> phase3 M0/M1 [FROZEN] -> M2 development -> fresh validation`

A frozen phase is not edited merely because a later result is inconvenient. Reopen only for a concrete implementation or scientific defect. Later methods may consume stable outputs/utilities from earlier checkpoints without silently redefining them.

The strict PPG firewall remains in force throughout this experiment.
