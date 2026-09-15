"""Pure helpers for the Phase-3 M1-v2 direct full-I1 inverse lift.

M1-v2 searches the native simulator-compatible parameter vector
theta_i=(mean_service_time, cost_rate, service_cv) directly against the
complete public I1 sigma surface. This module contains only deterministic
bookkeeping: search-bound construction, tolerant surface alignment, loss
calculation, and boundary diagnostics. It does not read any white-box data.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt
from typing import Any, Mapping

import numpy as np
import pandas as pd

FLOAT_KEY_TOLERANCE = 1e-12


@dataclass(frozen=True)
class M1V2SearchBounds:
    mean_service_time_lower: float
    mean_service_time_upper: float
    cost_rate_lower: float
    cost_rate_upper: float
    service_cv_lower: float
    service_cv_upper: float
    cost_rate_public_reference: float

    def as_dict(self) -> dict[str, float]:
        return {
            "mean_service_time_lower": float(self.mean_service_time_lower),
            "mean_service_time_upper": float(self.mean_service_time_upper),
            "cost_rate_lower": float(self.cost_rate_lower),
            "cost_rate_upper": float(self.cost_rate_upper),
            "service_cv_lower": float(self.service_cv_lower),
            "service_cv_upper": float(self.service_cv_upper),
            "cost_rate_public_reference": float(self.cost_rate_public_reference),
        }


def public_cost_rate_reference(metadata: Mapping[str, object]) -> float:
    """Derive only a search scale from the public A_i latency/cost boundaries."""
    regions = metadata.get("rho_conditioned_regions")
    if not isinstance(regions, list) or not regions:
        raise ValueError("public card lacks rho_conditioned_regions")

    ratios: list[float] = []
    for region_object in regions:
        if not isinstance(region_object, Mapping):
            raise ValueError("public rho_conditioned_regions must contain mappings")
        latency = max(float(region_object["l_max"]), FLOAT_KEY_TOLERANCE)
        cost = float(region_object["c_max"])
        ratios.append(cost / latency)

    reference = float(np.median(np.asarray(ratios, dtype=float)))
    if not np.isfinite(reference) or reference <= 0.0:
        raise RuntimeError(
            "public A_i boundaries do not define a positive cost-rate search scale"
        )
    return reference


def build_search_bounds(
    metadata: Mapping[str, object],
    contract: Mapping[str, Any],
) -> M1V2SearchBounds:
    """Materialize M1-v2 bounds using only W_i, public A_i, and the contract."""
    workload = metadata.get("workload_contract")
    if not isinstance(workload, Mapping):
        raise ValueError("public I1 metadata lacks workload_contract")
    period = float(workload["period"])
    if not np.isfinite(period) or period <= 0.0:
        raise ValueError("public workload period must be positive")

    joint = contract.get("joint_full_surface_lift")
    if not isinstance(joint, Mapping):
        raise ValueError("M1-v2 contract lacks joint_full_surface_lift")
    optimization = joint.get("optimization")
    if not isinstance(optimization, Mapping):
        raise ValueError("M1-v2 contract lacks joint optimization")
    search_space = optimization.get("search_space")
    if not isinstance(search_space, Mapping):
        raise ValueError("M1-v2 contract lacks optimization.search_space")

    mu_factor_lower, mu_factor_upper = map(
        float, search_space["mu_over_workload_period_bounds"]
    )
    kappa_factor_lower, kappa_factor_upper = map(
        float, search_space["cost_rate_reference_multiplier_bounds"]
    )
    cv_lower, cv_upper = map(float, search_space["cv_bounds"])

    reference = public_cost_rate_reference(metadata)
    bounds = M1V2SearchBounds(
        mean_service_time_lower=mu_factor_lower * period,
        mean_service_time_upper=mu_factor_upper * period,
        cost_rate_lower=kappa_factor_lower * reference,
        cost_rate_upper=kappa_factor_upper * reference,
        service_cv_lower=cv_lower,
        service_cv_upper=cv_upper,
        cost_rate_public_reference=reference,
    )
    if not (
        0.0 < bounds.mean_service_time_lower < bounds.mean_service_time_upper
        and 0.0 < bounds.cost_rate_lower < bounds.cost_rate_upper
        and 0.0 <= bounds.service_cv_lower < bounds.service_cv_upper
    ):
        raise ValueError(f"invalid M1-v2 search bounds: {bounds}")
    return bounds


def _prepare_surface_for_alignment(
    surface: pd.DataFrame,
    *,
    sigma_name: str,
    rho_name: str,
    region_rho_name: str,
    exclude_horizon_zero: bool,
) -> pd.DataFrame:
    required = {
        "provider_id",
        "region_id",
        "region_rho",
        "rho",
        "horizon",
        "sigma_hat",
    }
    missing = sorted(required.difference(surface.columns))
    if missing:
        raise ValueError(
            f"sigma surface lacks required fields: {', '.join(missing)}"
        )

    frame = surface[
        ["provider_id", "region_id", "region_rho", "rho", "horizon", "sigma_hat"]
    ].copy()
    if exclude_horizon_zero:
        frame = frame[
            frame["horizon"].astype(float) > FLOAT_KEY_TOLERANCE
        ].copy()

    sigma = frame["sigma_hat"].astype(float).to_numpy()
    if not np.all(np.isfinite(sigma)):
        raise ValueError("sigma surface contains non-finite sigma_hat")
    if np.any(sigma < -FLOAT_KEY_TOLERANCE) or np.any(
        sigma > 1.0 + FLOAT_KEY_TOLERANCE
    ):
        raise ValueError("sigma_hat must lie in [0,1]")

    base_keys = ["provider_id", "region_id", "horizon"]
    frame = frame.sort_values(base_keys + ["rho"]).reset_index(drop=True)
    frame["_rho_ordinal"] = frame.groupby(base_keys, sort=False).cumcount()
    frame = frame.rename(
        columns={
            "region_rho": region_rho_name,
            "rho": rho_name,
            "sigma_hat": sigma_name,
        }
    )
    return frame


def calculate_full_surface_loss(
    public_surface: pd.DataFrame,
    simulated_surface: pd.DataFrame,
    *,
    exclude_horizon_zero: bool = True,
) -> tuple[dict[str, float], pd.DataFrame]:
    """Uniform full-I1 sigma-surface loss with tolerant floating-key auditing."""
    public = _prepare_surface_for_alignment(
        public_surface,
        sigma_name="sigma_i1",
        rho_name="rho_i1",
        region_rho_name="region_rho_i1",
        exclude_horizon_zero=exclude_horizon_zero,
    )
    simulated = _prepare_surface_for_alignment(
        simulated_surface,
        sigma_name="sigma_m1_local",
        rho_name="rho_m1",
        region_rho_name="region_rho_m1",
        exclude_horizon_zero=exclude_horizon_zero,
    )

    if len(public) != len(simulated):
        raise RuntimeError(
            "M1-v2 simulated surface point count differs from public I1"
        )

    base_keys = ["provider_id", "region_id", "horizon"]
    public_counts = (
        public.groupby(base_keys, sort=True)["_rho_ordinal"]
        .size()
        .rename("n_public")
        .reset_index()
    )
    simulated_counts = (
        simulated.groupby(base_keys, sort=True)["_rho_ordinal"]
        .size()
        .rename("n_simulated")
        .reset_index()
    )
    counts = public_counts.merge(
        simulated_counts,
        on=base_keys,
        how="outer",
        validate="one_to_one",
    )
    if (
        counts[["n_public", "n_simulated"]].isna().any().any()
        or not np.array_equal(
            counts["n_public"].astype(int).to_numpy(),
            counts["n_simulated"].astype(int).to_numpy(),
        )
    ):
        raise RuntimeError(
            "M1-v2 query-rho support count differs for at least one public key"
        )

    match_keys = base_keys + ["_rho_ordinal"]
    comparison = public.merge(
        simulated,
        on=match_keys,
        how="left",
        validate="one_to_one",
    )
    if comparison["sigma_m1_local"].isna().any():
        raise RuntimeError("M1-v2 simulated surface does not cover every public point")
    if len(comparison) != len(public):
        raise RuntimeError("M1-v2 comparison changed the public point count")

    region_match = np.isclose(
        comparison["region_rho_i1"].astype(float),
        comparison["region_rho_m1"].astype(float),
        atol=FLOAT_KEY_TOLERANCE,
        rtol=0.0,
    )
    if not bool(np.all(region_match)):
        raise RuntimeError(
            "M1-v2 region_rho values disagree between public and simulated surfaces"
        )

    rho_match = np.isclose(
        comparison["rho_i1"].astype(float),
        comparison["rho_m1"].astype(float),
        atol=FLOAT_KEY_TOLERANCE,
        rtol=0.0,
    )
    if not bool(np.all(rho_match)):
        raise RuntimeError(
            "M1-v2 query-rho values disagree between public and simulated surfaces"
        )

    comparison["region_rho"] = comparison["region_rho_i1"].astype(float)
    comparison["rho"] = comparison["rho_i1"].astype(float)
    comparison = comparison.drop(
        columns=[
            "_rho_ordinal",
            "region_rho_i1",
            "region_rho_m1",
            "rho_i1",
            "rho_m1",
        ]
    )

    error = (
        comparison["sigma_m1_local"].astype(float)
        - comparison["sigma_i1"].astype(float)
    )
    comparison["error"] = error
    comparison["abs_error"] = error.abs()
    comparison["squared_error"] = error**2

    error_values = error.to_numpy(dtype=float)
    metrics = {
        "n_points": int(len(comparison)),
        "mse": float(np.mean(np.square(error_values))),
        "rmse": float(sqrt(np.mean(np.square(error_values)))),
        "mae": float(np.mean(np.abs(error_values))),
        "bias": float(np.mean(error_values)),
        "max_abs_error": float(np.max(np.abs(error_values))),
    }
    return metrics, comparison.sort_values(
        ["region_rho", "rho", "horizon"]
    ).reset_index(drop=True)


def _normalized_linear(value: float, lower: float, upper: float) -> float:
    return float((float(value) - float(lower)) / (float(upper) - float(lower)))


def _normalized_log(value: float, lower: float, upper: float) -> float:
    if value <= 0.0 or lower <= 0.0 or upper <= 0.0:
        raise ValueError("log-normalized search coordinates require positive values")
    return float(
        (log(float(value)) - log(float(lower)))
        / (log(float(upper)) - log(float(lower)))
    )


def boundary_diagnostics(
    *,
    mean_service_time: float,
    cost_rate: float,
    service_cv: float,
    bounds: M1V2SearchBounds,
    boundary_fraction: float,
) -> dict[str, object]:
    """Report near-boundary positions in the coordinates used by the optimizer."""
    fraction = float(boundary_fraction)
    if not 0.0 < fraction < 0.5:
        raise ValueError("boundary_fraction must lie in (0,0.5)")

    positions = {
        "mean_service_time": _normalized_log(
            mean_service_time,
            bounds.mean_service_time_lower,
            bounds.mean_service_time_upper,
        ),
        "cost_rate": _normalized_log(
            cost_rate,
            bounds.cost_rate_lower,
            bounds.cost_rate_upper,
        ),
        "service_cv": _normalized_linear(
            service_cv,
            bounds.service_cv_lower,
            bounds.service_cv_upper,
        ),
    }
    near = {
        name: bool(position <= fraction or position >= 1.0 - fraction)
        for name, position in positions.items()
    }
    return {
        "boundary_fraction": fraction,
        "normalized_search_positions": positions,
        "near_boundary": near,
        "any_near_boundary": bool(any(near.values())),
    }
