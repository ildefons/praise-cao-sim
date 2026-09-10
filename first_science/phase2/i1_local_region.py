"""Provider-local A_i construction from frozen traces under the anchor query.

Scientific rule
---------------
This module implements the already-agreed Phase-2 calibration rule in the
current cumulative-admissibility semantics.

For each provider i and each coordinate separately, candidate thresholds are
scanned offline on the frozen local trace bank T_i.  For one candidate threshold
we form the coordinate-only local admissibility query and compute

    sigma_i(A_i^X,H;rho_anchor) = P(c_i(A_i^X,H) >= rho_anchor).

The chosen threshold is the candidate whose *first* crossing below the frozen
probability target sigma_target=0.95 is closest to H*=120 s.  Latency and cost
are calibrated independently.  If quality is constant on the frozen trace bank,
as in the current anchor, its unique observed value is used directly rather than
inventing an artificial quality threshold.

The final rectangular boundary is

    A_i = {L_i <= l_i*, C_i <= c_i*, Q_i >= q_i*}.

The joint sigma curve of that rectangle is not forced to equal 0.95 at H*=120.
That is intentional: the 0.95-at-120 rule calibrates each coordinate, then the
coordinates are combined.

Important distinctions
----------------------
* rho_anchor is the already-frozen global anchor query tolerance used during
  trace calibration.  It is not a provider-specific rho_i selected by M0.
* I1 still exposes the complete frozen rho support after A_i is constructed.
* No A_G boundary, M0/M1 result, request-level percentile target, or hidden
  generator parameter enters this module.
"""
from __future__ import annotations

from typing import Callable, Mapping

import numpy as np
import pandas as pd

EVENT_TOLERANCE = 1e-12
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
REQUIRED_COLUMNS = {"trajectory", "emission", "completion", "L", "C", "Q"}
DEFAULT_ANCHOR_HORIZON = 120.0
DEFAULT_SIGMA_TARGET = 0.95


def _numeric(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)


def _finite_unique_values(series: pd.Series, *, descending: bool = False) -> np.ndarray:
    values = _numeric(series)
    values = np.unique(values[np.isfinite(values)])
    if len(values) == 0:
        raise ValueError("cannot calibrate a coordinate with no finite observations")
    values.sort()
    if descending:
        values = values[::-1]
    return values


def _validate_calibration_inputs(
    ledger: pd.DataFrame,
    rho_anchor: float,
    horizons: list[float],
    stop_time: float,
    anchor_horizon: float,
    sigma_target: float,
) -> None:
    missing = REQUIRED_COLUMNS.difference(ledger.columns)
    if missing:
        raise ValueError(
            "provider ledger missing columns: " + ", ".join(sorted(missing))
        )
    if ledger.empty or int(ledger["trajectory"].nunique()) <= 0:
        raise ValueError("provider ledger must contain at least one trajectory")
    if not 0.0 < float(rho_anchor) <= 1.0:
        raise ValueError("rho_anchor must lie in (0,1]")
    if not 0.0 < float(sigma_target) <= 1.0:
        raise ValueError("sigma_target must lie in (0,1]")
    if not horizons or horizons != sorted(horizons):
        raise ValueError("horizons must be a non-empty sorted list")
    if float(horizons[0]) < -EVENT_TOLERANCE:
        raise ValueError("horizons must begin at or after t=0")
    if float(horizons[-1]) > float(stop_time) + EVENT_TOLERANCE:
        raise ValueError("horizons must not exceed stop_time")
    if not any(
        abs(float(horizon) - float(anchor_horizon)) <= EVENT_TOLERANCE
        for horizon in horizons
    ):
        raise ValueError("anchor_horizon must be present in the horizon grid")


