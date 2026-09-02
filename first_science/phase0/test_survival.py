import math
import pandas as pd

from survival import (
    AdmissibilityRegion,
    empirical_survival,
    trajectory_first_violation,
    validate_ledger,
)

A = AdmissibilityRegion(l_max=3.0, c_max=5.0, q_min=0.5)
STOP = 10.0


def ledger(rows):
    base = {
        "service_start": None,
        "completion": None,
        "service": None,
        "wait": None,
        "L": None,
        "cost_rate": 2.0,
        "C": None,
        "x": 0.5,
        "Q": 0.5,
        "network_latency": 1.0,
    }
    out = []
    for row in rows:
        x = dict(base)
        x.update(row)
        out.append(x)
    return pd.DataFrame(out)


# 1) Completed and admissible -> censored/no failure.
df = ledger([{
    "request_id": 1, "arrival": 1.0, "status": "completed",
    "service_start": 1.5, "completion": 3.0, "service": 1.5,
    "wait": 0.5, "L": 2.0, "C": 3.0,
}])
validate_ledger(df, stop_time=STOP)
assert math.isinf(trajectory_first_violation(df, A, stop_time=STOP))

# 2) Completed too late -> latency violation occurs at deadline, not completion.
df = ledger([{
    "request_id": 2, "arrival": 1.0, "status": "completed",
    "service_start": 2.0, "completion": 6.0, "service": 4.0,
    "wait": 1.0, "L": 5.0, "C": 8.0,
}])
assert trajectory_first_violation(df, A, stop_time=STOP) == 4.0

# 3) Queued request whose latency deadline passed -> violation at deadline.
df = ledger([{"request_id": 3, "arrival": 4.0, "status": "queued"}])
assert trajectory_first_violation(df, A, stop_time=STOP) == 7.0

# 4) Queued request whose deadline has not passed -> right-censored.
df = ledger([{"request_id": 4, "arrival": 8.5, "status": "queued"}])
assert math.isinf(trajectory_first_violation(df, A, stop_time=STOP))

# 5) Cost failure with latency passing -> violation at completion.
df = ledger([{
    "request_id": 5, "arrival": 1.0, "status": "completed",
    "service_start": 1.0, "completion": 3.8, "service": 2.8,
    "wait": 0.0, "L": 2.8, "C": 5.6,
}])
assert trajectory_first_violation(df, A, stop_time=STOP) == 3.8

# 6) In service beyond stop, but latency deadline has passed -> latency violation.
df = ledger([{
    "request_id": 6, "arrival": 5.0, "status": "in_service",
    "service_start": 6.0, "completion": 12.0, "service": 6.0,
    "wait": 1.0, "L": 7.0, "C": 12.0,
}])
assert trajectory_first_violation(df, A, stop_time=STOP) == 8.0

# 7) In service beyond stop; future cost must not be used before completion.
A_long = AdmissibilityRegion(l_max=20.0, c_max=5.0, q_min=0.5)
assert math.isinf(trajectory_first_violation(df, A_long, stop_time=STOP))

# 8) Strict survival convention sigma(H)=P(T>H).
s = empirical_survival([3.0, math.inf, 5.0], [0.0, 3.0, 4.0, 5.0, 10.0], stop_time=STOP)
expected = [1.0, 2/3, 2/3, 1/3, 1/3]
assert all(abs(a-b) < 1e-12 for a, b in zip(s["sigma"], expected))

print("PHASE0_SURVIVAL_UNIT_TESTS_PASS")
