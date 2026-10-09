# Phase-6 I2b lag/stride information-cost audit (2026-10-09)

## Purpose

Before defining an I2b reconstruction objective, measure whether preserving
trajectory identity across separated horizons exposes nontrivial temporal
persistence, and determine how much lag/stride sampling is needed to retain
that structure at acceptable cost.

This stage is **information-interface development only**.  It performs no
provider reconstruction and reads no graph prediction, graph WB, final WB, or
hidden provider parameter.

## Source data

Use the exact Phase-5 provider-local N=100 sigma-estimation ledgers for
P1-P4 x ProviderA-C.  This is the same provider evidence from which I2a was
derived, but trajectory identity is preserved privately for this audit.

No new provider-world simulation is acquired.

For each provider world, provider, I1 region A, trajectory j and positive
horizon H, derive cumulative compliance

    c_j(A,H).

## Rank representation

At each (provider world, provider, region, H), transform the N=100 compliance
values to tie-aware empirical midranks

    u_j(A,H) = (rank_j(A,H) - 0.5) / N.

This removes the marginal distribution already represented by I2a and isolates
relative temporal persistence.

## Sliding lag windows

For every available lag

    Delta = 5,10,...,235 s,

evaluate every valid start horizon under the full stride-5 reference:

    (u_j(A,H), u_j(A,H+Delta)).

For each window record:

- Spearman/rank persistence (Pearson correlation of the midranks), when both
  endpoints are nondegenerate;
- mean absolute rank displacement;
- mean absolute raw compliance displacement;
- fraction of trajectories whose raw compliance changes at all;
- whether the window is nondegenerate at both endpoints.

Small lags are not assumed to be useful.  The audit reports their behavior
rather than selecting a minimum lag in advance.

## Stride audit

Subsample window starts with strides

    s in {5,10,15,20,25,30,40,50} s.

For each stride, compare the resulting lag-dependent curves against the
maximal stride-5 reference.

Report:

- total temporal windows;
- total paired trajectory observations;
- cost ratio relative to stride 5;
- lag-curve MAE and maximum deviation for persistence;
- lag-curve MAE for rank displacement;
- lag-curve MAE for raw compliance displacement.

No scalar utility combining information and cost is defined at this stage.
The purpose is to expose the Pareto tradeoff and freeze a practical
lag/stride configuration only after inspecting it.

## Provenance

This is post-I1/I2a development evidence.  The audit deliberately accesses
private trajectory identity, because that identity is precisely the candidate
new I2b information.  Public I2b disclosure/reconstruction is not defined by
this audit.
