# Phase 6: I2a marginal-distribution development protocol

**Status:** frozen before any Phase-6 I2a outcome is inspected.  
**Date:** 2026-10-08  
**Role:** information-axis method development after the frozen Phase-5 I1 battery.

## 1. Motivation

Phase 5 established that, with provider disclosure fixed at I1, propagating ambiguity among compatible provider reconstructions improves aggregate graph prediction and SLA decisions, but substantial residual error remains in several nontrivial Mid/Stress conditions.

The Phase-6 question is therefore not whether to invent another graph-composition method first. It is:

> What minimal additional provider-side behavioral information is needed to make composition more identifiable without revealing provider internals?

M2 and M3 from Phase 5 are retained as the method baselines. Phase 6 changes the information interface.

## 2. I2a-full

For each provider-local admissibility region A_i and horizon H, let c_i(A_i,H) be the cumulative fraction of provider-local decided requests that satisfy the region.

I1 exposes a sparse set of upper-tail probabilities

    sigma_i(A_i,H;rho) = P(c_i(A_i,H) >= rho)

for the frozen rho support.

I2a-full instead exposes the complete empirical marginal distribution

    F_i,A,H(x) = P(c_i(A_i,H) <= x)

at every frozen region and horizon.

The Phase-6 implementation represents this empirical CDF by the independently sorted N=100 compliance samples at each (region,H).

### Privacy / abstraction rule

I2a-full exposes only marginal behavioral distributions.

It does **not** expose:
- provider queue structure;
- hardware or service discipline;
- hidden generating parameters;
- internal state variables;
- raw request traces;
- trajectory identifiers;
- correspondence of a trajectory across different horizons.

The N=100 compliance values are sorted independently at every (region,H), deliberately destroying temporal identity. Thus I2a contains marginal severity information but no persistence/memory information. Temporal dependence belongs to a later I2b investigation.

## 3. Evidence reuse

The provider-side target distribution is materialized from the already frozen Phase-5 I1 sigma-estimation corpus:

    phase5/results/01_i1/{world}/private/sigma/{provider}/provider_request_ledgers.csv

No new provider-world trajectory is acquired. This isolates the information-representation change I1 -> I2a from a change in acquisition budget.

The frozen five rho-conditioned I1 regions and frozen horizon grid are reused unchanged.

Candidate reconstructions are the same seven provider surrogate candidates frozen in Phase 5 V3b. No candidate family expansion or parameter refitting is allowed in the first I2a audit.

Candidate I2a behavior is re-simulated on the already frozen V3 common N=100 rescore seed bank only to recover trajectory-level compliance fractions that were not stored by the I1 surface files.

## 4. I2a discrepancy

For candidate theta and every frozen (region,H), compare the N=100 target and candidate compliance samples with one-dimensional Wasserstein-1 distance.

Because both empirical distributions contain exactly 100 samples,

    W1 = mean_k | sort(c_public)[k] - sort(c_theta)[k] |.

The provider-level I2a score is the unweighted arithmetic mean of W1 over all frozen regions and all H>0.

H=0 is excluded because its zero-decision convention is structurally degenerate and adds no discrimination.

No graph-level result, graph WB, Step-0 WB outcome, or final WB value may enter this score.

## 5. First Phase-6 stage: provider-only ambiguity audit

The first executable stage stops at provider level.

For every P1-P4 x ProviderA-C:
1. materialize I2a-full from the frozen provider sigma corpus;
2. simulate the same seven frozen V3b candidates on the common N=100 rescore bank;
3. compute per-(region,H) and aggregate W1 scores;
4. rank candidates by mean W1, tie-breaking by candidate_id;
5. compare the I2a ranking with the frozen I1 V3b ranking;
6. record the I2a top-3 set that would instantiate M2.

This stage performs no graph prediction.

P2 is included in this provider-level audit even though its graph cells failed Step 0; the Step-0 failure is irrelevant to whether I2a discriminates provider-local reconstructions.

## 6. Later M2/M3 development

Only after inspecting the provider-only audit:

- I2a-M2 will use the three lowest-W1 candidates per provider, equal provider weights, preserving the M2 philosophy.
- I2a-M3 will use all seven candidates. A new concentration parameter must be frozen using provider-local I2a evidence only, because the old lambda=30 belongs to a different I1 discrepancy scale.
- Graph WB can never select the I2a-M3 concentration parameter.

## 7. Development graph

If provider-level I2a materially increases candidate discrimination, graph development will use one frozen difficult topology across P1, P3 and P4.

The topology will be selected mechanically from the already frozen Phase-5 I1 results as the graph with the largest mean absolute error of I1-M3_FULL343 over:
- eligible worlds P1, P3, P4;
- regimes Mid and Stress;
- primary horizons H=60..240;
- all frozen rho/query points in those regimes.

This topology selection is explicitly development-driven from prior I1 outcomes and is not prospective validation.

## 8. Final validation discipline

The current Phase-5 worlds become development evidence for the I2 axis once I2a is designed against them.

If I2a is retained as a paper claim, its final validation should use fresh untouched provider worlds and a frozen I2a interface/method contract.

## 9. Decision logic

The first audit is diagnostic, not a pass/fail gate with an arbitrary threshold.

- If I2a strongly separates candidates previously similar under I1, proceed to I2a-M2 and I2a-M3.
- If I2a barely changes ambiguity or graph prediction, do not over-engineer M. This is evidence that the missing information is temporal/state dependence, motivating I2b.
- If I2a succeeds, later work may compress the full empirical CDF to a smaller public representation and measure the disclosure/performance trade-off.
