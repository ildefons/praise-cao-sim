"""Simulator-independent guards for the Phase-3 sigma-curve diagnostics."""
from __future__ import annotations

from math import isclose
from pathlib import Path

import pandas as pd

from diagnose_rho_conditioned_i1_m0_sigma_curves import _compare_sigma_curves

HERE = Path(__file__).resolve().parent


def main() -> None:
    wb = pd.DataFrame(
        {
            "horizon": [0.0, 5.0, 10.0],
            "sigma_whitebox": [1.0, 0.8, 0.6],
        }
    )
    m0 = pd.DataFrame(
        {
            "rho_global": [0.95, 0.95, 0.95],
            "horizon": [0.0, 5.0, 10.0],
            "sigma_i1_m0": [1.0, 0.6, 0.3],
            "sigma_ProviderA": [1.0, 0.9, 0.8],
            "sigma_ProviderB": [1.0, 0.8, 0.7],
            "sigma_ProviderC": [1.0, 0.7, 0.6],
        }
    )
    comparison, metrics = _compare_sigma_curves(
        wb,
        m0,
        whitebox_column="sigma_whitebox_same_region",
    )
    assert "sigma_whitebox_same_region" in comparison.columns
    assert list(comparison["rho_global"].astype(float)) == [0.95, 0.95, 0.95]
    assert comparison.columns.tolist().count("rho_global") == 1
    assert isclose(
        float(metrics["sigma_mae"]),
        (0.0 + 0.2 + 0.3) / 3.0,
        abs_tol=1e-12,
    )
    assert isclose(float(metrics["sigma_bias"]), (-0.5) / 3.0, abs_tol=1e-12)
    assert isclose(
        float(comparison.loc[2, "error_m0_minus_whitebox"]),
        -0.3,
        abs_tol=1e-12,
    )

    source = (
        HERE / "diagnose_rho_conditioned_i1_m0_sigma_curves.py"
    ).read_text(encoding="utf-8")
    assert "sigma_whitebox_reference" in source
    assert "sigma_whitebox_same_region" in source
    assert "build_phase1_g0_full_m0_boundary" in source
    assert "build_real_whitebox_curve" in source
    assert "i1_m0_reference_sigma_curves.csv" in source
    assert "i1_m0_same_region_sigma_curves.csv" in source
    assert "i1_m0_same_region_sigma_summary.csv" in source
    assert "i1_m0_same_region_sigma.png" in source
    assert "provider_request_ledgers.csv" not in source
    assert "i1_sigma_acquisition_v1" not in source
    assert "derive_nested_rho_regions" not in source
    assert "phase1_whitebox_used_only_for_external_evaluation" in source
    assert 'same_comparison.insert(0, "rho_global"' not in source
    assert 'comparison.insert(2, "rho_global"' not in source

    print("PHASE3_RHO_CONDITIONED_I1_M0_SIGMA_CURVE_TESTS_PASS")
    print("FROZEN_REFERENCE_CURVE_DIAGNOSTIC_PASS")
    print("SAME_M0_REGION_WHITEBOX_DIAGNOSTIC_PASS")
    print("SAME_REGION_ERROR_METRICS_PASS")
    print("SINGLE_RHO_GLOBAL_COLUMN_PASS")
    print("PHASE3_SIGMA_CURVE_PUBLIC_I1_FIREWALL_PASS")


if __name__ == "__main__":
    main()
