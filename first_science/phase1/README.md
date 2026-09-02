# PRAISE first science — Phase 1

**Status: IN DEVELOPMENT — scientific discovery v1 frozen and ready to run.**

## Purpose

Construct and freeze a small technology-neutral battery of white-box reference regimes and admissibility regions before any I1, M0, or M1 implementation.

AICon/YAFS execution of the physical graph is the sole white-box truth generator. Phase 1 must not analytically fabricate white-box outcomes and must not use M0/M1 performance to select the benchmark.

## Primary sigma semantics

The authoritative event is cumulative admissibility through the horizon:

`σ_G(A,H) = P(no violation of A occurs at any time t <= H)`.

In the event-driven simulator, `T_violation,A` denotes the time of the first actual latency/cost/quality violation event under the declared observation semantics, with `+inf` if no violation occurs. Therefore the exact computational representation is:

`σ_G(A,H) = P(T_violation,A > H)`.

A violation exactly at `H` counts as violated by `H`. The reporting horizon grid does not define sigma; it is used only for stored comparison/fitting tables. Exact white-box target-crossing times must be taken from first-violation events. See `SIGMA_SEMANTICS_AUDIT.md`.

## Physical graph and provider instruction semantics

`Fpre -> ParAll(A,B,C) -> Fpost`

A/B/C intentionally use the same native service-module implementation. Their stochasticity enters through a new native per-invocation realization of `Message.instructions`.

For this benchmark, the interpretation is frozen:

- `D_i` / `Message.instructions` is the computational instruction requirement of provider `i` for one service invocation.
- `Dbar` is the central mean provider service-instruction requirement per invocation.
- `delta` controls provider-to-provider heterogeneity in that mean requirement:
  - `A = Dbar * (1-delta)`
  - `B = Dbar`
  - `C = Dbar * (1+delta)`
- `delta` is not invocation-to-invocation stochastic variability; that is controlled separately by the frozen gamma CV.
- `D_i` is not the external/root workload. Workload `W` is fixed separately by root invocation timing/pattern.

Existing implementation/configuration names such as `center_instruction_mean` are retained for compatibility.

AICon/YAFS causally generates service, queueing, latency, cost, and quality from provider requirements together with the fixed execution/resource/environment configuration. `L`, `C`, and `Q` are never directly sampled. Quality remains `Q=x`.

## N=10 discovery -> freeze finalists -> N=100 confirmation

Phase 1 separates cheap discovery from confirmation:

1. **Discovery (`N=10` per candidate).** Search provider settings under one common N=10 seed bank. For each physical candidate, reuse its native ledgers to scan many `A={L<=l,C<=c,Q>=x}` offline. M0/M1 are forbidden.
2. **Freeze finalists.** Retain a small informative battery and freeze each exact `(Dbar,delta,A)` in `selected_whiteboxes.json` with status `FROZEN_FOR_CONFIRMATION`.
3. **Confirmation (`N=100` per finalist).** Rerun only those exact finalists with 100 fresh independent trajectories. **Do not recalibrate A on N=100 data.**
4. **Later precision, only if needed.** Increase N further only for convergence/precision after confirmation; do not reopen physical parameters or A.

At N=10, `0.9` and `1.0` form the empirical bracket around target `0.95`. N=10 is used to discover informative regimes, not to claim 0.95 precision.

## Development atlas result and lesson

The original 3x3, N=10 development atlas validated native execution, provider parameterization, offline AR scanning, exact-event sigma reconstruction and diagnostics. It remains explicitly non-scientific.

A first finalist selector applied to that coarse atlas proposed:

- a promising latency-dominant case at `Dbar=420M, delta=0` with 10 distinct first-violation times by H=240;
- cost and mixed cases with only two first violations by H=240.

Those sparse cost/mixed curves are **not** frozen. This result motivated an explicit information gate and a targeted scientific discovery grid rather than weakening the finalist standard.

## Frozen scientific discovery v1

`config_phase1.json` remains the general fail-closed template. The first complete versioned instantiation is:

`config_phase1_discovery_v1.json`

It freezes the already validated environment/workload/provider constants and a targeted 5x5 provider grid selected using white-box development evidence only:

- `Dbar ∈ {300, 330, 360, 390, 420} M instructions/invocation`
- `delta ∈ {0, 0.05, 0.10, 0.15, 0.20}`
- 25 physical candidates total
- common scientific discovery seeds `2000..2009`, fresh from development seeds `1000..1009`
- `N=10` per candidate
- `H*=120`, horizon domain `[0,240]`, reporting step 5
- gamma CV `0.3`, IPT `1e9`, COST rate `3`, `x=q*=0.5`
- fixed root workload period `0.2`
- no M0/M1 in discovery

The targeted search box follows the coarse development atlas: 160M was largely floor/ceiling-uninformative, while the 300–420M region contained the useful transition structure. The v1 grid refines that interval without using any M0/M1 result.

## Finalist information gate

`whitebox_candidate_selection.py` does not freeze a case merely because it carries a latency/cost/mixed label. Before role ranking, an N=10 finalist must satisfy:

- anchor survival within the N=10 0.9/1.0 bracket around 0.95;
- at least 4 first violations by H=240;
- at least 4 distinct first-violation times;
- at least 4 distinct stored sigma levels.

Role-specific requirements are then applied:

- latency: at least 3 latency-first trajectories and at least 2:1 latency dominance over cost;
- cost: at least 3 cost-first trajectories and at least 2:1 cost dominance over latency;
- mixed: at least 2 latency-first and 2 cost-first trajectories, with cause-count imbalance <=2.

If discovery does not contain a qualifying case for a role, selection fails explicitly. The correct response is to refine/expand discovery, not to freeze a sparse curve.

## Commands

First validate the simulator-independent contracts:

```bash
python test_presearch_contract.py
python test_atlas_analysis.py
python test_whitebox_atlas_configuration.py
python test_generate_sigma_plots.py
python test_sigma_curve_diagnostics.py
python test_whitebox_candidate_selection.py
python test_scientific_discovery_configuration.py
```

Before the full scientific run, use an engineering-only smoke:

```bash
python whitebox_scientific_discovery.py --clean --max-physical-settings 1 --max-trajectories-per-setting 2
```

Then run the complete frozen 25x10 discovery:

```bash
python whitebox_scientific_discovery.py --clean
```

Post-process without rerunning the simulator:

```bash
python generate_sigma_plots.py --results-dir results/scientific_discovery_v1
python sigma_curve_diagnostics.py --results-dir results/scientific_discovery_v1
python whitebox_candidate_selection.py --results results/scientific_discovery_v1
```

Expected final selector marker, if all three roles have informative candidates:

```text
PHASE1_WHITEBOX_SELECTION_PROPOSAL_PASS
```

The proposal is written to:

`results/scientific_discovery_v1/whitebox_selection/selected_whiteboxes_proposal.json`

Review that proposal once. Only then copy the exact finalists into `selected_whiteboxes.json` and change its status to `FROZEN_FOR_CONFIRMATION`.

## Selected-whitebox manifest

`selected_whiteboxes.json` remains empty until discovery produces acceptable finalists. N=100 confirmation is blocked until the manifest contains the exact selected physical parameters and exact `A=(l_max,c_max,q_min)` values with status `FROZEN_FOR_CONFIRMATION`.

`assert_phase1_confirmation_configuration_is_ready(...)` additionally requires a 100-seed confirmation bank disjoint from the N=10 discovery bank.

## Development requirement

Non-trivial functions use explicit self-explanatory snake-case names. Each non-trivial function carries a docstring describing purpose, inputs/outputs/side effects as relevant, and maintained **Called by** provenance.
