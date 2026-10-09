# Phase-6 I2b-v1 energy-loss freeze (2026-10-09)

## Decision

Freeze the reconstruction loss for the first I2b experiment as the empirical bivariate energy V-statistic over the already frozen public temporal-pair representation.

For one temporal window, with observed pair sample X and candidate pair sample Y in R^2 where each point is (c(H), c(H+Delta)), use

    E_hat(X,Y) = 2 mean||X-Y|| - mean||X-X'|| - mean||Y-Y'||,

with Euclidean distance in the two-dimensional compliance plane.

Target and candidate sample sizes may differ. In particular, the frozen search uses target N=100 versus candidate N=25, while common rescore uses N=100 versus N=100.

## Aggregation

For each selected lag Delta, average the window energy losses equally over all five SLA regions and all valid frozen start horizons. Then average the eight lag means equally.

    L_I2b(theta) = mean_Delta mean_(A,H in W_Delta) E_hat(P_obs, P_theta).

No additional I2a marginal term is added to the objective. Each bivariate pair distribution already constrains both endpoint marginals and their temporal dependence. The separately materialized I2a marginals remain part of the public I2b interface and can be used for diagnostics, but they do not receive an extra objective weight.

## Evidence supporting the freeze

The pre-reconstruction benchmark passed all algebraic and information-sensitivity checks over P1-P4 x ProviderA-C:

- self-distance was exactly zero;
- deterministic endpoint shuffling preserved each one-dimensional marginal exactly;
- destroying only within-window pairing produced strictly positive loss for all 12 providers;
- mean shuffled-pair loss across providers was about 4.89e-4;
- provider means ranged from about 2.73e-4 to 6.98e-4;
- pure scoring cost was about 0.058 s at N=25 and 0.256 s at N=100, implying about 21 s/provider for the planned 256-search + 24-rescore schedule.

## Lag-level sanity check

The shuffle response was positive at every frozen lag for every provider. Aggregate mean shuffle sensitivity decreased smoothly with lag:

- 20 s: 8.38e-4
- 30 s: 7.30e-4
- 40 s: 6.47e-4
- 50 s: 5.82e-4
- 75 s: 4.52e-4
- 100 s: 3.46e-4
- 150 s: 2.06e-4
- 200 s: 1.14e-4.

This is not treated as a defect or used to reweight/reselect lags. It is consistent with the earlier persistence audit: temporal dependence weakens as separation grows, so destroying the pairing has a smaller effect at long lag. The 200-s response remains positive for all providers.

## Frozen implementation

The authoritative scorer is i2b_energy_loss_v1.py. The implementation precomputes each target-target self term and uses the empirical V-statistic without binning, kernels, bandwidths, or learned weights.

## Immutability

This loss is frozen before any I2b inverse reconstruction or graph prediction. It must not be modified in response to provider fit quality, recovered parameters, graph prediction, SLA decision accuracy, or white-box results.

Any later alternative loss must be named as a separate method and may not overwrite I2b-v1.
