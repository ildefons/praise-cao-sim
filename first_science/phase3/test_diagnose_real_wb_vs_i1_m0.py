"""Simulator-independent tests for the real WB versus I1-M0 diagnostic."""
from __future__ import annotations

import inspect
from math import isclose, sqrt

import pandas as pd

from diagnose_real_wb_vs_i1_m0 import (
    _rho_tag,
    build_same_rho_m0_curve,
    compare_curves,
    derive_local_regions_from_traces,
    empirical_lower_threshold,
    empirical_upper_threshold,
    run_real_trace_diagnostic,
)


def _synthetic_surface(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rho": [0.95, 0.95],
            "horizon": [0.0, 5.0],
            "sigma_hat": values,
        }
    )


def _synthetic_provider_ledger(offset: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trajectory": [0] * 10,
            "request_id": list(range(10)),
            "emission": [float(i) for i in range(10)],
            "completion": [float(i) + 0.1 for i in range(10)],
            "L": [offset + float(i) for i in range(1, 11)],
            "C": [10.0 * offset + float(i) for i in range(1, 11)],
            "Q": [offset + float(i) for i in range(1, 11)],
        }
    )


def main() -> None:
    values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    assert isclose(empirical_upper_threshold(values, 0.8), 8.0)
    assert isclose(empirical_lower_threshold(values, 0.8), 3.0)
    assert isclose(empirical_upper_threshold(values, 0.95), 10.0)
    assert isclose(empirical_lower_threshold(values, 0.95), 1.0)

    provider_ledgers = {
        "ProviderA": _synthetic_provider_ledger(0.0),
        "ProviderB": _synthetic_provider_ledger(100.0),
        "ProviderC": _synthetic_provider_ledger(200.0),
    }
    regions, table = derive_local_regions_from_traces(provider_ledgers, 0.8)
    assert isclose(regions["ProviderA"].l_max, 8.0)
    assert isclose(regions["ProviderA"].c_max, 8.0)
    assert isclose(regions["ProviderA"].q_min, 3.0)
    assert isclose(regions["ProviderB"].l_max, 108.0)
    assert isclose(regions["ProviderC"].q_min, 203.0)
    assert set(table["provider"]) == {"ProviderA", "ProviderB", "ProviderC"}
    assert set(table["rho_global"]) == {0.8}

    # The production diagnostic must not expose an external A_i input anymore.
    signature = inspect.signature(run_real_trace_diagnostic)
    assert "local_regions_path" not in signature.parameters
    assert "local_regions" not in signature.parameters
    assert "rho_global" in signature.parameters
    assert "provider_root" in signature.parameters

    surfaces = {
        "ProviderA": _synthetic_surface([1.0, 0.8]),
        "ProviderB": _synthetic_surface([0.9, 0.5]),
        "ProviderC": _synthetic_surface([0.5, 0.25]),
    }
    m0 = build_same_rho_m0_curve(surfaces, 0.95, [0.0, 5.0])
    assert list(m0["horizon"]) == [0.0, 5.0]
    assert isclose(float(m0.loc[0, "sigma_i1_m0"]), 0.45, abs_tol=1e-12)
    assert isclose(float(m0.loc[1, "sigma_i1_m0"]), 0.1, abs_tol=1e-12)
    assert isclose(float(m0.loc[1, "sigma_ProviderA"]), 0.8, abs_tol=1e-12)

    whitebox = pd.DataFrame(
        {
            "horizon": [0.0, 5.0],
            "sigma_whitebox": [0.50, 0.20],
        }
    )
    comparison, metrics = compare_curves(whitebox, m0)
    errors = comparison["error_m0_minus_wb"].astype(float).tolist()
    assert len(errors) == 2
    assert isclose(errors[0], -0.05, abs_tol=1e-12)
    assert isclose(errors[1], -0.1, abs_tol=1e-12)
    assert isclose(metrics["mae"], 0.075, abs_tol=1e-12)
    assert isclose(metrics["bias"], -0.075, abs_tol=1e-12)
    assert isclose(metrics["rmse"], sqrt((0.05**2 + 0.1**2) / 2), abs_tol=1e-12)
    assert isclose(metrics["max_abs_error"], 0.1, abs_tol=1e-12)

    assert _rho_tag(0.95) == "0p95"
    assert _rho_tag(0.9833333333333333) == "0p983333"

    print("PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_TESTS_PASS")
    print("A_I_DERIVED_FROM_T_I_AND_RHO_G_PASS")
    print("NO_EXTERNAL_A_I_INPUT_PASS")
    print("M0_REAL_CURVE_COMPOSITION_KERNEL_PASS")
    print("WB_M0_ERROR_METRICS_PASS")
    print("DIAGNOSTIC_FILENAME_RHO_TAG_PASS")


if __name__ == "__main__":
    main()
