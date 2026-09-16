# Phase 3 M1-v2 direct inverse lift

Status: **frozen pilot baseline as of 16 September 2026**.

M1-v2 is no longer to be changed or retuned to improve the observed G0 white-box result. Historical generated artifacts may still contain `NOT_FROZEN` in their status strings because they were materialized before the freeze decision. The current scientific source of truth is `../PRAISE_I1_M0_M1_M2_DESIGN_2026-09-16.md`.

## Why v2 exists

M1-v1 introduced a deterministic median-compliance Stage 1 before fitting service variability. The full ProviderA Stage-1 search collapsed to a boundary plateau with an always-compliant deterministic surrogate. That diagnosis used only public I1 reconstruction diagnostics. No graph-level white-box result was consulted.

M1-v2 therefore removed the lossy median intermediate target and implemented the direct inverse-lifting definition:

\[
(I_{1,i},W_i) \longrightarrow \theta_i^{M1}
\]

with

\[
\theta_i^{M1}=(\mu_i,\kappa_i,CV_i).
\]

The three parameters are searched jointly through the native single-provider AICon/YAFS simulator.

## Objective

For each provider, M1-v2 minimizes uniform MSE over the complete public local I1 surface for all public admissibility regions, all exposed query-rho values, and all horizons H>0:

\[
\mathcal L_i(\mu,\kappa,CV)=
\frac{1}{N}\sum_{\rho_{region},H,\rho_q}
\left(\hat\sigma_i^{M1}-\sigma_i^{I1}\right)^2.
\]

The optimizer never receives graph-level white-box outcomes, private provider traces, fitted GMM parameters, or hidden Phase-1 provider parameters.

## Search protocol

The frozen implementation uses Optuna `TPESampler`, because the empirical sigma objective is black-box, non-differentiable, and can be piecewise flat. Mean service time and cost rate are sampled logarithmically. Service CV is sampled linearly.

Every candidate uses the same calibration trajectory seed bank (common random numbers). This makes the finite-trajectory objective deterministic conditional on the candidate and reduces Monte Carlo noise when comparing candidates.

Frozen budget:

- 100 TPE trials, 20 startup trials.
- 25 common trajectories per search candidate.
- Re-evaluate the top 5 search candidates on a disjoint common bank of 100 trajectories and select the lowest confirmation MSE.
- Replay the selected candidate on another disjoint bank of 100 trajectories. This independent replay is diagnostic only and cannot change the selected parameters.

`--smoke` remains implementation testing only.

## Public-only search bounds

Initial bounds:

- `mu / workload_period` in `[0.05, 2.0]`.
- `kappa / public_cost_rate_reference` in `[0.1, 10.0]`, where the reference is the median public `c_max / l_max` ratio.
- `CV` in `[0.0, 2.0]`.

A selected point within 2% of a search-space edge blocks freezing and requires a declared public-I1-only bound expansion.

Provider C triggered this rule. One predeclared expansion was executed before graph WB was consulted:

- `mu/workload_period` lower multiplier expanded from `0.05` to `0.005`;
- `kappa/reference` upper multiplier expanded from `10` to `100`;
- CV bounds, objective, seeds, simulator closure, and public I1 were unchanged.

The resulting selected Provider C point was interior. No further M1 bound expansion is permitted after freeze.

## Pilot closure

The pilot fixes `x=0.5` and `LinearQoS(0,1)` because the frozen I1 cards have degenerate `q_min=0.5`. Canonical IPT remains a numerical gauge. The local injector/provider adapter contributes zero network delay.

These are pilot closure conventions, not general PRAISE assumptions.

## Frozen selected provider surrogates

| Provider | mean service time | cost rate | service CV |
| --- | ---: | ---: | ---: |
| ProviderA | 0.03515902181174001 | 0.5010610641116193 | 1.4559952139534043 |
| ProviderB | 0.04788017702777221 | 2.1024570659802144 | 1.2555234974919558 |
| ProviderC | 0.0026819926073551946 | 87.30698671847529 | 0.9941982270091521 |

Provider A and B use the original v2 bounds. Provider C uses the single public-I1-only expanded contract `config_phase3_m1_contract_v2_providerC_expanded_v1.json`.

## Native graph composition and semantics correction

M1 graph prediction uses native G0:

`Fpre -> ParAll(A,B,C) -> Fpost`.

The native PRAISE ParAll completion message from each terminal provider to the composition controller is zero-byte/zero-instruction but pays the reverse-link propagation delay `0.001 s`. Therefore the corrected deterministic graph latency term outside provider boundaries is `0.014003 s`, matching the corrected M0 adapter.

This correction is a simulator-semantics defect fix, not a white-box tuning adjustment.

## Frozen graph result

The full graph prediction used 100 trajectories and was completely materialized before the graph-level WB ledger was opened. The white-box firewall passed.

Same-region whole-horizon MAE:

| rho | M0 | M1 |
| ---: | ---: | ---: |
| 0.95 | 0.500497 | 0.218163 |
| 0.975 | 0.438298 | 0.218776 |
| 0.9833333333333333 | 0.428397 | 0.179592 |
| 0.99 | 0.410442 | 0.171224 |
| 0.995 | 0.421576 | 0.128367 |

M1 improves strongly over M0 but remains systematically optimistic. Its graph sigma rapidly saturates near one.

A request-level WB/M1 trace comparison showed why: the M1 graph process is substantially faster and cheaper, especially in latency tails. Mean graph latency is approximately `0.256830 s` in WB versus `0.084790 s` in M1; 99% latency is approximately `0.565265 s` versus `0.338319 s`. Mean graph cost is approximately `1.379616` in WB versus `0.382132` in M1. QoS is `0.5` in both.

The frozen interpretation is that the native composition step works as specified, but one selected point inverse lift does not preserve enough latent process/tail information for accurate graph-level sigma.

## Files

- `config_phase3_m1_contract_v2.json`: base v2 public-I1-only inverse-lift contract.
- `config_phase3_m1_contract_v2_providerC_expanded_v1.json`: one declared Provider C boundary expansion.
- `m1_joint_lift_v2.py`: public-only bounds, tolerant full-surface loss, and boundary diagnostics.
- `run_m1_provider_lift_v2.py`: TPE search, shortlist confirmation, independent replay, manifests and CSV artifacts.
- `config_phase3_m1_graph_prediction_v2.json`: graph-prediction contract.
- `m1_graph_simulator_v2.py`: native G0 surrogate composition and top-level trace extraction.
- `run_m1_graph_prediction_v2.py`: materialize M1 graph prediction before optional WB external evaluation.
- `test_m1_joint_lift_v2.py`, `test_m1_single_provider_simulator.py`, `test_m1_graph_simulator_v2.py`: implementation/regression tests.

## Freeze rule

Do not change M1-v2 because it is optimistic, because its graph sigma saturates, or because another parameterization appears closer to WB. Reopen only for a concrete implementation defect.

The next method is M2. The first M2 gate is to test whether multiple substantially different `theta_i` vectors with similarly good public-I1 reconstruction loss produce materially different graph-level sigma. If they do, M2 should preserve inverse ambiguity rather than collapse it to one point. If they do not, M2 should introduce a richer latent process family while still consuming only the same public I1 and W_i.
