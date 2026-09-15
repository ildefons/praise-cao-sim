"""Simulator-independent objectives for the PRAISE Phase-3 M1 provider lift.

M1 consumes only the frozen public rho-conditioned I1 provider cards. The
provider lift is deliberately staged:

1. Deterministic nominal lift: infer the central location of each public
   compliance-fraction distribution from the exposed query-rho survival slice,
   then fit the native single-provider surrogate's mean service time and cost
   rate to that central behaviour.
2. Stochastic variability lift: keep the Stage-1 parameters fixed, introduce a
   Gamma service-time CV, and fit that single variability parameter to the full
   public I1 sigma surface.

This module contains no white-box access and no AICon/YAFS dependency. It is
therefore suitable for regression-testing the scientific fitting contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np
import pandas as pd

TOLERANCE = 1e-12
CENTRAL_SURVIVAL_PROBABILITY = 0.5


@dataclass(frozen=True)
class M1PilotSurrogate:
    """Minimal pilot surrogate recovered from public I1 only."""

    provider_id: str
    mean_service_time: float
    cost_rate: float
    service_cv: float

    def __post_init__(self) -> None:
        if not str(self.provider_id).strip():
            raise ValueError("provider_id must be non-empty")
        if self.mean_service_time <= 0.0:
            raise ValueError("mean_service_time must be positive")
        if self.cost_rate < 0.0:
            raise ValueError("cost_rate must be non-negative")
        if self.service_cv < 0.0:
            raise ValueError("service_cv must be non-negative")


@dataclass(frozen=True)
class SearchResult:
    """One best point plus the full candidate table from a grid search."""

    best_parameters: dict[str, float]
    best_loss: float
    candidates: pd.DataFrame


def _validate_public_surface_for_median_inference(surface: pd.DataFrame) -> None:
    required = {
        "provider_id",
        "region_id",
        "region_rho",
        "rho",
        "horizon",
        "sigma_hat",
    }
    missing = required.difference(surface.columns)
    if missing:
        raise ValueError(
            "public I1 surface missing median-inference columns: "
            + ", ".join(sorted(missing))
        )
    if surface.empty:
        raise ValueError("public I1 surface is empty")
    if np.any(~np.isfinite(surface["sigma_hat"].astype(float))):
        raise ValueError("public I1 sigma_hat must be finite")
    if np.any(
        (surface["sigma_hat"].astype(float) < -TOLERANCE)
        | (surface["sigma_hat"].astype(float) > 1.0 + TOLERANCE)
    ):
        raise ValueError("public I1 sigma_hat must lie in [0,1]")


def _infer_one_median_target(
    ordered_slice: pd.DataFrame,
    central_probability: float,
) -> dict[str, object]:
    """Infer one central compliance target from a sampled survival function.

    At fixed provider, A_i and H, the public map

        rho_query -> sigma_i(A_i,H;rho_query)

    is the sampled survival function P(C_i(H)>=rho_query) of the random
    cumulative compliance fraction C_i(H). The Stage-1 deterministic surrogate
    targets the median of that distribution.
    """
    ordered = ordered_slice.sort_values("rho").reset_index(drop=True)
    rho = ordered["rho"].astype(float).to_numpy()
    sigma = ordered["sigma_hat"].astype(float).to_numpy()
    if len(rho) < 2:
        raise ValueError("median inference requires at least two query-rho points")
    if np.any(np.diff(rho) <= 0.0):
        raise ValueError("query-rho support must be strictly increasing")
    if np.any(sigma[:-1] + TOLERANCE < sigma[1:]):
        raise ValueError("sigma must be non-increasing in query rho")

    p = float(central_probability)
    if not 0.0 < p < 1.0:
        raise ValueError("central_probability must lie strictly inside (0,1)")

    # Entire observed support lies above the central probability. The median is
    # at or above the largest exposed query threshold.
    if sigma[-1] >= p - TOLERANCE:
        return {
            "target_kind": "lower_censored",
            "median_target": np.nan,
            "lower_bound": float(rho[-1]),
            "upper_bound": np.nan,
            "bracket_rho_low": float(rho[-1]),
            "bracket_rho_high": np.nan,
        }

    # Even the least demanding exposed threshold has survival below p. The
    # median lies below the observed support.
    if sigma[0] < p - TOLERANCE:
        return {
            "target_kind": "upper_censored",
            "median_target": np.nan,
            "lower_bound": np.nan,
            "upper_bound": float(rho[0]),
            "bracket_rho_low": np.nan,
            "bracket_rho_high": float(rho[0]),
        }

    exact = np.flatnonzero(np.isclose(sigma, p, atol=TOLERANCE, rtol=0.0))
    if len(exact):
        # Empirical survival surfaces can contain a flat sigma=0.5 plateau. Its
        # midpoint is a deterministic convention for the nominal Stage-1 target.
        lo = float(rho[int(exact[0])])
        hi = float(rho[int(exact[-1])])
        return {
            "target_kind": "point",
            "median_target": 0.5 * (lo + hi),
            "lower_bound": np.nan,
            "upper_bound": np.nan,
            "bracket_rho_low": lo,
            "bracket_rho_high": hi,
        }

    for index in range(len(rho) - 1):
        s_lo = float(sigma[index])
        s_hi = float(sigma[index + 1])
        if s_lo > p and s_hi < p:
            r_lo = float(rho[index])
            r_hi = float(rho[index + 1])
            # Linear interpolation is intentionally only a Stage-1 central-
            # location convention. It does not create new public sigma queries.
            weight = (s_lo - p) / (s_lo - s_hi)
            target = r_lo + weight * (r_hi - r_lo)
            return {
                "target_kind": "point",
                "median_target": float(target),
                "lower_bound": np.nan,
                "upper_bound": np.nan,
                "bracket_rho_low": r_lo,
                "bracket_rho_high": r_hi,
            }

    raise RuntimeError("could not classify a valid monotone survival slice")


def infer_median_compliance_targets(
    public_surface: pd.DataFrame,
    *,
    central_probability: float = CENTRAL_SURVIVAL_PROBABILITY,
    exclude_horizon_zero: bool = True,
) -> pd.DataFrame:
    """Infer Stage-1 point/censored median-compliance targets from public I1."""
    _validate_public_surface_for_median_inference(public_surface)
    surface = public_surface.copy()
    if exclude_horizon_zero:
        surface = surface[surface["horizon"].astype(float) > TOLERANCE].copy()
    if surface.empty:
        raise ValueError("no positive-horizon public I1 points remain")

    rows: list[dict[str, object]] = []
    group_columns = ["provider_id", "region_id", "region_rho", "horizon"]
    for keys, fixed_slice in surface.groupby(group_columns, sort=True):
        provider_id, region_id, region_rho, horizon = keys
        inferred = _infer_one_median_target(
            fixed_slice,
            central_probability=float(central_probability),
        )
        rows.append(
            {
                "provider_id": str(provider_id),
                "region_id": str(region_id),
                "region_rho": float(region_rho),
                "horizon": float(horizon),
                **inferred,
            }
        )
    targets = pd.DataFrame(rows).sort_values(
        ["provider_id", "region_rho", "horizon"]
    ).reset_index(drop=True)
    if targets.empty:
        raise RuntimeError("median-compliance target table is empty")
    return targets


def calculate_stage1_nominal_loss(
    deterministic_compliance: pd.DataFrame,
    median_targets: pd.DataFrame,
) -> tuple[float, pd.DataFrame]:
    """Return uniform MSE using point and one-sided censored Stage-1 losses."""
    required_compliance = {
        "provider_id",
        "region_id",
        "region_rho",
        "horizon",
        "compliance_fraction",
    }
    missing = required_compliance.difference(deterministic_compliance.columns)
    if missing:
        raise ValueError(
            "deterministic compliance missing columns: "
            + ", ".join(sorted(missing))
        )
    required_targets = {
        "provider_id",
        "region_id",
        "region_rho",
        "horizon",
        "target_kind",
        "median_target",
        "lower_bound",
        "upper_bound",
    }
    missing_targets = required_targets.difference(median_targets.columns)
    if missing_targets:
        raise ValueError(
            "median target table missing columns: "
            + ", ".join(sorted(missing_targets))
        )

    keys = ["provider_id", "region_id", "horizon"]
    deterministic_for_merge = deterministic_compliance[
        [
            "provider_id",
            "region_id",
            "region_rho",
            "horizon",
            "compliance_fraction",
        ]
    ].rename(columns={"region_rho": "region_rho_deterministic"})

    merged = median_targets.merge(
        deterministic_for_merge,
        on=keys,
        how="left",
        validate="one_to_one",
    )
    if merged["compliance_fraction"].isna().any():
        raise RuntimeError("deterministic compliance does not cover every Stage-1 target")

    region_rho_matches = np.isclose(
        merged["region_rho"].astype(float),
        merged["region_rho_deterministic"].astype(float),
        atol=TOLERANCE,
        rtol=0.0,
    )
    if not bool(np.all(region_rho_matches)):
        raise RuntimeError(
            "Stage-1 region_rho values disagree between public targets "
            "and deterministic compliance"
        )

    residuals: list[float] = []
    for row in merged.itertuples(index=False):
        c = float(row.compliance_fraction)
        kind = str(row.target_kind)
        if kind == "point":
            residual = c - float(row.median_target)
        elif kind == "lower_censored":
            residual = max(0.0, float(row.lower_bound) - c)
        elif kind == "upper_censored":
            residual = max(0.0, c - float(row.upper_bound))
        else:
            raise ValueError(f"unknown Stage-1 target_kind: {kind!r}")
        residuals.append(float(residual))

    merged = merged.copy()
    merged["residual"] = residuals
    merged["squared_loss"] = np.square(np.asarray(residuals, dtype=float))
    return float(merged["squared_loss"].mean()), merged


def calculate_stage2_sigma_loss(
    public_surface: pd.DataFrame,
    simulated_surface: pd.DataFrame,
    *,
    exclude_horizon_zero: bool = True,
) -> tuple[dict[str, float], pd.DataFrame]:
    """Compare a stochastic surrogate against the complete public I1 surface."""
    required = {
        "provider_id",
        "region_id",
        "region_rho",
        "rho",
        "horizon",
        "sigma_hat",
    }
    for label, surface in (
        ("public", public_surface),
        ("simulated", simulated_surface),
    ):
        missing = required.difference(surface.columns)
        if missing:
            raise ValueError(
                f"{label} sigma surface missing columns: "
                + ", ".join(sorted(missing))
            )

    public = public_surface.copy()
    simulated = simulated_surface.copy()
    if exclude_horizon_zero:
        public = public[public["horizon"].astype(float) > TOLERANCE].copy()
        simulated = simulated[
            simulated["horizon"].astype(float) > TOLERANCE
        ].copy()

    base_keys = ["provider_id", "region_id", "horizon"]

    public_for_merge = public[
        base_keys + ["region_rho", "rho", "sigma_hat"]
    ].sort_values(base_keys + ["rho"]).reset_index(drop=True)
    public_for_merge["_rho_ordinal"] = public_for_merge.groupby(
        base_keys, sort=False
    ).cumcount()
    public_for_merge = public_for_merge.rename(
        columns={
            "region_rho": "region_rho_i1",
            "rho": "rho_i1",
            "sigma_hat": "sigma_i1",
        }
    )

    simulated_for_merge = simulated[
        base_keys + ["region_rho", "rho", "sigma_hat"]
    ].sort_values(base_keys + ["rho"]).reset_index(drop=True)
    simulated_for_merge["_rho_ordinal"] = simulated_for_merge.groupby(
        base_keys, sort=False
    ).cumcount()
    simulated_for_merge = simulated_for_merge.rename(
        columns={
            "region_rho": "region_rho_m1",
            "rho": "rho_m1",
            "sigma_hat": "sigma_m1_local",
        }
    )

    match_keys = base_keys + ["_rho_ordinal"]
    comparison = public_for_merge.merge(
        simulated_for_merge,
        on=match_keys,
        how="left",
        validate="one_to_one",
    )
    if comparison["sigma_m1_local"].isna().any():
        raise RuntimeError("simulated surface does not cover every public I1 point")
    if len(comparison) != len(public):
        raise RuntimeError("Stage-2 comparison changed the public point count")

    if not bool(
        np.all(
            np.isclose(
                comparison["region_rho_i1"].astype(float),
                comparison["region_rho_m1"].astype(float),
                atol=TOLERANCE,
                rtol=0.0,
            )
        )
    ):
        raise RuntimeError(
            "Stage-2 region_rho values disagree between public and simulated surfaces"
        )

    if not bool(
        np.all(
            np.isclose(
                comparison["rho_i1"].astype(float),
                comparison["rho_m1"].astype(float),
                atol=TOLERANCE,
                rtol=0.0,
            )
        )
    ):
        raise RuntimeError(
            "Stage-2 query-rho values disagree between public and simulated surfaces"
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
    ).to_numpy(dtype=float)
    comparison["error_m1_local_minus_i1"] = error
    comparison["squared_error"] = error * error
    metrics = {
        "mse": float(np.mean(error * error)),
        "rmse": float(np.sqrt(np.mean(error * error))),
        "mae": float(np.mean(np.abs(error))),
        "bias": float(np.mean(error)),
        "max_abs_error": float(np.max(np.abs(error))),
        "n_points": float(len(error)),
    }
    return metrics, comparison


def grid_search_stage1(
    mean_service_times: Iterable[float],
    cost_rates: Iterable[float],
    evaluator: Callable[[float, float], pd.DataFrame],
    median_targets: pd.DataFrame,
) -> SearchResult:
    """Evaluate one deterministic simulator trajectory per (mu,kappa) point."""
    rows: list[dict[str, float]] = []
    best: tuple[float, float, float] | None = None
    for mu in map(float, mean_service_times):
        if mu <= 0.0:
            raise ValueError("Stage-1 mean service times must be positive")
        for kappa in map(float, cost_rates):
            if kappa < 0.0:
                raise ValueError("Stage-1 cost rates must be non-negative")
            compliance = evaluator(mu, kappa)
            loss, _ = calculate_stage1_nominal_loss(compliance, median_targets)
            rows.append(
                {
                    "mean_service_time": mu,
                    "cost_rate": kappa,
                    "loss": loss,
                }
            )
            candidate = (loss, mu, kappa)
            if best is None or candidate < best:
                best = candidate
    if best is None:
        raise ValueError("Stage-1 search received no candidates")
    candidates = pd.DataFrame(rows).sort_values(
        ["loss", "mean_service_time", "cost_rate"]
    ).reset_index(drop=True)
    return SearchResult(
        best_parameters={
            "mean_service_time": float(best[1]),
            "cost_rate": float(best[2]),
        },
        best_loss=float(best[0]),
        candidates=candidates,
    )


def grid_search_stage2(
    service_cvs: Iterable[float],
    evaluator: Callable[[float], pd.DataFrame],
    public_surface: pd.DataFrame,
) -> SearchResult:
    """Evaluate the stochastic local simulator for each candidate service CV."""
    rows: list[dict[str, float]] = []
    best: tuple[float, float] | None = None
    for cv in map(float, service_cvs):
        if cv < 0.0:
            raise ValueError("Stage-2 CV candidates must be non-negative")
        simulated = evaluator(cv)
        metrics, _ = calculate_stage2_sigma_loss(public_surface, simulated)
        rows.append(
            {
                "service_cv": cv,
                **metrics,
            }
        )
        candidate = (float(metrics["mse"]), cv)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise ValueError("Stage-2 search received no candidates")
    candidates = pd.DataFrame(rows).sort_values(
        ["mse", "service_cv"]
    ).reset_index(drop=True)
    return SearchResult(
        best_parameters={"service_cv": float(best[1])},
        best_loss=float(best[0]),
        candidates=candidates,
    )
