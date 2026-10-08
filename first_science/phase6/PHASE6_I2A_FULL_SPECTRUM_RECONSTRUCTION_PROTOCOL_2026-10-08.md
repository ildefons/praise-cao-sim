# Phase-6 I2a full-spectrum provider reconstruction protocol (2026-10-08)

## Purpose

This is the next development reconstruction after the cross-world I2a loss audit.

The I2a fitting loss is now frozen as the best current provider-reconstruction loss:

[
L_{I2a}(theta)=sqrt(mean_{A,H} integral_0^1 [sigma_theta(A,H;rho)-sigma_I2a(A,H;rho)]^2 d rho).
]

The integral is evaluated exactly over pooled empirical breakpoints. No discrete rho grid is used.

This protocol does **not** reopen the loss choice. The remaining development question is whether a stronger inverse search can exploit that loss.

## Information firewall

The reconstruction may read only:

- the public I2a empirical marginal compliance distributions;
- the public provider card metadata;
- the frozen public-derived parameter domains;
- the method-side surrogate simulator;
- the search and common-rescore seed banks frozen below.

It may not read graph predictions, graph WB, final WB, private I1 ledgers, or hidden provider parameters.

Hidden truth may be opened only after the provider support is frozen, in a separate diagnostic.

## Development world

Run first on P4, Providers A/B/C, to provide a direct comparison with the earlier I1-M2 and I2a-W1 development experiments.

This is post-I1 development evidence, not prospective Phase-5 evidence.

## Search architecture

The old V3 architecture (7 independent TPE fits x 25 trials, retain only one winner per fit) is not reused.

For each provider:

1. Search the same frozen public-derived 3-D domain.
2. Use one 256-trial study.
3. The first 64 trials are a deterministic scrambled Sobol design in normalized parameter space.
4. The remaining 192 trials are TPE-adaptive.
5. Every search trial is evaluated on the same N=25 CRN provider-simulation bank.
6. Rank all 256 trials by the frozen full-spectrum I2a loss.
7. Carry the best 24 trials, without hidden-truth filtering, to a fresh common N=100 rescore bank.
8. Select the best 3 by N=100 full-spectrum loss, deterministic tie-break by trial number.
9. Assign equal provider weights 1/3 and form the 27 Cartesian M2 joint models with weight 1/27.

Search sampling is log-uniform for mean service time and cost rate and linear for service CV, matching the existing parameter-domain semantics.

## Seeds

- Sobol design seed: 420001.
- TPE sampler seeds by provider: 420101, 420103, 420107.
- Search CRN bank: 60000..60024 (N=25).
- Common rescore bank: 60100..60199 (N=100).

These development banks are disjoint from the Phase-5 V3 reconstruction and graph-prediction banks.

## No tuning after outcome

The following are frozen before execution:

- full-spectrum loss;
- 256 total trials;
- 64 Sobol initial trials;
- 192 adaptive TPE trials;
- N=25 search bank;
- top-24 rescore shortlist;
- N=100 common rescore bank;
- top-3 M2 selection.

Do not change these after seeing provider reconstruction or graph results. Any further search architecture would be a new explicitly labelled development version.
