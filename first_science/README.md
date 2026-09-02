# PRAISE first scientific experiment

This directory contains immutable-by-convention implementation checkpoints for the first PRAISE I1-M0/M1 experiment.

- `phase0/`: frozen white-box provider observation/survival kernel.
- `phase1/`: reference-regime construction and admissibility-region calibration. It starts in `IN_DEVELOPMENT` state and must not execute a scientific search until its pre-search configuration validates as complete.

A frozen phase is not edited to implement the next phase. Later phases consume the scientific outputs/semantics of earlier checkpoints without silently redefining them.
