# Phase-6 I2b public paired-distribution representation v1 (2026-10-09)

## Purpose

Materialize the first public I2b information interface after the temporal sampling has been frozen.

I2b-v1 is defined as the I2a marginal compliance distributions plus anonymous empirical paired distributions across selected temporal windows. No new provider-world simulation is acquired.

## Frozen temporal sampling

The authoritative sampling contract is `config_phase6_i2b_temporal_sampling_v1.json`:

- stride s = 10 s;
- lags D = {20, 30, 40, 50, 75, 100, 150, 200} s;
- canonical starts H = 5 + 10k, restricted by H + Delta <= 240 s;
- five frozen I1 regions per provider.

## Public empirical pair measure

For provider p, region A, start H and lag Delta, let

    c_j(A,H)

be cumulative SLA compliance for private trajectory j. The public temporal object is the empirical bivariate measure

    P_hat^(2)_{p,A,H,Delta}
      = (1/N) sum_j delta_( c_j(A,H), c_j(A,H+Delta) ),

with N = 100.

The CSV therefore contains 100 anonymous pairs per temporal window:

    (compliance_start, compliance_end).

Each row has sample_mass = 1/100. Pair rows are deterministically sorted lexicographically within each window and receive an `anonymous_pair_index` only for stable serialization.

## Linkage rule

The same private trajectory is used to form the two values inside one pair. This within-window pairing is the new I2b information.

After a window is formed, the private trajectory identifier is removed. No identifier, seed, request identifier, or stable cross-window sample identifier is included in the public artifact. The `anonymous_pair_index` is recomputed independently in every window and must not be interpreted as correspondence across windows.

This is an information-interface rule, not a claim of formal cryptographic privacy.

## Marginal component

I2b includes the I2a empirical marginal distribution at every frozen region and positive horizon. A self-contained copy is materialized alongside the temporal-pair file using the established I2a publicization rule: sort compliance values independently within each (region,H), with no trajectory identity.

## Expected cardinalities per provider

- I2a marginal rows: 5 regions x 48 horizons x 100 samples = 24,000.
- Temporal windows per region: 126.
- Temporal windows per provider: 630.
- Temporal pair rows per provider: 630 x 100 = 63,000.

The per-region window counts by lag are:

- 20 s: 22
- 30 s: 21
- 40 s: 20
- 50 s: 19
- 75 s: 17
- 100 s: 14
- 150 s: 9
- 200 s: 4

## Firewall

This construction may read the private Phase-5 provider trajectory ledgers because trajectory identity is exactly the new information being publicized in anonymized pair form. It must not read graph predictions, graph white-box results, final white-box results, or hidden provider parameters.

## Immutability

These publicization semantics are frozen before an I2b reconstruction loss is selected or evaluated. Later loss choices may consume this representation but may not alter its lag set, stride, pairing semantics, or public linkage rule.
