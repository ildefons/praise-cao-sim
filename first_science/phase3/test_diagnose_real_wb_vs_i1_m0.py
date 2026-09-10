"""Simulator-independent tests for the real WB versus I1-M0 diagnostic."""
from __future__ import annotations

import inspect
from math import isclose, sqrt

import numpy as np
import pandas as pd

from diagnose_real_wb_vs_i1_m0 import (
    _rho_tag,
    build_same_rho_m0_curve,
    compare_curves,
    run_real_trace_diagnostic,
)
from i1_local_region import (
    _choose_threshold_by_first_crossing,
    _coordinate_sigma_curve,
    calibrate_coordinate_threshold,
)


def _synthetic_surface(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rho": [0.95, 0.95],
            "horizon": [0.0, 5.0],
            "sigma_hat": values,
        }
    )


def _minimal_ledger() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trajectory": [0, 1],
            "request_id": [0, 0],
            "emission": [0.0, 0.0],
            "completion": [1.0, 3.0],
            "L": [1.0, 3.0],
            "C": [1.0, 1.0],
            "Q": [0.5, 0.5],
        }
    )


def main() -> None:
    # Exact cumulative-accounting sanity check for a latency-only coordinate.
    ledger = _minimal_ledger()
    curve = _coordinate_sigma_curve(
        ledger,
        coordinate="L",
        threshold=2.0,
        rho_anchor=0.95,
        horizons=[0.0, 1.0, 2.0, 3.0, 120.0],
        stop_time=120.0,
    )
    expected = [1.0, 1.0, 0.5, 0.5, 0.5]
    assert np.allclose(curve["sigma"].to_numpy(dtype=float), expected, atol=1e-12)

    # The frozen selector is based on first crossing time. Candidate 2 crosses
    # below 0.95 exactly at H*=120 and must therefore be selected.
    fake_horizons = [0.0, 60.0, 120.0, 180.0, 240.0]
    crossing_by_threshold = {1.0: 60.0, 2.0: 120.0, 3.0: 180.0, 4.0: None}

    def fake_evaluator(threshold: float) -> pd.DataFrame:
        crossing = crossing_by_threshold[float(threshold)]
        sigma = []
        for horizon in fake_horizons:
            sigma.append(1.0 if crossing is None or horizon < crossing else 0.90)
        return pd.DataFrame({"horizon": fake_horizons, "sigma": sigma})

    selected, diagnostics = _choose_threshold_by_first_crossing(
        candidate_thresholds_in_relaxation_order=np.array([1.0, 2.0, 3.0, 4.0]),
        evaluate_curve=fake_evaluator,
        anchor_horizon=120.0,
        sigma_target=0.95,
    )
    assert isclose(selected, 2.0, abs_tol=1e-12)
    assert isclose(float(diagnostics["first_crossing_below_target"]), 120.0)
    assert diagnostics["selection_mode"] == (
        "first_crossing_below_sigma_target_closest_to_H_star"
    )

    # Current anchor quality is constant. Preserve its unique observed value.
    q_threshold, q_diagnostics = calibrate_coordinate_threshold(
        ledger=ledger,
        coordinate="Q",
        rho_anchor=0.95,
        horizons=[0.0, 60.0, 120.0],
        stop_time=120.0,
        anchor_horizon=120.0,
        sigma_target=0.95,
    )
    assert isclose(q_threshold, 0.5, abs_tol=1e-12)
    assert q_diagnostics["selection_mode"] == "constant_observed_quality_use_unique_value"

    # No external A_i input. The full Phase-1 physical config is now required
    # because applicability is evaluated on the complete G0 boundary.
    signature = inspect.signature(run_real_trace_diagnostic)
    assert "local_regions_path" not in signature.parameters
    assert "local_regions" not in signature.parameters
    assert "rho_global" in signature.parameters
    assert "provider_root" in signature.parameters
    assert "phase1_physical_config_path" in signature.parameters

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
    comparison, metrics = compare_curves(whitebox, m0, m0_applicable=True)
    errors = comparison["error_m0_minus_wb"].astype(float).tolist()
    assert len(errors) == 2
    assert isclose(errors[0], -0.05, abs_tol=1e-12)
    assert isclose(errors[1], -0.1, abs_tol=1e-12)
    assert isclose(metrics["mae"], 0.075, abs_tol=1e-12)
    assert isclose(metrics["bias"], -0.075, abs_tol=1e-12)
    assert isclose(metrics["rmse"], sqrt((0.05**2 + 0.1**2) / 2), abs_tol=1e-12)
    assert isclose(metrics["max_abs_error"], 0.1, abs_tol=1e-12)
    assert np.allclose(
        comparison["sigma_i1_m0_raw_probability_component"].to_numpy(dtype=float),
        [0.45, 0.1],
        atol=1e-12,
    )

    # A failed boundary containment means M0 has no prediction. Keep the raw
    # product only as a diagnostic component and suppress errors/metrics.
    not_applicable, na_metrics = compare_curves(
        whitebox,
        m0,
        m0_applicable=False,
    )
    assert not_applicable["sigma_i1_m0"].isna().all()
    assert not_applicable["error_m0_minus_wb"].isna().all()
    assert np.allclose(
        not_applicable["sigma_i1_m0_raw_probability_component"].to_numpy(dtype=float),
        [0.45, 0.1],
        atol=1e-12,
    )
    assert all(np.isnan(value) for value in na_metrics.values())

    assert _rho_tag(0.95) == "0p95"
    assert _rho_tag(0.9833333333333333) == "0p983333"

    print("PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_TESTS_PASS")
    print("A_I_COORDINATE_FIRST_CROSSING_H120_RULE_PASS")
    print("CUMULATIVE_COORDINATE_ACCOUNTING_PASS")
    print("CONSTANT_QUALITY_NO_ARTIFICIAL_THRESHOLD_PASS")
    print("NO_EXTERNAL_A_I_INPUT_PASS")
    print("FULL_M0_APPLICABILITY_INPUT_PASS")
    print("M0_REAL_CURVE_COMPOSITION_KERNEL_PASS")
    print("M0_NOT_APPLICABLE_SUPPRESSION_PASS")
    print("RAW_PRODUCT_RETAINED_AS_DIAGNOSTIC_ONLY_PASS")
    print("WB_M0_ERROR_METRICS_PASS")


if __name__ == "__main__":
    main()
