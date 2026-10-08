# Phase-6 matched I1-strong control protocol (2026-10-08)

## Purpose

This control isolates the effect of the richer I2a information from the effect
of the stronger reconstruction search used by I2AFS.

The matched control keeps the reconstruction architecture, parameter domain,
simulation budgets, random-number banks, shortlist size, M2 support size, and
graph-propagation budget identical to the frozen I2AFS experiment.  The only
scientific change is the provider-level fitting information/loss:

- **I2AFS:** full-spectrum I2a marginal survival loss.
- **I1-strong:** original complete public-I1 sigma-surface loss.

## Frozen provider-level objective

For a candidate provider surrogate theta, I1-strong minimizes the original I1
full-surface mean squared error over every public I1 region/query/horizon point
with H>0, exactly as implemented by the existing Phase-3
`calculate_full_surface_loss` / `_simulate_and_score` path.

No I2a distribution, hidden truth, graph result, graph WB, final WB, or private
I1 ledger is read by the reconstruction.

## Exact search match to I2AFS

For each P4 provider:

1. Same frozen public-derived parameter domain.
2. Same 256 total trials.
3. Same first 64 deterministic scrambled-Sobol initial points.
4. Same remaining 192 TPE-adaptive trials.
5. Same Sobol seed: 420001.
6. Same provider TPE seeds:
   - ProviderA: 420101
   - ProviderB: 420103
   - ProviderC: 420107
7. Same N=25 search CRN bank: 60000..60024.
8. Same top-24 search shortlist.
9. Same fresh common N=100 rescore bank: 60100..60199.
10. Same top-3 provider support, equal weight 1/3.
11. Same 27 Cartesian M2 joint models, equal weight 1/27.

Thus the initial space-filling proposals are exactly matched to I2AFS and the
adaptive search has the same sampler seeds and budget.  TPE proposals may
diverge after the Sobol block because the objective evidence differs; that is
part of the intended information/loss comparison.

## Graph control

After provider support is frozen, propagate I1-strong M2 through the same
P4/G_SEQPAR graph using the exact same Phase-5 M1/M2 common graph seed bank
(N=100 per joint model, 27 joint models, 2700 trajectories).

The final comparison is therefore:

[
  I1	ext{-strong M2} quad 	ext{vs} quad I2a	ext{-full-spectrum M2}
]

with reconstruction and graph budgets matched.

## Development status

This is post-I1 method-development evidence, not prospective Phase-5 evidence.
No tuning is allowed after observing the matched-control provider or graph
results.  Any further change must be a new explicitly labelled development
version.
