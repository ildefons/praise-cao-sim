# M2 validation reopening for calibrated G2

**Date:** 22 September 2026  
**Status:** REOPENED_FOR_CALIBRATED_G2_VALIDATION  
**Scope:** the frozen M2 method remains unchanged; only the scientific validation chapter is reopened.

## Reason for reopening

The predeclared G1 prospective experiment was executed correctly and remains valid evidence. Its blind prediction freeze preceded white-box generation, the white-box seed bank was independent, and the predeclared M2-vs-M1 criteria were evaluated without retuning.

However, inspection of the resulting sigma curves shows that G1 is a poor final validation condition for the intended dependable-service regime. The G1 white-box survival curves enter a strong floor regime: for several rho values, sigma_G falls rapidly toward zero over the horizon.

This makes G1 scientifically useful as a **prospective stress test**, but not as the final representative validation of the M2 mechanism in the operating regime targeted by PRAISE.

The issue is experimental-condition calibration, not a protocol violation. G1 changed the public network embedding while carrying forward the induced admissibility regions. Those regions were not Step-0 calibrated for the new G1 condition, so the resulting WB survival surface is strongly degenerate.

## G1 evidence retained

Nothing from G1 is discarded.

G1 remains a prospective stress-test result:

- M1 MAE: 0.765469
- M2 MAE: 0.617345
- M2 beats M1 on MAE and RMSE
- M2 beats M1 in 5/5 rho slices
- M0 MAE: 0.202037
- M2 finite-portfolio range coverage: 0.114286
- 0.885714 of WB points lie below the M2 range

Interpretation: under a severe out-of-support condition, preserving inverse ambiguity helps relative to M1, but the small frozen M2 portfolio does not span the required lower-survival behavior.

## What remains frozen

The following are not reopened:

- public I1 cards;
- M0 semantics;
- M1 parameters;
- M2 provider portfolios;
- the 27-member Cartesian product;
- equal 1/27 M2 weights;
- G0 and G1 results;
- all historical prediction and WB artifacts.

No G1-driven M2 repair is permitted.

## What is reopened

Only the final M2 validation conclusion is reopened.

A new prospective condition, G2, must be designed with an explicit **Step-0 calibration stage** so that the white-box survival surface is nondegenerate and representative of the intended dependable-service regime before M0/M1/M2 are compared.

The calibration procedure itself must be frozen before using G2 calibration evidence. Calibration data may be used only to choose the admissibility-region battery according to the predeclared rule. It may not be used to modify M1/M2, select M2 members, alter M2 weights, or optimize prediction error.

After calibration, the selected G2 admissibility regions must be frozen. M0/M1/M2 predictions must then be materialized and hashed before any fresh G2 evaluation white-box trajectories are generated or inspected.

## Desired validation regime

The purpose is to avoid both floor and ceiling experiments.

The exact numerical calibration rule and target band must be specified in the G2 contract before calibration is run. The scientific intent is a high-survival, nondegenerate regime representative of dependable services, with sigma_G mostly near the upper reliability range while retaining enough variation over horizon and rho to discriminate methods.

No numerical target is frozen in this reopening note. That belongs to the next G2 design contract.

## Current status

`M2_METHOD_STATUS = FROZEN_UNCHANGED`

`M2_VALIDATION_STATUS = REOPENED_FOR_CALIBRATED_G2`

`G1_EVIDENCE_ROLE = PROSPECTIVE_STRESS_TEST`

`FINAL_M2_VALIDATION = PENDING_G2`

`M3_START = DEFERRED_UNTIL_G2_CLOSES_M2`
