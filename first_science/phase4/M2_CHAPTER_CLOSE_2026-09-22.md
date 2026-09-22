# M2 chapter close

> **REOPENING NOTICE, 22 September 2026:** This closure decision has been superseded by `M2_REOPENING_FOR_G2_2026-09-22.md`. The M2 method itself remains frozen, but final validation is reopened because G1 is retained as a prospective stress test rather than the final dependable-regime validation. The historical G1 results below are preserved unchanged for provenance.

**Date:** 22 September 2026  
**Status:** SUPERSEDED_BY_G2_VALIDATION_REOPENING  
**Method:** frozen 27-member equal-weight joint ensemble over the already-frozen three-member provider portfolios.

## Scientific question

Does preserving a small amount of inverse ambiguity from public I1 improve graph-level reliability prediction relative to the single reconstructed latent process used by M1?

M2 was frozen before the prospective G1 white-box was generated. No G1 result was used to select members, alter parameters, change weights, redesign the graph, or change the success criteria.

## G0 retrospective diagnostic

On the already-seen G0 condition, the frozen M2 equal-weight mean improved strongly over M1:

- M0 MAE: 0.439842
- M1 MAE: 0.184776
- M2 MAE: 0.077758
- M2 RMSE: 0.094818
- M2 bias: +0.038671
- M2 finite-portfolio range coverage: 0.730612

This result is retrospective diagnostic evidence only because G0 white-box behavior had already been inspected during M2 development.

## G1 prospective validation

G1 was predeclared as an untouched asymmetric public network embedding while keeping the logical ParAll graph, provider workload, provider cards, M1 parameters, M2 candidate set, and M2 weights unchanged.

Blind prediction seeds: 30000..30099.  
Independent white-box seeds: 31000..31099.

The predeclared primary criterion was:

`M2 whole-surface MAE < M1 whole-surface MAE`.

The confirmatory criteria were:

- `M2 whole-surface RMSE < M1 whole-surface RMSE`;
- M2 MAE lower than M1 MAE in at least 3 of 5 frozen rho slices.

### Prospective result

All predeclared M2-vs-M1 criteria passed:

- M1 MAE: 0.765469
- M2 MAE: 0.617345
- improvement: 0.148124 absolute MAE
- M1 RMSE: 0.804938
- M2 RMSE: 0.672633
- M2 MAE lower than M1 in 5/5 rho slices

Therefore the prospective evidence supports the narrow claim that the frozen ambiguity-preserving M2 ensemble improves on the frozen single-latent M1 predictor under this untouched G1 condition.

## Critical limitation exposed by G1

The prospective pass is not evidence that M2 is an accurate graph-level predictor.

Absolute G1 performance remains poor:

- M0 MAE: 0.202037
- M2 MAE: 0.617345
- M1 MAE: 0.765469

M0 therefore substantially outperformed both reconstructed-process methods on G1.

M2 remained strongly optimistic:

- M2 bias: +0.617164
- M2 max absolute error: 0.974074

The finite-portfolio ambiguity range also failed to contain the new white-box behavior:

- overall coverage: 0.114286
- mean range width: 0.339224
- fraction of WB below the range: 0.885714
- fraction of WB above the range: 0.0

Coverage increased with stricter rho but remained low:

- rho=0.95: 0.020408
- rho=0.975: 0.040816
- rho=0.983333: 0.061224
- rho=0.99: 0.122449
- rho=0.995: 0.326531

Thus the frozen 27-member portfolio does not span the relevant lower-survival behavior under G1. The problem is not merely central averaging; the support represented by M2 is itself too narrow in the direction required by the prospective condition.

## Interpretation

The M2 result has two distinct conclusions.

First, preserving inverse ambiguity is useful. Relative to M1, M2 reduced error prospectively and consistently across all five rho slices. This supports the mechanism-level claim that collapsing I1 to one latent reconstruction discards compositionally relevant uncertainty.

Second, a small diversity-selected portfolio is insufficient as a general solution. G1 shows severe transfer failure in absolute terms and weak ambiguity-range coverage. Equal weighting over three deliberately diverse representatives per provider does not create a calibrated or representative distribution over the full I1-compatible latent space.

The fact that M0 outperformed both M1 and M2 on G1 is scientifically important. It shows that adding a reconstructed process model is not automatically beneficial when the inverse reconstruction is badly misspecified relative to the new composition condition. A simple public-card composition baseline can be more robust than a richer but poorly identified latent model.

## Frozen claim boundary

Supported:

> Under fixed public I1, retaining a small diverse set of compatible latent reconstructions can prospectively improve graph-level sigma prediction relative to collapsing the inverse problem to a single reconstruction.

Not supported:

- M2 is an accurate general graph-level predictor;
- the equal-weight M2 mean is probabilistically calibrated;
- the 27-member min-max range is a valid confidence or credible interval;
- the frozen M2 portfolio spans all materially compatible latent behavior;
- M2 dominates M0 across composition conditions.

## Closure decision

M2 is permanently frozen and closed.

No G1-driven member addition, deletion, retuning, reweighting, local-search repair, graph-specific calibration, or low-rho repair is permitted inside M2.

The next methodological stage belongs to M3.

The main question carried forward is no longer whether inverse ambiguity matters. G1 provides prospective evidence that it does. The next question is how to represent the compatible latent population more faithfully so that both central mass and support transfer across composition conditions.

A future M3 weighting rule must not simply turn local I1 reconstruction error into probability. Any probabilistic weighting requires an explicit generative/noise or prior model. A conservative starting point is therefore a large predeclared sampled compatible population with transparent sampling measure and equal weighting after acceptance, before considering justified non-uniform weights.

## Final status

`M2_STATUS = CLOSED_AFTER_PROSPECTIVE_G1_VALIDATION`

`PRIMARY_G1_M2_VS_M1 = PASS`

`ABSOLUTE_G1_ACCURACY = POOR`

`M2_RANGE_GENERALIZATION = POOR`

`M0_G1_REFERENCE = SUBSTANTIALLY_BETTER_THAN_M1_AND_M2`

`NEXT_METHOD = M3`
