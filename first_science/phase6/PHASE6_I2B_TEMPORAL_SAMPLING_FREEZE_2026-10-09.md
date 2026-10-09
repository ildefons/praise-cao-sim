# Phase-6 I2b temporal-sampling freeze (2026-10-09)

## Decision

Freeze the first I2b temporal sampling design as:

- sliding-window stride: **s = 10 s**
- temporal lags: **D = {20, 30, 40, 50, 75, 100, 150, 200} s**

This freeze applies to the first I2b reconstruction experiment. No graph outcome, graph white-box result, final white-box result, or hidden provider parameter was used to choose it.

## Evidence used

The freeze is based on the provider-only lag/stride audit run_phase6_i2b_lag_stride_audit_v1.py, using the existing Phase-5 N=100 provider-local trajectories for P1-P4 x ProviderA-C.

The audit showed:

- stride 10 retains the stride-5 persistence curve closely while using about 51% of the paired-observation cost;
- persistence-curve MAE versus stride 5 at stride 10 is about 0.0083, with maximum absolute deviation about 0.0308;
- longer lags expose substantial nontrivial temporal change, with mean rank persistence decreasing from about 0.86 at 20 s to about 0.25 at 200 s;
- the selected lag set spans short, medium and long persistence scales while excluding the nearly-adjacent 5/10 s regime and the extremely sparse 235 s endpoint.

## Interpretation

The temporal interface is not intended to approximate every possible lag. It is a compact multiscale summary of temporal dependence whose computational cost is acceptable for reconstruction.

The selected lags are treated as separate, equally important temporal scales. No distance-dependent lag weighting is introduced.

## Frozen sampling semantics

For each provider, SLA region A, selected lag Delta in D, and valid start horizon H on the frozen positive horizon grid, retain the paired observation

    (c_j(A,H), c_j(A,H+Delta))

for the same trajectory j.

Valid start horizons are sampled every 10 s using the canonical phase inherited from the 5-s grid: start indices 0,2,4,..., i.e. H = 5,15,25,... whenever H+Delta <= 240 s.

The first I2b interface may publicize anonymous within-window pairs, but must not expose trajectory identifiers or link a trajectory across different windows.

## Immutability

The stride and lag set above are frozen before defining or evaluating an I2b reconstruction loss. They must not be changed in response to provider-fit quality, graph prediction accuracy, admission decisions, or white-box results.

Any later alternative temporal sampling must be a separately named method or development branch and must not overwrite this frozen I2b-v1 definition.
