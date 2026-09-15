# Phase 3 M1-v2 direct inverse lift

Status: implementation candidate, not frozen.

## Why v2 exists

M1-v1 introduced a deterministic median-compliance Stage 1 before fitting service variability. The full ProviderA Stage-1 search collapsed to a boundary plateau with an always-compliant deterministic surrogate. That diagnosis used only public I1 reconstruction diagnostics. No graph-level white-box result was consulted.

M1-v2 therefore removes the lossy median intermediate target and returns to the intended inverse-lifting definition:

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

## Search

The candidate implementation uses Optuna `TPESampler`, because the empirical sigma objective is black-box, non-differentiable, and can be piecewise flat. Mean service time and cost rate are sampled logarithmically. Service CV is sampled linearly.

Every candidate uses the same calibration trajectory seed bank (common random numbers). This makes the finite-trajectory objective deterministic conditional on the candidate and reduces Monte Carlo noise when comparing candidates.

The default candidate budget is:

- 100 TPE trials, 20 startup trials.
- 25 common trajectories per search candidate.
- Re-evaluate the top 5 search candidates on a disjoint common bank of 100 trajectories and select the lowest confirmation MSE.
- Replay the selected candidate on another disjoint bank of 100 trajectories. This independent replay is diagnostic only and cannot change the selected parameters.

`--smoke` uses much smaller budgets and is implementation testing only.

## Public-only search bounds

The initial bounds are unchanged in spirit from M1-v1 and use only the public workload and public admissibility boundaries:

- `mu / workload_period` in `[0.05, 2.0]`.
- `kappa / public_cost_rate_reference` in `[0.1, 10.0]`, where the reference is the median public `c_max / l_max` ratio.
- `CV` in `[0.0, 2.0]`.

A selected point within 2% of a search-space edge in optimizer coordinates is flagged. A boundary flag blocks freezing and requires a declared public-I1-only bound expansion.

## Pilot closure

The current pilot still fixes `x=0.5` and `LinearQoS(0,1)` because the frozen I1 cards have degenerate `q_min=0.5`. Canonical IPT remains a numerical gauge. The local two-node zero-delay injector/provider adapter remains unchanged.

These are pilot closure conventions, not general PRAISE assumptions.

## Files

- `config_phase3_m1_contract_v2.json`: auditable v2 contract and budgets.
- `m1_joint_lift_v2.py`: pure public-only bounds, tolerant full-surface loss, and boundary diagnostics.
- `run_m1_provider_lift_v2.py`: Optuna TPE search, shortlist confirmation, independent replay, manifests and CSV artifacts.
- `test_m1_joint_lift_v2.py`: simulator-independent regression tests.

## Run order

From `first_science/phase3`:

```bash
python test_m1_joint_lift_v2.py
python test_m1_single_provider_simulator.py
python run_m1_provider_lift_v2.py --provider ProviderA --smoke
```

If Optuna is not already installed in the active environment:

```bash
python -m pip install optuna
```

Do not run the full three-provider lift until the ProviderA smoke output has been inspected.
