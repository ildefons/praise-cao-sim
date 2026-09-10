# Sigma semantics audit - current Phase-1 v2 / Phase-2 / Phase-3

## Status

The current first-science pipeline uses **rho-thresholded cumulative request compliance**. Earlier first-violation/no-violation survival semantics are historical development provenance and are not the authoritative semantics for the frozen Phase-1 v2 AR battery, rho-conditioned I1, or M0 evaluation.

## Authoritative trajectory state

For admissibility region `A`, let every emitted request receive one decision time:

- completion time, when it completes no later than its latency deadline;
- latency deadline, when it has not completed in time;
- unresolved, when the decision time lies after the observable horizon/stop.

At horizon `H`, only requests decided by `H` enter the cumulative compliance fraction:

`c(A,H) = n_compliant_decided_by_H / n_decided_by_H`.

Before any request is decided, the frozen convention is `c(A,H)=1.0`.

For required fraction `rho`, a trajectory is SLA-compliant at `H` exactly when

`c(A,H) >= rho`.

Across independent trajectories the authoritative probability is

`sigma(A,H;rho) = P(c(A,H) >= rho)`.

## Consequence: recovery is allowed

This is not a first-passage event. After a failure lowers the cumulative fraction below `rho`, later compliant decisions can raise the fraction above `rho` again. Therefore both trajectory SLA state and empirical `sigma(H;rho)` may be non-monotone in horizon.

The exact-compliant-time area utilities in `sla_compliance_analysis.py` integrate every compliant interval and explicitly do not compute RMST/first-passage survival.

## Request-level semantics

- `L <= l_max` is evaluated using the request latency deadline. A missed deadline is a latency failure at that deadline.
- `C <= c_max` and `Q >= q_min` are evaluated when an in-time completion makes those outcomes observable.
- Cost and quality are not evaluated after a latency failure.
- Requests not yet decided by `H` are excluded from the cumulative denominator.
- A decision exactly at `H` counts as decided by `H`.

These rules are implemented in `build_request_sla_decision_table(...)` and `calculate_trajectory_cumulative_sla_curve(...)` in `sla_compliance_analysis.py`.

## Relation to historical first-violation code

Earlier Phase-0/Phase-1 development used `T_violation` and `P(T_violation>H)` to represent a strict no-violation-through-H event. That event is mathematically different from the current `P(c(A,H)>=rho)` query whenever `rho<1`, and it forbids the recovery behavior intentionally allowed by the current benchmark.

Accordingly:

- do not use first-violation crossing utilities to define current sigma;
- do not infer monotonicity in H for current sigma;
- do not describe the M0 same-rho product as a theorem-level lower bound merely by importing the old no-violation conjunction argument.

## Frozen provenance

The authoritative Phase-1 v2 contract is `phase1_v2_ar_freeze_manifest_v1.json`, which records

`sigma_G(A,H;rho)=P(c_G(A,H)>=rho)`

with cumulative `[0,H]` accounting, zero-decision compliance `1.0`, and the frozen latency/cost/mixed AR battery. Phase 2 and Phase 3 reuse these accounting semantics through `sla_compliance_analysis.py`.
