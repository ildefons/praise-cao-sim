# PRAISE first scientific experiment

This directory contains immutable-by-convention implementation checkpoints for the first PRAISE `tau=(I,M)` **pilot program**. The pilot is intended to learn which information and integration mechanisms deserve to enter the later, broader tau battery. It is not yet the final battery.

Current design source of truth:

`PRAISE_I1_M0_M1_M2_M3_PILOT_DESIGN_2026-09-16.md`

Current development roadmap:

`PRAISE_I1_M2_M3_PILOT_DEV_PROGRAM_2026-09-16.md`

Current frozen state:

- `phase0/`: early mechanics/probe checkpoint retained for provenance.
- `phase1/`: **frozen white-box pilot benchmark**. Physical benchmark construction, admissibility-region calibration, and untouched N=100 confirmation.
- `phase2/`: **frozen I1 information representation**. Rho-conditioned provider-local admissibility regions and sigma surfaces built from independent evidence.
- `phase3/`: **frozen M0 and frozen M1-v2 pilot baselines** over the same public I1. M0 is direct analytic composition. M1-v2 is public-I1-only inverse lifting to one native provider surrogate per provider followed by native graph composition.
- `M2`: next short-term pilot stage. Preserve inverse ambiguity through an I1-compatible ensemble if the identifiability gate supports it; otherwise test the minimum richer latent process family without changing I1.
- `M3`: mid-term pilot stage. Dynamic/incremental integration over the same I1 schema, defined only after M2 is understood.

The immediate method-axis dependency direction is one-way:

`phase1 WB [FROZEN] -> phase2 I1 [FROZEN] -> phase3 M0/M1 [FROZEN] -> I1-M2 -> I1-M3 -> later information-axis experiments`

From M2 onward, every scientific tau run should record prediction quality, admissibility-region quality where applicable, and formal plus empirical computational cost. New timed runs should preferably capture wall time, CPU time, and peak RSS in addition to simulator/evaluation counts.

A frozen phase is not edited merely because a later result is inconvenient. Reopen only for a concrete implementation or scientific defect. Later methods may consume stable outputs/utilities from earlier checkpoints without silently redefining them.

The strict PPG firewall remains in force throughout the pilot.
