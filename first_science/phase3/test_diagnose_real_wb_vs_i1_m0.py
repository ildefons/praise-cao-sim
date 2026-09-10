"""Simulator-independent tests for the real WB versus I1-M0 diagnostic."""
from __future__ import annotations

import json
from math import isclose, sqrt
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from diagnose_real_wb_vs_i1_m0 import (
    _rho_tag,
    build_same_rho_m0_curve,
    compare_curves,
    load_explicit_local_regions,
)


def _write_json(directory: Path, name: str, document: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


def _synthetic_surface(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rho": [0.95, 0.95],
            "horizon": [0.0, 5.0],
            "sigma_hat": values,
        }
    )


def main() -> None:
    with TemporaryDirectory(prefix="praise_real_m0_diag_test_") as temporary:
        root = Path(temporary)
        valid_path = _write_json(
            root,
            "valid_regions.json",
            {
                "regions": {
                    "ProviderA": {"l_max": 0.2, "c_max": 0.6, "q_min": 0.5},
                    "ProviderB": {"l_max": 0.3, "c_max": 0.8, "q_min": 0.5},
                    "ProviderC": {"l_max": 0.4, "c_max": 1.0, "q_min": 0.5},
                }
            },
        )
        regions = load_explicit_local_regions(valid_path)
        assert set(regions) == {"ProviderA", "ProviderB", "ProviderC"}
        assert isclose(regions["ProviderA"].l_max, 0.2)
        assert isclose(regions["ProviderC"].c_max, 1.0)

        top_level_rho_path = _write_json(
            root,
            "invalid_top_level_rho.json",
            {
                "rho_i": 0.95,
                "regions": {
                    "ProviderA": {"l_max": 0.2, "c_max": 0.6, "q_min": 0.5},
                    "ProviderB": {"l_max": 0.3, "c_max": 0.8, "q_min": 0.5},
                    "ProviderC": {"l_max": 0.4, "c_max": 1.0, "q_min": 0.5},
                },
            },
        )
        try:
            load_explicit_local_regions(top_level_rho_path)
        except ValueError as error:
            assert "must not select rho" in str(error)
        else:
            raise AssertionError("diagnostic accepted a top-level rho_i selection")

        provider_rho_path = _write_json(
            root,
            "invalid_provider_rho.json",
            {
                "regions": {
                    "ProviderA": {
                        "l_max": 0.2,
                        "c_max": 0.6,
                        "q_min": 0.5,
                        "rho": 0.95,
                    },
                    "ProviderB": {"l_max": 0.3, "c_max": 0.8, "q_min": 0.5},
                    "ProviderC": {"l_max": 0.4, "c_max": 1.0, "q_min": 0.5},
                }
            },
        )
        try:
            load_explicit_local_regions(provider_rho_path)
        except ValueError as error:
            assert "must not contain rho" in str(error)
        else:
            raise AssertionError("diagnostic accepted rho inside ProviderA A_i")

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
    assert list(comparison["error_m0_minus_wb"]) == [-0.05, -0.1]
    assert isclose(metrics["mae"], 0.075, abs_tol=1e-12)
    assert isclose(metrics["bias"], -0.075, abs_tol=1e-12)
    assert isclose(metrics["rmse"], sqrt((0.05**2 + 0.1**2) / 2), abs_tol=1e-12)
    assert isclose(metrics["max_abs_error"], 0.1, abs_tol=1e-12)

    assert _rho_tag(0.95) == "0p95"
    assert _rho_tag(0.9833333333333333) == "0p983333"

    print("PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_TESTS_PASS")
    print("DIAGNOSTIC_DOES_NOT_SELECT_A_I_OR_RHO_I_PASS")
    print("M0_REAL_CURVE_COMPOSITION_KERNEL_PASS")
    print("WB_M0_ERROR_METRICS_PASS")
    print("DIAGNOSTIC_FILENAME_RHO_TAG_PASS")


if __name__ == "__main__":
    main()
