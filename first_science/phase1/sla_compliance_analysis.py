"""SLA-compliance accounting for PRAISE Phase-1 white-box request ledgers.

The primary Phase-1 sigma is the probability that a stochastic trajectory meets
a cumulative request-level SLA over the accounting window [0,H] from the common
prescribed initialization at t=0.  A request is decided either when it completes
within its latency deadline or, if it misses that deadline, at the deadline.
Requests not yet decided by H do not enter that horizon's compliance fraction.

This module is simulator-independent and can be applied to N=10 discovery
ledgers and fresh N=100 confirmation ledgers without rerunning AICon/YAFS.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import sqrt
from typing import Iterable

import numpy as np
import pandas as pd

EVENT_TOLERANCE = 1e-12


@dataclass(frozen=True)
class SlaComplianceDefinition:
    """Hold the frozen request-level SLA accounting semantics.

    Args:
        rho: Required fraction of decided requests that must be admissible.
        accounting_origin: Common time origin. Phase 1 freezes this at t=0.
        zero_decision_compliance: Compliance fraction before any request is
            decided. Phase 1 uses 1.0: no observable violation has yet occurred.

    Called by:
        - ``load_sla_compliance_definition`` in ``selection_policy.py``.
        - N=10/N=100 SLA analysis entry points.
    """

    rho: float
    accounting_origin: float = 0.0
    zero_decision_compliance: float = 1.0


def build_request_sla_decision_table(
    trajectory_request_ledger: pd.DataFrame,
    latency_threshold: float,
    cost_threshold: float,
    quality_threshold: float,
    stop_time: float,
) -> pd.DataFrame:
    """Reconstruct one SLA decision per emitted top-level request.

    A request that completes no later than ``emission + latency_threshold`` is
    decided at completion, where cost and quality are also observable. A request
    that has not completed by its latency deadline is decided as a latency
    failure at that deadline. Requests whose decision time lies after the
    simulator stop remain unresolved.

    Args:
        trajectory_request_ledger: One top-level ledger row per logical request.
        latency_threshold: Inclusive request latency limit.
        cost_threshold: Inclusive request cost limit.
        quality_threshold: Inclusive minimum request quality.
        stop_time: Largest observable physical time.

    Returns:
        A table retaining every request with decision time/status, joint
        compliant flag, and request-level failure dimensions.

    Side effects:
        None.

    Called by:
        - ``calculate_empirical_sla_sigma_from_ledgers`` in this module.
        - ``write_selected_sla_candidate_diagnostics`` in
          ``whitebox_candidate_selection.py``.
        - ``analyze_and_plot_n100_confirmation`` in
          ``run_n100_matched_confirmation.py``.
        - unit tests in ``test_sla_compliance_analysis.py``.
    """
    required = {"request_id", "emission", "completion", "L", "C", "Q"}
    missing = required.difference(trajectory_request_ledger.columns)
    if missing:
        raise ValueError(f"trajectory ledger missing columns: {sorted(missing)}")

    latency_limit = float(latency_threshold)
    cost_limit = float(cost_threshold)
    quality_limit = float(quality_threshold)
    stop = float(stop_time)
    if latency_limit < 0.0 or cost_limit < 0.0:
        raise ValueError("latency and cost thresholds must be non-negative")

    ordered = trajectory_request_ledger.sort_values(["emission", "request_id"]).copy()
    emission = ordered["emission"].astype(float).to_numpy()
    completion = pd.to_numeric(ordered["completion"], errors="coerce").to_numpy(dtype=float)
    latency = pd.to_numeric(ordered["L"], errors="coerce").to_numpy(dtype=float)
    cost = pd.to_numeric(ordered["C"], errors="coerce").to_numpy(dtype=float)
    quality = pd.to_numeric(ordered["Q"], errors="coerce").to_numpy(dtype=float)

    deadline = emission + latency_limit
    completion_is_finite = np.isfinite(completion)
    completed_in_time = completion_is_finite & (
        completion <= deadline + EVENT_TOLERANCE
    )
    decision_time = np.where(completed_in_time, completion, deadline)
    decided_by_stop = decision_time <= stop + EVENT_TOLERANCE

    if np.any(completed_in_time & (~np.isfinite(cost) | ~np.isfinite(quality))):
        raise ValueError("in-time completed requests must expose finite C and Q")

    latency_failed = decided_by_stop & (~completed_in_time)
    cost_failed = decided_by_stop & completed_in_time & (cost > cost_limit)
    quality_failed = decided_by_stop & completed_in_time & (quality < quality_limit)
    compliant = decided_by_stop & completed_in_time & (~cost_failed) & (~quality_failed)

    causes: list[str] = []
    for is_decided, fail_l, fail_c, fail_q in zip(
        decided_by_stop, latency_failed, cost_failed, quality_failed
    ):
        if not bool(is_decided):
            causes.append("unresolved")
            continue
        active = [
            name
            for name, flag in (
                ("latency", bool(fail_l)),
                ("cost", bool(fail_c)),
                ("quality", bool(fail_q)),
            )
            if flag
        ]
        if not active:
            causes.append("none")
        elif len(active) == 1:
            causes.append(active[0])
        else:
            causes.append("tie")

    output = pd.DataFrame(
        {
            "request_id": ordered["request_id"].to_numpy(),
            "emission": emission,
            "completion": completion,
            "latency_deadline": deadline,
            "decision_time": np.where(decided_by_stop, decision_time, np.nan),
            "decision_status": np.where(decided_by_stop, "decided", "unresolved"),
            "compliant": pd.array(
                [bool(value) if decided else pd.NA for value, decided in zip(compliant, decided_by_stop)],
                dtype="boolean",
            ),
            "failure_cause": causes,
            "latency_failed": latency_failed,
            "cost_failed": cost_failed,
            "quality_failed": quality_failed,
            "L": latency,
            "C": cost,
            "Q": quality,
        }
    )
    return output.sort_values(["emission", "request_id"]).reset_index(drop=True)


def _cumulative_compliance_after_decisions(
    decided_table: pd.DataFrame,
    horizon: float,
    zero_decision_compliance: float,
) -> tuple[int, int, float]:
    """Return decided count, compliant count, and cumulative compliance at H.

    Called by:
        - ``calculate_trajectory_cumulative_sla_curve`` in this module.
        - ``calculate_empirical_sla_sigma_from_decision_tables`` in this module.
    """
    h = float(horizon)
    decided = decided_table[
        decided_table["decision_time"].notna()
        & (decided_table["decision_time"].astype(float) <= h + EVENT_TOLERANCE)
    ]
    n_decided = int(len(decided))
    if n_decided == 0:
        return 0, 0, float(zero_decision_compliance)
    n_compliant = int(decided["compliant"].fillna(False).astype(bool).sum())
    return n_decided, n_compliant, float(n_compliant / n_decided)


def calculate_trajectory_cumulative_sla_curve(
    request_decisions: pd.DataFrame,
    horizons: Iterable[float],
    sla_definition: SlaComplianceDefinition,
) -> pd.DataFrame:
    """Evaluate one trajectory's cumulative [0,H] SLA status on a horizon grid.

    Args:
        request_decisions: Output of ``build_request_sla_decision_table``.
        horizons: Elapsed times H measured from the common t=0 origin.
        sla_definition: Frozen rho and zero-decision convention.

    Returns:
        One row per horizon with counts, compliance fraction and SLA pass/fail.

    Side effects:
        None.

    Called by:
        - ``calculate_empirical_sla_sigma_from_decision_tables`` in this module.
        - selected-candidate and N=100 diagnostic writers.
    """
    rows: list[dict[str, object]] = []
    for horizon in map(float, horizons):
        if horizon < sla_definition.accounting_origin - EVENT_TOLERANCE:
            raise ValueError("horizon precedes the frozen accounting origin")
        n_decided, n_compliant, fraction = _cumulative_compliance_after_decisions(
            request_decisions,
            horizon,
            sla_definition.zero_decision_compliance,
        )
        rows.append(
            {
                "horizon": horizon,
                "decided_requests": n_decided,
                "compliant_requests": n_compliant,
                "compliance_fraction": fraction,
                "sla_compliant": bool(
                    fraction + EVENT_TOLERANCE >= float(sla_definition.rho)
                ),
            }
        )
    return pd.DataFrame(rows)


def calculate_exact_trajectory_sla_compliance_area(
    request_decisions: pd.DataFrame,
    sla_definition: SlaComplianceDefinition,
    horizon_min: float,
    horizon_max: float,
) -> tuple[float, float]:
    """Integrate one trajectory's binary SLA-compliant state exactly in time.

    The trajectory may leave and later recover cumulative SLA compliance. Area
    therefore sums every compliant interval; it is not a first-passage/RMST
    calculation.

    Args:
        request_decisions: Per-request decision table for one trajectory/A.
        sla_definition: Frozen SLA definition.
        horizon_min: Lower integration endpoint.
        horizon_max: Upper integration endpoint.

    Returns:
        ``(compliant_time, normalized_area)``.

    Side effects:
        None.

    Called by:
        - ``calculate_exact_empirical_sla_compliance_area`` in this module.
        - optimized N=10 candidate metric tests.
    """
    start = float(horizon_min)
    stop = float(horizon_max)
    if start < sla_definition.accounting_origin - EVENT_TOLERANCE or stop <= start:
        raise ValueError("area interval must satisfy accounting_origin <= min < max")

    decided = request_decisions[request_decisions["decision_time"].notna()].copy()
    if decided.empty:
        width = stop - start
        initial_state = (
            sla_definition.zero_decision_compliance + EVENT_TOLERANCE
            >= sla_definition.rho
        )
        area = width if initial_state else 0.0
        return float(area), float(area / width)

    grouped = (
        decided.groupby("decision_time", sort=True)["compliant"]
        .agg(["count", lambda values: int(pd.Series(values).fillna(False).astype(bool).sum())])
        .reset_index()
    )
    grouped.columns = ["decision_time", "n_decisions", "n_compliant"]

    prior = grouped[grouped["decision_time"].astype(float) <= start + EVENT_TOLERANCE]
    n_decided = int(prior["n_decisions"].sum())
    n_compliant = int(prior["n_compliant"].sum())
    if n_decided == 0:
        fraction = float(sla_definition.zero_decision_compliance)
    else:
        fraction = float(n_compliant / n_decided)
    current_state = bool(fraction + EVENT_TOLERANCE >= sla_definition.rho)
    current_time = start
    area = 0.0

    future = grouped[
        (grouped["decision_time"].astype(float) > start + EVENT_TOLERANCE)
        & (grouped["decision_time"].astype(float) <= stop + EVENT_TOLERANCE)
    ]
    for row in future.itertuples(index=False):
        event_time = min(float(row.decision_time), stop)
        if event_time > current_time:
            area += (event_time - current_time) * float(current_state)
        n_decided += int(row.n_decisions)
        n_compliant += int(row.n_compliant)
        fraction = float(n_compliant / n_decided)
        current_state = bool(fraction + EVENT_TOLERANCE >= sla_definition.rho)
        current_time = event_time

    if current_time < stop:
        area += (stop - current_time) * float(current_state)
    width = stop - start
    return float(area), float(area / width)


def calculate_exact_empirical_sla_compliance_area(
    decision_tables: list[pd.DataFrame],
    sla_definition: SlaComplianceDefinition,
    horizon_min: float,
    horizon_max: float,
) -> tuple[float, float]:
    """Average exact SLA-compliant time over independent trajectories.

    Called by:
        - N=10 and N=100 analysis code.
        - unit tests in ``test_sla_compliance_analysis.py``.
    """
    if not decision_tables:
        raise ValueError("at least one trajectory decision table is required")
    areas = [
        calculate_exact_trajectory_sla_compliance_area(
            table, sla_definition, horizon_min, horizon_max
        )[0]
        for table in decision_tables
    ]
    mean_area = float(np.mean(areas))
    return mean_area, float(mean_area / (float(horizon_max) - float(horizon_min)))


def calculate_empirical_sla_sigma_from_decision_tables(
    decision_tables: list[pd.DataFrame],
    horizons: Iterable[float],
    sla_definition: SlaComplianceDefinition,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute sigma(H,rho) and trajectory compliance summaries on a grid.

    Returns:
        ``(sigma_curve, trajectory_curves)``.

    Called by:
        - ``calculate_empirical_sla_sigma_from_ledgers`` in this module.
        - N=100 confirmation analysis.
    """
    if not decision_tables:
        raise ValueError("at least one trajectory decision table is required")
    trajectory_frames: list[pd.DataFrame] = []
    for trajectory_index, table in enumerate(decision_tables):
        curve = calculate_trajectory_cumulative_sla_curve(
            table, horizons, sla_definition
        )
        curve.insert(0, "trajectory", trajectory_index)
        trajectory_frames.append(curve)
    trajectories = pd.concat(trajectory_frames, ignore_index=True)
    sigma = (
        trajectories.groupby("horizon", as_index=False)
        .agg(
            sigma=("sla_compliant", "mean"),
            mean_compliance_fraction=("compliance_fraction", "mean"),
            mean_decided_requests=("decided_requests", "mean"),
        )
        .sort_values("horizon")
        .reset_index(drop=True)
    )
    sigma.insert(1, "rho", float(sla_definition.rho))
    return sigma, trajectories


