"""Simulator-independent tests for Phase-3 M0 evaluation diagnostics."""
from __future__ import annotations

from math import isclose

import pandas as pd

from m0_analytic_composition import AdmissibilityBoundary
from m0_evaluation_diagnostics import (
    boundary_overlap_metrics,
    build_rho_vector_sigma_family,
    common_rho_support,
    summarize_rho_vector_shapes,
)


def _surface(values: dict[tuple[float, float], float]) -> pd.DataFrame:
    rows = []
    for (rho, horizon), sigma in sorted(values.items()):
        rows.append({"rho": rho, "horizon": horizon, "sigma_hat": sigma})
    return pd.DataFrame(rows)


def main() -> None:
    wb = AdmissibilityBoundary(l_max=2.0, c_max=4.0, q_min=0.5)
    equal = boundary_overlap_metrics(wb, wb)
    assert equal["region_relation"] == "EQUAL"
    assert isclose(float(equal["J_A"]), 1.0, abs_tol=1e-12)
    assert equal["measure_semantics"] == "LC_projection_exact_same_Q_threshold"

    m0_subset = AdmissibilityBoundary(l_max=1.0, c_max=2.0, q_min=0.5)
    subset = boundary_overlap_metrics(m0_subset, wb)
    assert subset["region_relation"] == "M0_SUBSET_WB"
    assert isclose(float(subset["J_A"]), 0.25, abs_tol=1e-12)
    assert isclose(float(subset["intersection_over_A_G_WB"]), 0.25, abs_tol=1e-12)
    assert isclose(float(subset["intersection_over_A_G_M0"]), 1.0, abs_tol=1e-12)

    partial = boundary_overlap_metrics(
        AdmissibilityBoundary(l_max=1.0, c_max=8.0, q_min=0.5), wb
    )
    assert partial["region_relation"] == "PARTIAL_OVERLAP"
    assert isclose(float(partial["J_A"]), 4.0 / 12.0, abs_tol=1e-12)

    unequal_q = AdmissibilityBoundary(l_max=2.0, c_max=4.0, q_min=0.6)
    try:
        boundary_overlap_metrics(unequal_q, wb)
        raise AssertionError("quality_upper guard did not fire")
    except ValueError:
        pass
    q_bounded = boundary_overlap_metrics(unequal_q, wb, quality_upper=1.0)
    assert q_bounded["measure_semantics"] == "LCQ_volume_on_declared_finite_Q_domain"
    assert 0.0 < float(q_bounded["J_A"]) < 1.0

    values_a = {
        (0.95, 0.0): 1.0, (0.95, 10.0): 0.8,
        (0.99, 0.0): 1.0, (0.99, 10.0): 0.2,
    }
    values_b = {
        (0.95, 0.0): 1.0, (0.95, 10.0): 0.5,
        (0.99, 0.0): 1.0, (0.99, 10.0): 0.1,
    }
    values_c = {
        (0.95, 0.0): 1.0, (0.95, 10.0): 0.25,
        (0.99, 0.0): 1.0, (0.99, 10.0): 0.05,
    }
    surfaces = {
        "ProviderA": _surface(values_a),
        "ProviderB": _surface(values_b),
        "ProviderC": _surface(values_c),
    }
    assert common_rho_support(surfaces) == (0.95, 0.99)

    family = build_rho_vector_sigma_family(surfaces, [0.0, 10.0])
    assert len(family) == 2**3 * 2
    vectors = family[["rho_ProviderA", "rho_ProviderB", "rho_ProviderC"]].drop_duplicates()
    assert len(vectors) == 8
    diagonal_vectors = family[family["is_same_rho_diagonal"]][
        ["rho_ProviderA", "rho_ProviderB", "rho_ProviderC"]
    ].drop_duplicates()
    assert len(diagonal_vectors) == 2

    point = family[
        (family["rho_ProviderA"] == 0.95)
        & (family["rho_ProviderB"] == 0.99)
        & (family["rho_ProviderC"] == 0.95)
        & (family["horizon"] == 10.0)
    ].iloc[0]
    assert isclose(float(point["sigma_hat_m0_rho_vector"]), 0.8 * 0.1 * 0.25, abs_tol=1e-12)
    assert point["rho_vector_role"] == "DIAGNOSTIC_RHO_VECTOR_SENSITIVITY"

    summary = summarize_rho_vector_shapes(family, snapshot_horizons=(0.0, 10.0))
    assert len(summary) == 8
    diagonal_095 = summary[
        (summary["rho_ProviderA"] == 0.95)
        & (summary["rho_ProviderB"] == 0.95)
        & (summary["rho_ProviderC"] == 0.95)
    ].iloc[0]
    end_sigma = 0.8 * 0.5 * 0.25
    assert isclose(float(diagonal_095["sigma_H10"]), end_sigma, abs_tol=1e-12)
    assert isclose(float(diagonal_095["normalized_sigma_area"]), (1.0 + end_sigma) / 2.0, abs_tol=1e-12)

    print("PHASE3_M0_EVALUATION_DIAGNOSTICS_TESTS_PASS")
    print("M0_REGION_JACCARD_PASS")
    print("M0_REGION_RELATION_AND_COVERAGE_PASS")
    print("M0_RHO_VECTOR_CARTESIAN_FAMILY_PASS")
    print("M0_RHO_VECTOR_OFF_DIAGONAL_DIAGNOSTIC_ONLY_PASS")
    print("M0_RHO_VECTOR_SHAPE_SUMMARY_PASS")


if __name__ == "__main__":
    main()
