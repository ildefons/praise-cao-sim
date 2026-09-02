"""Phase-0 survival semantics for the PRAISE I1-M0/M1 benchmark.

This module is simulator-independent by design.  It consumes a per-request
provider ledger and computes first-violation times and empirical survival.
No M0/M1/card logic belongs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf, isfinite
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AdmissibilityRegion:
    l_max: float
    c_max: float
    q_min: float

    def __post_init__(self) -> None:
        if self.l_max < 0:
            raise ValueError("l_max must be non-negative")
        if self.c_max < 0:
            raise ValueError("c_max must be non-negative")
        if not (0.0 <= self.q_min <= 1.0):
            raise ValueError("q_min must lie in [0,1]")


REQUIRED_LEDGER_COLUMNS = {
    "request_id",
    "arrival",
    "status",
    "completion",
    "C",
    "Q",
}


def _as_optional_float(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def validate_ledger(ledger: pd.DataFrame, *, stop_time: float, atol: float = 1e-10) -> None:
    """Validate Phase-0 ledger identities and censoring-compatible structure."""
    missing = REQUIRED_LEDGER_COLUMNS.difference(ledger.columns)
    if missing:
        raise ValueError(f"ledger is missing required columns: {sorted(missing)}")
    if stop_time <= 0:
        raise ValueError("stop_time must be positive")

    allowed_status = {"completed", "in_service", "queued"}
    bad_status = set(ledger["status"].dropna().unique()) - allowed_status
    if bad_status:
        raise ValueError(f"unknown request status values: {sorted(bad_status)}")

    if ledger["request_id"].duplicated().any():
        dup = ledger.loc[ledger["request_id"].duplicated(), "request_id"].tolist()
        raise ValueError(f"duplicate provider request IDs in ledger: {dup[:5]}")

    for row in ledger.to_dict("records"):
        arrival = float(row["arrival"])
        if arrival < 0 or arrival > stop_time + atol:
            raise ValueError(f"invalid arrival time for request {row['request_id']}: {arrival}")

        status = row["status"]
        start = _as_optional_float(row.get("service_start"))
        completion = _as_optional_float(row.get("completion"))
        service = _as_optional_float(row.get("service"))
        wait = _as_optional_float(row.get("wait"))
        latency = _as_optional_float(row.get("L"))
        cost = _as_optional_float(row.get("C"))
        rate = _as_optional_float(row.get("cost_rate"))
        q = _as_optional_float(row.get("Q"))
        x = _as_optional_float(row.get("x"))

        if q is None:
            raise ValueError(f"Q must be known for request {row['request_id']}")
        if x is not None and not np.isclose(q, x, atol=atol, rtol=0):
            raise ValueError(f"Q != x for request {row['request_id']}: Q={q}, x={x}")

        if status == "queued":
            if start is not None or completion is not None or service is not None:
                raise ValueError(f"queued request {row['request_id']} has service/completion data")
            if cost is not None:
                raise ValueError(f"queued request {row['request_id']} has a realized cost")
            continue

        if start is None or completion is None or service is None or wait is None or latency is None:
            raise ValueError(f"started request {row['request_id']} has incomplete timing fields")
        if start + atol < arrival or completion + atol < start:
            raise ValueError(f"non-monotone times for request {row['request_id']}")
        if not np.isclose(wait, start - arrival, atol=atol, rtol=0):
            raise ValueError(f"wait identity failed for request {row['request_id']}")
        if not np.isclose(service, completion - start, atol=atol, rtol=0):
            raise ValueError(f"service identity failed for request {row['request_id']}")
        if not np.isclose(latency, completion - arrival, atol=atol, rtol=0):
            raise ValueError(f"local latency identity failed for request {row['request_id']}")
        if rate is not None:
            expected_cost = rate * service
            if cost is None or not np.isclose(cost, expected_cost, atol=atol, rtol=0):
                raise ValueError(f"cost identity failed for request {row['request_id']}")

        if status == "completed" and completion > stop_time + atol:
            raise ValueError(f"completed request {row['request_id']} completes after stop_time")
        if status == "in_service" and completion <= stop_time + atol:
            raise ValueError(f"in_service request {row['request_id']} should be completed by stop_time")


def request_violation_time(
    row: Mapping,
    region: AdmissibilityRegion,
    *,
    stop_time: float,
) -> float:
    """Earliest *observed-by-stop* violation time for one provider request.

    Semantics:
      - latency violates at arrival + l_max if completion has not occurred by then;
      - cost and quality are request outcomes and violate at completion;
      - no use is made of outcomes occurring after stop_time.

    Returns +inf when no violation is observed by stop_time.
    """
    arrival = float(row["arrival"])
    deadline = arrival + region.l_max
    completion = _as_optional_float(row.get("completion"))
    cost = _as_optional_float(row.get("C"))
    quality = _as_optional_float(row.get("Q"))

    candidates = []

    # Latency is special: the violation is known as soon as its deadline passes.
    if deadline <= stop_time:
        if completion is None or completion > deadline:
            candidates.append(deadline)

    # Cost/quality are realized request outcomes; do not look beyond stop_time.
    if completion is not None and completion <= stop_time:
        if cost is not None and cost > region.c_max:
            candidates.append(completion)
        if quality is not None and quality < region.q_min:
            candidates.append(completion)

    return min(candidates) if candidates else inf


def trajectory_first_violation(
    ledger: pd.DataFrame,
    region: AdmissibilityRegion,
    *,
    stop_time: float,
    validate: bool = True,
) -> float:
    if validate:
        validate_ledger(ledger, stop_time=stop_time)
    if ledger.empty:
        return inf
    times = [
        request_violation_time(row, region, stop_time=stop_time)
        for row in ledger.to_dict("records")
    ]
    return min(times) if times else inf


def empirical_survival(
    first_violation_times: Sequence[float],
    horizons: Iterable[float],
    *,
    stop_time: float,
) -> pd.DataFrame:
    """Compute sigma(H)=P(T_violation > H) from independent trajectories."""
    times = np.asarray(first_violation_times, dtype=float)
    if times.ndim != 1 or len(times) == 0:
        raise ValueError("first_violation_times must be a non-empty 1-D sequence")

    hs = np.asarray(list(horizons), dtype=float)
    if np.any(hs < 0):
        raise ValueError("horizons must be non-negative")
    if np.any(hs > stop_time + 1e-12):
        raise ValueError("cannot estimate survival beyond the trajectory stop_time")

    rows = []
    for h in hs:
        survived = times > h
        rows.append({
            "horizon": float(h),
            "sigma": float(np.mean(survived)),
            "n_trajectories": int(len(times)),
            "n_survived": int(np.sum(survived)),
        })
    return pd.DataFrame(rows)


def summarize_first_violations(first_violation_times: Sequence[float], stop_time: float) -> dict:
    times = np.asarray(first_violation_times, dtype=float)
    finite = times[np.isfinite(times)]
    return {
        "n_trajectories": int(len(times)),
        "n_failed_by_stop": int(len(finite)),
        "n_censored_at_stop": int(np.sum(~np.isfinite(times))),
        "stop_time": float(stop_time),
        "min_first_violation": float(np.min(finite)) if len(finite) else None,
        "median_first_violation": float(np.median(finite)) if len(finite) else None,
    }
