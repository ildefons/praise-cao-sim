# Phase-6 I2b-v2 variability-weighted energy loss freeze (2026-10-09)

## Decision

Freeze a second I2b reconstruction objective that keeps the exact I2b-v1 public temporal-pair representation and temporal sampling, but replaces equal temporal-window weighting with provider-specific weights derived only from the public target variability.

For temporal window w=(A,H,Delta), with public same-trajectory pairs (c_j(H),c_j(H+Delta)), define

    V_w = (1/N) sum_j [c_j(H+Delta)-c_j(H)]^2

and

    omega_w = V_w / sum_w' V_w'.

The I2b-v2 reconstruction loss is

    L_var(theta) = sum_w omega_w E_hat(P_obs,w, P_theta,w),

where E_hat is the already frozen empirical bivariate energy V-statistic in the two-dimensional compliance plane.

## Rationale

The equal-window I2b-v1 loss gives the same aggregation weight to a nearly static interval and to an interval containing substantial temporal displacement. The variability weighting makes the observed process itself determine temporal importance. Squared displacement naturally gives more influence to windows containing larger changes without introducing a hand-chosen lag or severity coefficient.

The second moment E[(Delta c)^2] is used rather than Var(Delta c), because a window in which all trajectories make the same large transition must still count as highly dynamic.

Both deterioration and improvement contribute to V_w. No directional safety preference is inserted into the weights.

## Audit basis

The pre-reconstruction variability audit over P1-P4 x ProviderA-C showed nonuniform but nondegenerate weights. Across providers, the largest single-window weight was at most about 0.0459. The effective number of windows ranged from about 49.9 to 252.9 out of 630. The largest top-50 mass was about 0.737. Endpoint-shuffle sensitivity remained positive for all providers.

For P4 specifically, the weighting shifts substantial mass toward the rho=0.95 region: about 0.503 for ProviderA, 0.439 for ProviderB, and 0.738 for ProviderC. This arises from the public temporal variability itself and was observed before any I2b-v2 reconstruction or graph prediction.

## Frozen scope

The following remain unchanged from I2b-v1:

- stride s=10 s;
- lags {20,30,40,50,75,100,150,200} s;
- public anonymous paired-distribution representation;
- empirical energy V-statistic inside each window;
- provider parameter domains;
- 64 Sobol + 192 TPE matched search architecture;
- N=25 search CRN bank;
- top-24 fresh N=100 rescore;
- top-3/provider equal-weight M2 support.

Only the cross-window aggregation is changed.

## Firewall and immutability

The weights are computed only from each provider's frozen public I2b target. Graph prediction, graph white-box outcomes, final white-box outcomes, hidden provider parameters, and candidate reconstruction quality do not enter the weights.

This objective is frozen before any I2b-v2 inverse reconstruction. It must not be changed in response to provider fit quality or graph performance.