def _coordinate_sigma_curve(
    ledger: pd.DataFrame,
    coordinate: str,
    threshold: float,
    rho_anchor: float,
    horizons: list[float],
    stop_time: float,
) -> pd.DataFrame:
    """Compute one exact coordinate-only cumulative-admissibility sigma curve.

    This is a vectorized implementation of the same request-accounting semantics
    used by the I1 card builder.  For latency, a request is decided at completion
    when it completes by its local deadline and otherwise at that deadline.  For
    cost or quality calibration latency is unconstrained, so only completed
    requests are decided and unresolved requests remain outside c_i(H).
    """
    axis = str(coordinate).upper()
    if axis not in {"L", "C", "Q"}:
        raise ValueError("coordinate must be one of L, C or Q")

    horizon_values = np.asarray(horizons, dtype=float)
    n_trajectories = int(ledger["trajectory"].nunique())
    successes = np.zeros(len(horizon_values), dtype=int)

    for _, trajectory in ledger.groupby("trajectory", sort=True):
        emission = _numeric(trajectory["emission"])
        completion = _numeric(trajectory["completion"])

        if axis == "L":
            deadline = emission + float(threshold)
            completed_in_time = np.isfinite(completion) & (
                completion <= deadline + EVENT_TOLERANCE
            )
            decision_time = np.where(completed_in_time, completion, deadline)
            admissible = completed_in_time
        elif axis == "C":
            cost = _numeric(trajectory["C"])
            decision_time = completion
            admissible = (
                np.isfinite(completion)
                & np.isfinite(cost)
                & (cost <= float(threshold) + EVENT_TOLERANCE)
            )
        else:
            quality = _numeric(trajectory["Q"])
            decision_time = completion
            admissible = (
                np.isfinite(completion)
                & np.isfinite(quality)
                & (quality + EVENT_TOLERANCE >= float(threshold))
            )

        observable = np.isfinite(decision_time) & (
            decision_time <= float(stop_time) + EVENT_TOLERANCE
        )
        times = decision_time[observable]
        flags = admissible[observable].astype(int)

        if len(times) == 0:
            # Frozen zero-decision convention: c_i(H)=1 before any decision.
            successes += 1
            continue

        order = np.argsort(times, kind="mergesort")
        times = times[order]
        flags = flags[order]
        prefix = np.concatenate(([0], np.cumsum(flags, dtype=int)))
        decided = np.searchsorted(
            times,
            horizon_values + EVENT_TOLERANCE,
            side="right",
        )
        compliant = prefix[decided]
        fractions = np.ones(len(horizon_values), dtype=float)
        nonzero = decided > 0
        fractions[nonzero] = compliant[nonzero] / decided[nonzero]
        successes += (
            fractions + EVENT_TOLERANCE >= float(rho_anchor)
        ).astype(int)

    return pd.DataFrame(
        {
            "horizon": horizon_values,
            "sigma": successes.astype(float) / float(n_trajectories),
        }
    )


def _first_crossing_below_target(
    sigma_curve: pd.DataFrame,
    sigma_target: float,
) -> float | None:
    """Return the first grid horizon where sigma is strictly below target."""
    below = sigma_curve[
        sigma_curve["sigma"].astype(float) < float(sigma_target) - EVENT_TOLERANCE
    ]
    if below.empty:
        return None
    return float(below.iloc[0]["horizon"])


def _sigma_at_horizon(sigma_curve: pd.DataFrame, horizon: float) -> float:
    selected = sigma_curve[
        np.isclose(
            sigma_curve["horizon"].astype(float),
            float(horizon),
            atol=EVENT_TOLERANCE,
        )
    ]
    if len(selected) != 1:
        raise RuntimeError("expected exactly one sigma point at anchor horizon")
    return float(selected.iloc[0]["sigma"])


