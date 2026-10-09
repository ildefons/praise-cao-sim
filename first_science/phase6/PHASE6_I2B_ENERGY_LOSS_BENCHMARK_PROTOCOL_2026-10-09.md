# Phase-6 I2b empirical energy-loss benchmark v1 (2026-10-09)

## Purpose

Before launching a new inverse reconstruction, validate one parameter-free bivariate loss against the already frozen public I2b-v1 representation and measure its scoring cost.

This benchmark does not perform provider reconstruction and does not read graph predictions, graph white-box outcomes, final white-box outcomes, or hidden provider parameters.

## Candidate loss

For one frozen temporal window, compare the observed and candidate empirical pair distributions in the two-dimensional compliance plane with the empirical energy V-statistic

    E(P,Q) = 2 E||X-Y|| - E||X-X'|| - E||Y-Y'||,

where ||.|| is Euclidean distance on (compliance_start, compliance_end).

The target-target term is precomputed once for each public window. No kernel bandwidth, binning resolution, temporal weighting coefficient, or marginal-vs-dependence coefficient is introduced.

## Aggregation

For each selected lag Delta, average the window losses equally over all five SLA regions and all valid frozen start horizons. Then average the eight lag means equally.

This exactly follows the frozen temporal-sampling contract:

- s = 10 s
- D = {20,30,40,50,75,100,150,200} s
- equal lag weighting
- equal within-lag window weighting.

## Dependence-sensitivity diagnostic

For each public temporal window, construct deterministic endpoint-shuffled controls that preserve the start and end marginals exactly but destroy the observed within-window pairing.

Use three deterministic shuffle repetitions with base seed 620001. Seeds are derived from SHA-256 of the provider/window key and repetition, so results are independent of process scheduling.

The benchmark verifies:

1. self-distance is numerically zero;
2. endpoint shuffling preserves both one-dimensional marginals exactly;
3. the bivariate energy loss is positive when temporal pairing is destroyed;
4. lag-level energy responses are reported rather than tuned.

The shuffled controls are diagnostics only. They are not candidate provider models and are not used to choose lags, stride, graph cells, or provider parameters.

## Computational benchmark

Measure pure scoring time after the public target has been prepared for:

- candidate N=25, matching the planned search-stage trajectory budget;
- candidate N=100, matching the planned shortlist-rescore budget.

For timing only, deterministic shuffled candidates are used. Report median provider score time and the implied scoring-only cost of a 256-trial search plus 24 N=100 rescored candidates:

    256 * t_N25 + 24 * t_N100.

This excludes simulation time and is therefore a conservative way to determine whether loss arithmetic is negligible or material relative to provider simulation.

## Decision rule

If algebraic invariants pass and the loss responds to destroyed pairing while scoring cost remains practical, the empirical energy statistic may be frozen as the I2b-v1 reconstruction loss in a separate subsequent freeze.

No reconstruction or graph result is allowed to alter this benchmark.

## Upload convenience

The runner creates one ZIP bundle containing the benchmark summary, lag-level diagnostics, and manifest so that any follow-up requiring multiple artifacts needs only one upload.
