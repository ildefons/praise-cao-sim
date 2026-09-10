"""Simulator-independent guards for rho-conditioned I1-M0 two-axis evaluation."""
from __future__ import annotations

from math import isclose
from pathlib import Path

import pandas as pd

from diagnose_rho_conditioned_i1_m0 import (
    _curve_error,
    build_same_rho_conditioned_m0_curve,
    common_same_rho_support,
    provider_boundaries_at_region_rho,
)

HERE = Path(__file__).resolve().parent


def _surface(values_095: list[float], values_099: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region_id": ["r095", "r095", "r099", "r099"],
            "region_rho": [0.95, 0.95, 0.99, 0.99],
            "rho": [0.95, 0.95, 0.99, 0.99],
            "horizon": [0.0, 5.0, 0.0, 5.0],
            "sigma_hat": [
                values_095[0],
                values_095[1],
                values_099[0],
                values_099[1],
            ],
        }
    )


def main() -> None:
    metadata = {}
    for provider, scale in zip(
        ("ProviderA", "ProviderB", "ProviderC"),
        (1.0, 2.0, 3.0),
    ):
        metadata[provider] = {
            "supported_region_rho_values": [0.95, 0.99],
            "supported_query_rho_values": [0.95, 0.99],
            "rho_conditioned_regions": [
                {
                    "region_id": "r095",
                    "region_rho": 0.95,
                    "l_max": 1.0 * scale,
                    "c_max": 2.0 * scale,
                    "q_min": 0.5,
                },
                {
                    "region_id": "r099",
                    "region_rho": 0.99,
                    "l_max": 1.2 * scale,
                    "c_max": 2.4 * scale,
                    "q_min": 0.5,
                },
            ],
        }

    assert common_same_rho_support(metadata) == (0.95, 0.99)
    b095 = provider_boundaries_at_region_rho(metadata, 0.95)
    b099 = provider_boundaries_at_region_rho(metadata, 0.99)
    assert b099["ProviderC"].l_max > b095["ProviderC"].l_max
    assert b099["ProviderC"].c_max > b095["ProviderC"].c_max

    surfaces = {
        "ProviderA": _surface([1.0, 0.8], [1.0, 0.4]),
        "ProviderB": _surface([1.0, 0.5], [1.0, 0.2]),
        "ProviderC": _surface([1.0, 0.25], [1.0, 0.1]),
    }
    curve_095 = build_same_rho_conditioned_m0_curve(
        surfaces,
        rho=0.95,
        horizons=[0.0, 5.0],
    )
    curve_099 = build_same_rho_conditioned_m0_curve(
        surfaces,
        rho=0.99,
        horizons=[0.0, 5.0],
    )
    assert isclose(
        float(curve_095.loc[1, "sigma_i1_m0"]), 0.1, abs_tol=1e-12
    )
    assert isclose(
        float(curve_099.loc[1, "sigma_i1_m0"]), 0.008, abs_tol=1e-12
    )

    wb = pd.DataFrame(
        {"horizon": [0.0, 5.0], "sigma_whitebox": [1.0, 0.2]}
    )
    comparison, metrics = _curve_error(wb, curve_095)
    assert isclose(float(metrics["sigma_mae"]), 0.05, abs_tol=1e-12)
    assert isclose(
        float(comparison.loc[1, "error_m0_minus_wb"]), -0.1, abs_tol=1e-12
    )

    source = (
        HERE / "diagnose_rho_conditioned_i1_m0.py"
    ).read_text(encoding="utf-8")
    assert "provider_request_ledgers.csv" not in source
    assert "derive_nested_rho_regions" not in source
    assert "sigma_error_suppressed_when_not_contained" in source
    assert "rho_region=rho_query=rho_G" in source

    print("PHASE3_RHO_CONDITIONED_I1_M0_TESTS_PASS")
    print("RHO_DEPENDENT_PROVIDER_BOUNDARY_SELECTION_PASS")
    print("SAME_RHO_REGION_QUERY_DIAGONAL_PASS")
    print("RHO_CONDITIONED_M0_PRODUCT_PASS")
    print("TWO_AXIS_SIGMA_MAE_WITHOUT_CONTAINMENT_SUPPRESSION_PASS")
    print("PHASE3_PRIVATE_PROVIDER_TRACE_ACCESS_BLOCKED_PASS")


if __name__ == "__main__":
    main()
