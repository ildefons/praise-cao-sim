# Sigma semantics audit — Phase 0 / Phase 1

## Primary scientific event

The authoritative definition is cumulative admissibility through the horizon:

`σ_G(A,H) = P(no violation of A occurs at any time t <= H)`.

For the event-driven benchmark, define `T_violation,A` as the time of the first **actual simulator violation event** under the declared latency/cost/quality observation semantics, with `T_violation,A = +inf` when no such event is observed. Then, exactly:

`no violation of A through H  <=>  T_violation,A > H`.

A violation occurring exactly at `H` counts as a violation by `H`.

The first-event representation is therefore a lossless compression for this specific cumulative survival functional. It does not replace the primary semantics; it is the computational representation used by the simulator analysis.

## Phase 0 audit

Phase 0 is already numerically consistent with the primary definition:

- every provider request is checked for an admissibility violation;
- latency violations occur at the request deadline when completion has not occurred;
- cost/quality violations occur when those request outcomes become observable;
- the trajectory event is the earliest actual request-level violation;
- empirical sigma at H averages `1[T_violation > H]` over independent trajectories;
- unresolved requests are right-censored unless a violation is already known.

Therefore **Phase 0 remains FROZEN**. No scientific numeric change is required.

The wording `P(T_violation > H)` should be read only as the exact event-driven implementation of the primary cumulative no-violation event above.

## Phase 1 audit

The current atlas also evaluates every top-level request and takes the earliest actual latency/cost/quality violation event. Its anchor value at `H*=120` is therefore consistent with the primary cumulative definition.

Two implementation consequences are now explicit:

1. The horizon grid is a reporting/comparison grid only. It must not define the geometry of sigma or quantize a first-crossing time.
2. Scientific calibration/search code must locate `first sigma < target` crossings from exact first-violation event times. The helper `calculate_exact_first_crossing_below_target(...)` in `sigma_curve_diagnostics.py` implements this rule and is intended for the later scientific search driver.

The PNG post-process already reconstructs exact first-violation times from `all_top_level_request_ledgers.csv` and draws the empirical staircase over the complete horizon domain rather than linearly interpolating the 5-unit reporting table.

## Finite-N curve resolution and "smoothness"

The true survival function may be smooth, but the nonparametric Monte Carlo estimator is necessarily a staircase. Horizon samples are not independent probability samples and must never be averaged as if they increased N.

For N independent trajectories the vertical probability resolution is `1/N`. Around a target survival of 0.95, the expected number of failures observed by the target horizon is only about `0.05*N`. Therefore:

- N=10 development atlas: 0.1 vertical resolution; shape is intentionally very coarse;
- N=100 scientific coarse search: 0.01 vertical resolution but only about five failures by a 0.95 crossing, so it remains a coarse location diagnostic;
- final high-N confirmation must be chosen by convergence/resolution evidence rather than visual preference.

`sigma_curve_diagnostics.py` records, for each best/bracketing AR:

- N and vertical probability resolution;
- exact sigma at H*;
- failures by H* and by stop;
- number of unique first-violation event times;
- maximum empirical jump;
- longest plateau and its fraction of the horizon domain;
- exact first crossing below the target;
- deterministic split-half difference at H* and the full-curve sup difference.

These diagnostics are a **resolution/convergence check**, not a smoothing method. Artificial smoothing of empirical white-box sigma is prohibited.

## Final freeze implication

Before freezing the final white-box reference regime/cards, inspect the exact-event best sigma curves and their resolution diagnostics using fresh high-N seeds. If the staircase remains too coarse or split-half curves are materially unstable for the effect sizes being compared, increase N without changing the physical regime, admissibility region, graph, or method definitions.
