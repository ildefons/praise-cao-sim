"""Pure regression tests for the Phase-3 M1-v2 joint-lift helpers."""
from __future__ import annotations

from math import isclose

import pandas as pd

from m1_joint_lift_v2 import (
    M1V2SearchBounds,
    boundary_diagnostics,
    build_search_bounds,
    calculate_full_surface_loss,
)


def _synthetic_surface(offset: float = 0.0) -> pd.DataFrame:
    rows = []
    for region_id, region_rho in (
        ("rho_region_0p95", 0.95),
        ("rho_region_0p983333333", 0.9833333333333333),
    ):
        for rho in (0.95, 0.975, 0.99):
            for horizon in (0.0, 5.0, 10.0):
                sigma = 1.0 if horizon == 0.0 else 0.9 - 0.1 * (rho - 0.95) / 0.04
                rows.append(
                    {
                        "provider_id": "ProviderA",
                        "region_id": region_id,
                        "region_rho": region_rho,
                        "rho": rho,
                        "horizon": horizon,
                        "sigma_hat": sigma + offset if horizon > 0.0 else sigma,
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    public = _synthetic_surface(offset=0.0)
    simulated = _synthetic_surface(offset=-0.05)

    metrics, comparison = calculate_full_surface_loss(public, simulated)
    assert len(comparison) == 12
    assert isclose(metrics["mse"], 0.0025, abs_tol=1e-12)
    assert isclose(metrics["mae"], 0.05, abs_tol=1e-12)
    assert isclose(metrics["bias"], -0.05, abs_tol=1e-12)

    roundtrip = simulated.copy()
    roundtrip["region_rho"] = roundtrip["region_rho"].astype(float) + 5e-16
    roundtrip["rho"] = roundtrip["rho"].astype(float) + 5e-16
    roundtrip_metrics, roundtrip_comparison = calculate_full_surface_loss(
        public, roundtrip
    )
    assert len(roundtrip_comparison) == 12
    assert isclose(roundtrip_metrics["mse"], 0.0025, abs_tol=1e-12)

    bad_rho = simulated.copy()
    mask = (bad_rho["horizon"] == 5.0) & (bad_rho["rho"] == 0.975)
    bad_rho.loc[mask, "rho"] = bad_rho.loc[mask, "rho"] + 1e-4
    try:
        calculate_full_surface_loss(public, bad_rho)
    except RuntimeError as exc:
        assert "query-rho values disagree" in str(exc)
    else:
        raise AssertionError("M1-v2 failed to reject a real query-rho mismatch")

    metadata = {
        "provider_id": "ProviderA",
        "workload_contract": {
            "period": 0.2,
            "accounting_origin": 0.0,
            "horizon_max": 240.0,
        },
        "rho_conditioned_regions": [
            {
                "region_id": "r1",
                "region_rho": 0.95,
                "l_max": 1.0,
                "c_max": 2.0,
                "q_min": 0.5,
            },
            {
                "region_id": "r2",
                "region_rho": 0.99,
                "l_max": 2.0,
                "c_max": 6.0,
                "q_min": 0.5,
            },
        ],
    }
    contract = {
        "joint_full_surface_lift": {
            "optimization": {
                "search_space": {
                    "mu_over_workload_period_bounds": [0.05, 2.0],
                    "cost_rate_reference_multiplier_bounds": [0.1, 10.0],
                    "cv_bounds": [0.0, 2.0],
                }
            }
        }
    }
    bounds = build_search_bounds(metadata, contract)
    assert isclose(bounds.mean_service_time_lower, 0.01, abs_tol=1e-15)
    assert isclose(bounds.mean_service_time_upper, 0.4, abs_tol=1e-15)
    assert isclose(bounds.cost_rate_public_reference, 2.5, abs_tol=1e-15)
    assert isclose(bounds.cost_rate_lower, 0.25, abs_tol=1e-15)
    assert isclose(bounds.cost_rate_upper, 25.0, abs_tol=1e-15)
    assert isclose(bounds.service_cv_lower, 0.0, abs_tol=1e-15)
    assert isclose(bounds.service_cv_upper, 2.0, abs_tol=1e-15)

    interior = boundary_diagnostics(
        mean_service_time=(0.01 * 0.4) ** 0.5,
        cost_rate=(0.25 * 25.0) ** 0.5,
        service_cv=1.0,
        bounds=bounds,
        boundary_fraction=0.02,
    )
    assert not interior["any_near_boundary"]

    lower = boundary_diagnostics(
        mean_service_time=bounds.mean_service_time_lower,
        cost_rate=bounds.cost_rate_lower,
        service_cv=bounds.service_cv_lower,
        bounds=bounds,
        boundary_fraction=0.02,
    )
    assert lower["any_near_boundary"]
    assert all(lower["near_boundary"].values())

    assert isinstance(bounds, M1V2SearchBounds)

    print("PHASE3_M1_V2_HELPER_TESTS_PASS")
    print("M1_V2_FULL_SURFACE_TOLERANT_ALIGNMENT_PASS")
    print("M1_V2_PUBLIC_ONLY_SEARCH_BOUNDS_PASS")
    print("M1_V2_BOUNDARY_DIAGNOSTICS_PASS")


if __name__ == "__main__":
    main()