def calculate_empirical_sla_sigma_from_ledgers(
    all_trajectory_ledgers: pd.DataFrame,
    latency_threshold: float,
    cost_threshold: float,
    quality_threshold: float,
    horizons: Iterable[float],
    stop_time: float,
    sla_definition: SlaComplianceDefinition,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Reconstruct decisions and sigma directly from multi-trajectory ledgers.

    Returns:
        ``(sigma_curve, trajectory_curves, all_request_decisions)``.

    Side effects:
        None.

    Called by:
        - N=10 selected-candidate diagnostics.
        - N=100 matched confirmation analysis.
        - unit tests in ``test_sla_compliance_analysis.py``.
    """
    if "trajectory" not in all_trajectory_ledgers.columns:
        raise ValueError("all_trajectory_ledgers must contain trajectory")
    decisions: list[pd.DataFrame] = []
    for trajectory, ledger in all_trajectory_ledgers.groupby("trajectory", sort=True):
        table = build_request_sla_decision_table(
            ledger,
            latency_threshold,
            cost_threshold,
            quality_threshold,
            stop_time,
        )
        table.insert(0, "trajectory", trajectory)
        if "seed" in ledger.columns:
            table.insert(1, "seed", int(ledger["seed"].iloc[0]))
        decisions.append(table)
    all_decisions = pd.concat(decisions, ignore_index=True)
    per_trajectory = [
        frame.drop(columns=["trajectory", "seed"], errors="ignore")
        for _, frame in all_decisions.groupby("trajectory", sort=True)
    ]
    sigma, trajectory_curves = calculate_empirical_sla_sigma_from_decision_tables(
        per_trajectory, horizons, sla_definition
    )
    trajectory_ids = sorted(all_decisions["trajectory"].unique())
    trajectory_curves["trajectory"] = trajectory_curves["trajectory"].map(
        dict(enumerate(trajectory_ids))
    )
    return sigma, trajectory_curves, all_decisions


def calculate_exact_sla_sigma_step_curve(
    decision_tables: list[pd.DataFrame],
    sla_definition: SlaComplianceDefinition,
    horizon_min: float,
    horizon_max: float,
) -> pd.DataFrame:
    """Build exact transition-time coordinates for empirical SLA sigma.

    Only times where at least one trajectory changes SLA-compliant state are
    retained, so the plot remains compact even when many requests are decided.

    Called by:
        - ``analyze_and_plot_n100_confirmation`` in
          ``run_n100_matched_confirmation.py``.
        - selected-candidate diagnostics.
    """
    start = float(horizon_min)
    stop = float(horizon_max)
    if not decision_tables:
        raise ValueError("at least one trajectory decision table is required")

    deltas: Counter[float] = Counter()
    initial_pass_count = 0
    for table in decision_tables:
        decided = table[table["decision_time"].notna()].copy()
        grouped = (
            decided.groupby("decision_time", sort=True)["compliant"]
            .agg(["count", lambda values: int(pd.Series(values).fillna(False).astype(bool).sum())])
            .reset_index()
        )
        grouped.columns = ["decision_time", "n_decisions", "n_compliant"]

        prior = grouped[grouped["decision_time"].astype(float) <= start + EVENT_TOLERANCE]
        n_decided = int(prior["n_decisions"].sum())
        n_compliant = int(prior["n_compliant"].sum())
        fraction = (
            float(sla_definition.zero_decision_compliance)
            if n_decided == 0
            else float(n_compliant / n_decided)
        )
        state = bool(fraction + EVENT_TOLERANCE >= sla_definition.rho)
        initial_pass_count += int(state)

        future = grouped[
            (grouped["decision_time"].astype(float) > start + EVENT_TOLERANCE)
            & (grouped["decision_time"].astype(float) <= stop + EVENT_TOLERANCE)
        ]
        for row in future.itertuples(index=False):
            previous = state
            n_decided += int(row.n_decisions)
            n_compliant += int(row.n_compliant)
            state = bool(
                (n_compliant / n_decided) + EVENT_TOLERANCE >= sla_definition.rho
            )
            if state != previous:
                deltas[float(row.decision_time)] += 1 if state else -1

    n = len(decision_tables)
    rows = [{"horizon": start, "sigma": float(initial_pass_count / n)}]
    passing = initial_pass_count
    for time in sorted(deltas):
        passing += int(deltas[time])
        rows.append({"horizon": float(time), "sigma": float(passing / n)})
    if rows[-1]["horizon"] < stop - EVENT_TOLERANCE:
        rows.append({"horizon": stop, "sigma": rows[-1]["sigma"]})
    return pd.DataFrame(rows)


def summarize_request_level_sla_outcomes(
    all_request_decisions: pd.DataFrame,
) -> dict[str, float | int]:
    """Summarize all decided request outcomes without first-failure reduction.

    Called by:
        - N=10 candidate diagnostics.
        - N=100 confirmation summaries.
    """
    decided = all_request_decisions[
        all_request_decisions["decision_status"].astype(str) == "decided"
    ]
    unresolved_count = int(
        (all_request_decisions["decision_status"].astype(str) == "unresolved").sum()
    )
    n_decided = int(len(decided))
    n_compliant = int(decided["compliant"].fillna(False).astype(bool).sum())
    n_failed = n_decided - n_compliant
    latency_failures = int(decided["latency_failed"].astype(bool).sum())
    cost_failures = int(decided["cost_failed"].astype(bool).sum())
    quality_failures = int(decided["quality_failed"].astype(bool).sum())
    lc_total = latency_failures + cost_failures
    return {
        "decided_request_count": n_decided,
        "unresolved_request_count": unresolved_count,
        "compliant_request_count": n_compliant,
        "failed_request_count": n_failed,
        "request_compliance_fraction": (
            float(n_compliant / n_decided) if n_decided else 1.0
        ),
        "latency_failure_count": latency_failures,
        "cost_failure_count": cost_failures,
        "quality_failure_count": quality_failures,
        "latency_failure_fraction_of_lc": (
            float(latency_failures / lc_total) if lc_total else float("nan")
        ),
        "cost_failure_fraction_of_lc": (
            float(cost_failures / lc_total) if lc_total else float("nan")
        ),
    }


def calculate_pointwise_sigma_standard_error(sigma: float, n_trajectories: int) -> float:
    """Return the binomial Monte Carlo SE of sigma at one fixed horizon.

    Called by:
        - N=100 confirmation summary generation.
    """
    probability = float(sigma)
    n = int(n_trajectories)
    if n <= 0:
        raise ValueError("n_trajectories must be positive")
    return float(sqrt(probability * (1.0 - probability) / n))