def _choose_threshold_by_first_crossing(
    *,
    candidate_thresholds_in_relaxation_order: np.ndarray,
    evaluate_curve: Callable[[float], pd.DataFrame],
    anchor_horizon: float,
    sigma_target: float,
) -> tuple[float, dict[str, object]]:
    """Choose the candidate whose first sub-target crossing is closest to H*.

    Candidates must be ordered from stricter to more relaxed.  Pointwise sigma
    is then non-decreasing along the candidate list, so the first crossing below
    sigma_target moves weakly later.  Binary search finds the transition around
    H* without scanning every observed threshold.
    """
    candidates = np.asarray(candidate_thresholds_in_relaxation_order, dtype=float)
    if len(candidates) == 0:
        raise ValueError("at least one candidate threshold is required")

    cache: dict[int, tuple[pd.DataFrame, float | None, float]] = {}

    def evaluate(index: int) -> tuple[pd.DataFrame, float | None, float]:
        if index not in cache:
            curve = evaluate_curve(float(candidates[index]))
            crossing = _first_crossing_below_target(curve, sigma_target)
            sigma_anchor = _sigma_at_horizon(curve, anchor_horizon)
            cache[index] = (curve, crossing, sigma_anchor)
        return cache[index]

    # Find the first relaxed-enough candidate whose first crossing is at/after
    # H*, or which never crosses below the target on the frozen horizon domain.
    low = 0
    high = len(candidates)
    while low < high:
        mid = (low + high) // 2
        _, crossing, _ = evaluate(mid)
        if crossing is None or crossing >= float(anchor_horizon) - EVENT_TOLERANCE:
            high = mid
        else:
            low = mid + 1

    bracket_indices: set[int] = set()
    for index in range(low - 2, low + 3):
        if 0 <= index < len(candidates):
            bracket_indices.add(index)
    if low >= len(candidates):
        bracket_indices.update(
            range(max(0, len(candidates) - 3), len(candidates))
        )

    finite_crossing_candidates: list[tuple[float, int, float, float]] = []
    no_crossing_candidates: list[tuple[float, int, float]] = []
    for index in sorted(bracket_indices):
        _, crossing, sigma_anchor = evaluate(index)
        threshold = float(candidates[index])
        if crossing is None:
            no_crossing_candidates.append(
                (abs(sigma_anchor - float(sigma_target)), index, threshold)
            )
        else:
            finite_crossing_candidates.append(
                (
                    abs(float(crossing) - float(anchor_horizon)),
                    index,
                    threshold,
                    float(crossing),
                )
            )

    if finite_crossing_candidates:
        # Primary frozen rule: crossing closest to H*.  Deterministic tie-break:
        # the stricter candidate (lower relaxation-order index).
        _, chosen_index, chosen_threshold, chosen_crossing = min(
            finite_crossing_candidates,
            key=lambda item: (item[0], item[1]),
        )
        chosen_curve, _, chosen_sigma_anchor = evaluate(chosen_index)
        selection_mode = "first_crossing_below_sigma_target_closest_to_H_star"
    else:
        # This is a diagnostic fallback only for a coordinate that has no valid
        # crossing anywhere near the transition.  The current constant-Q anchor
        # is handled separately and never reaches this path.
        _, chosen_index, chosen_threshold = min(
            no_crossing_candidates,
            key=lambda item: (item[0], item[1]),
        )
        chosen_curve, _, chosen_sigma_anchor = evaluate(chosen_index)
        chosen_crossing = None
        selection_mode = "no_finite_crossing_choose_sigma_at_H_star_closest_to_target"

    return chosen_threshold, {
        "threshold": float(chosen_threshold),
        "first_crossing_below_target": chosen_crossing,
        "sigma_at_H_star": float(chosen_sigma_anchor),
        "crossing_distance_to_H_star": (
            None
            if chosen_crossing is None
            else abs(float(chosen_crossing) - float(anchor_horizon))
        ),
        "candidate_index_relaxation_order": int(chosen_index),
        "n_candidate_thresholds": int(len(candidates)),
        "selection_mode": selection_mode,
        "evaluated_candidate_count": int(len(cache)),
        "curve": chosen_curve,
    }


def calibrate_coordinate_threshold(
    *,
    ledger: pd.DataFrame,
    coordinate: str,
    rho_anchor: float,
    horizons: list[float],
    stop_time: float,
    anchor_horizon: float = DEFAULT_ANCHOR_HORIZON,
    sigma_target: float = DEFAULT_SIGMA_TARGET,
) -> tuple[float, dict[str, object]]:
    """Calibrate one L/C/Q threshold from T_i under the frozen anchor rule."""
    _validate_calibration_inputs(
        ledger,
        rho_anchor,
        horizons,
        stop_time,
        anchor_horizon,
        sigma_target,
    )
    axis = str(coordinate).upper()
    if axis not in {"L", "C", "Q"}:
        raise ValueError("coordinate must be one of L, C or Q")

    values = _finite_unique_values(ledger[axis], descending=(axis == "Q"))

    if axis == "Q" and len(values) == 1:
        threshold = float(values[0])
        curve = _coordinate_sigma_curve(
            ledger,
            axis,
            threshold,
            rho_anchor,
            horizons,
            stop_time,
        )
        diagnostics = {
            "threshold": threshold,
            "first_crossing_below_target": _first_crossing_below_target(
                curve, sigma_target
            ),
            "sigma_at_H_star": _sigma_at_horizon(curve, anchor_horizon),
            "crossing_distance_to_H_star": None,
            "candidate_index_relaxation_order": 0,
            "n_candidate_thresholds": 1,
            "selection_mode": "constant_observed_quality_use_unique_value",
            "evaluated_candidate_count": 1,
            "curve": curve,
        }
        return threshold, diagnostics

    def evaluate(threshold: float) -> pd.DataFrame:
        return _coordinate_sigma_curve(
            ledger,
            axis,
            threshold,
            rho_anchor,
            horizons,
            stop_time,
        )

    return _choose_threshold_by_first_crossing(
        candidate_thresholds_in_relaxation_order=values,
        evaluate_curve=evaluate,
        anchor_horizon=anchor_horizon,
        sigma_target=sigma_target,
    )


