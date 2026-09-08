# Phase-1 AR-selection reopening diagnostics

These figures are tracked document assets copied from read-only diagnostics of
the frozen Phase-1 v1 final N=100 confirmation.

Source evidence:

`first_science/phase1/results/final_n100_confirmation_v1/trajectory_compliance_curves.csv`

The rho-sensitivity figures show, for the same frozen v1 admissibility regions,
that rho=0.95 is already the boundary regime: rho=0.90 is near ceiling, while
rho>=0.975 degrades sharply.

The compliance-fraction ECDF figures show the underlying reason directly:
the distributions of c_j(A,H) at H=120 and H=240 are concentrated around
the nominal rho_G=0.95 threshold.

Scientific role:
these diagnostics motivate reopening only the Phase-1 top-level
admissibility-region selection policy. They do not change simulator semantics,
workload semantics, SLA accounting, or the historical v1 benchmark evidence.
