"""Simulator-independent guards for the public-I1 Phase-3 diagnostic."""
from __future__ import annotations

import inspect
from math import isclose, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from diagnose_real_wb_vs_i1_m0 import (
    _rho_tag,
    build_same_rho_m0_curve,
    compare_curves,
    run_real_trace_diagnostic,
)

HERE = Path(__file__).resolve().parent


def _synthetic_surface(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"rho": [0.95, 0.95], "horizon": [0.0, 5.0], "sigma_hat": values})


def main() -> None:
    signature = inspect.signature(run_real_trace_diagnostic)
    assert "i1_card_root" in signature.parameters
    assert "i1_card_manifest_path" in signature.parameters
    assert "provider_root" not in signature.parameters
    assert "local_regions" not in signature.parameters
    assert "phase1_physical_config_path" in signature.parameters

    source = (HERE / "diagnose_real_wb_vs_i1_m0.py").read_text(encoding="utf-8")
    assert "derive_local_regions_from_traces" not in source
    assert "i1_local_region" not in source
    assert "provider_request_ledgers.csv" not in source
    assert "load_i1_provider_card" in source
    assert "phase3_reads_private_provider_traces" in source

    surfaces = {
        "ProviderA": _synthetic_surface([1.0, 0.8]),
        "ProviderB": _synthetic_surface([0.9, 0.5]),
        "ProviderC": _synthetic_surface([0.5, 0.25]),
    }
    m0 = build_same_rho_m0_curve(surfaces, 0.95, [0.0, 5.0])
    assert isclose(float(m0.loc[0, "sigma_i1_m0"]), 0.45, abs_tol=1e-12)
    assert isclose(float(m0.loc[1, "sigma_i1_m0"]), 0.1, abs_tol=1e-12)

    whitebox = pd.DataFrame({"horizon": [0.0, 5.0], "sigma_whitebox": [0.50, 0.20]})
    comparison, metrics = compare_curves(whitebox, m0, m0_applicable=True)
    errors = comparison["error_m0_minus_wb"].astype(float).tolist()
    assert isclose(errors[0], -0.05, abs_tol=1e-12)
    assert isclose(errors[1], -0.1, abs_tol=1e-12)
    assert isclose(metrics["mae"], 0.075, abs_tol=1e-12)
    assert isclose(metrics["bias"], -0.075, abs_tol=1e-12)
    assert isclose(metrics["rmse"], sqrt((0.05**2 + 0.1**2) / 2), abs_tol=1e-12)

    not_applicable, na_metrics = compare_curves(whitebox, m0, m0_applicable=False)
    assert not_applicable["sigma_i1_m0"].isna().all()
    assert not_applicable["error_m0_minus_wb"].isna().all()
    assert np.allclose(
        not_applicable["sigma_i1_m0_raw_probability_component"].to_numpy(dtype=float),
        [0.45, 0.1], atol=1e-12,
    )
    assert all(np.isnan(value) for value in na_metrics.values())

    assert _rho_tag(0.95) == "0p95"
    assert _rho_tag(0.9833333333333333) == "0p983333"

    print("PHASE3_REAL_WB_VS_I1_M0_DIAGNOSTIC_TESTS_PASS")
    print("PHASE3_PUBLIC_I1_ONLY_FIREWALL_PASS")
    print("PHASE3_PRIVATE_PROVIDER_TRACE_ACCESS_BLOCKED_PASS")
    print("M0_REAL_CURVE_COMPOSITION_KERNEL_PASS")
    print("M0_NOT_APPLICABLE_SUPPRESSION_PASS")
    print("RAW_PRODUCT_RETAINED_AS_DIAGNOSTIC_ONLY_PASS")
    print("WB_M0_ERROR_METRICS_PASS")


if __name__ == "__main__":
    main()