def derive_provider_local_region(
    provider_id: str,
    ledger: pd.DataFrame,
    rho_anchor: float,
    horizons: list[float],
    stop_time: float,
    anchor_horizon: float = DEFAULT_ANCHOR_HORIZON,
    sigma_target: float = DEFAULT_SIGMA_TARGET,
) -> tuple[dict[str, object], dict[str, object]]:
    """Derive one provider-specific rectangular A_i from its frozen T_i."""
    calibrations: dict[str, dict[str, object]] = {}
    thresholds: dict[str, float] = {}
    for coordinate in ("L", "C", "Q"):
        threshold, diagnostic = calibrate_coordinate_threshold(
            ledger=ledger,
            coordinate=coordinate,
            rho_anchor=rho_anchor,
            horizons=horizons,
            stop_time=stop_time,
            anchor_horizon=anchor_horizon,
            sigma_target=sigma_target,
        )
        thresholds[coordinate] = threshold
        calibrations[coordinate] = diagnostic

    region = {
        "region_id": f"{provider_id}_COORD_SIGMA_H120_ANCHOR_V1",
        "l_max": float(thresholds["L"]),
        "c_max": float(thresholds["C"]),
        "q_min": float(thresholds["Q"]),
    }
    diagnostics = {
        "provider": str(provider_id),
        "rho_anchor": float(rho_anchor),
        "H_star": float(anchor_horizon),
        "sigma_target": float(sigma_target),
        "l_max": region["l_max"],
        "c_max": region["c_max"],
        "q_min": region["q_min"],
        "L_first_crossing": calibrations["L"]["first_crossing_below_target"],
        "L_sigma_at_H_star": calibrations["L"]["sigma_at_H_star"],
        "L_candidates": calibrations["L"]["n_candidate_thresholds"],
        "L_evaluated": calibrations["L"]["evaluated_candidate_count"],
        "C_first_crossing": calibrations["C"]["first_crossing_below_target"],
        "C_sigma_at_H_star": calibrations["C"]["sigma_at_H_star"],
        "C_candidates": calibrations["C"]["n_candidate_thresholds"],
        "C_evaluated": calibrations["C"]["evaluated_candidate_count"],
        "Q_first_crossing": calibrations["Q"]["first_crossing_below_target"],
        "Q_sigma_at_H_star": calibrations["Q"]["sigma_at_H_star"],
        "Q_candidates": calibrations["Q"]["n_candidate_thresholds"],
        "Q_evaluated": calibrations["Q"]["evaluated_candidate_count"],
        "Q_selection_mode": calibrations["Q"]["selection_mode"],
        "rule": "coordinate_first_sigma_crossing_below_0p95_closest_to_H120",
    }
    return region, diagnostics


def derive_local_regions_from_traces(
    provider_ledgers: Mapping[str, pd.DataFrame],
    rho_anchor: float,
    horizons: list[float],
    stop_time: float,
    anchor_horizon: float = DEFAULT_ANCHOR_HORIZON,
    sigma_target: float = DEFAULT_SIGMA_TARGET,
) -> tuple[dict[str, dict[str, object]], pd.DataFrame]:
    """Derive A_A,A_B,A_C independently from their frozen provider traces."""
    if set(provider_ledgers) != set(PROVIDERS):
        raise ValueError("provider ledgers must contain exactly ProviderA/B/C")

    regions: dict[str, dict[str, object]] = {}
    diagnostics: list[dict[str, object]] = []
    for provider in PROVIDERS:
        region, row = derive_provider_local_region(
            provider,
            provider_ledgers[provider],
            rho_anchor,
            horizons,
            stop_time,
            anchor_horizon,
            sigma_target,
        )
        regions[provider] = region
        diagnostics.append(row)

    return regions, pd.DataFrame(diagnostics)
