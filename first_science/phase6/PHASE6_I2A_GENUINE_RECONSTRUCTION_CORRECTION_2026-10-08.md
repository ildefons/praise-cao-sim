# Phase-6 correction: genuine I2a reconstruction

**Date:** 2026-10-08

The first Phase-6 graph experiment re-ranked the seven already-frozen
I1-generated V3 candidates with the I2a Wasserstein score and then propagated
the resulting Top-3 as M2. That experiment is retained as provenance, but it
must be interpreted only as:

> I2a re-ranking of an I1-optimized candidate bank.

It is **not** a genuine I2a-M2 reconstruction because I2a did not enter the
inverse reconstruction search itself.

The corrected development experiment therefore regenerates the provider
candidate bank with I2a as the search objective.

## Genuine I2a reconstruction

For P4 / ProviderA-C independently:

1. reuse the frozen public provider model family and frozen public-derived
   parameter domains;
2. reuse the seven V3 TPE sampler seeds and the seven disjoint N=15 search
   seed banks as common-random-number controls across the I1/I2a comparison;
3. in every TPE trial, simulate the candidate provider and minimize the mean
   empirical 1D Wasserstein distance between the public I2a distribution and
   the candidate compliance distribution over every frozen (region,H>0);
4. keep the winner of each of the seven independent fits;
5. rescore all seven winners on the frozen common N=100 rescore bank using the
   same I2a loss;
6. select the three lowest-W1 candidates, deterministic candidate-id tie break;
7. assign equal provider weights 1/3 and form the complete 3^3=27 M2 joint
   support.

No graph result or graph white-box value is used anywhere in reconstruction.

## Unequal-N search loss

The public I2a target has N=100 samples per (region,H), while a TPE search trial
uses N=15 candidate trajectories. Therefore search uses the exact empirical
1D Wasserstein-1 distance for unequal empirical sample sizes,

    W1(F_100,F_15) = integral |F_100(x)-F_15(x)| dx,

computed directly from the two empirical CDFs. The common N=100 rescore uses
the same exact implementation.

## Graph development

After the genuine provider reconstruction is frozen, the same P4 / G_SEQPAR
development cell is rerun with the genuine I2a Top-3 support, using the same
frozen M2 graph seed bank and the same graph simulator semantics as Phase 5.

The earlier re-ranking-only graph result remains immutable and is not used to
select or tune the genuine I2a reconstruction.
