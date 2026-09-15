"""Simulator-independent regression tests for the Phase-3 M1 lift contract."""
from __future__ import annotations

from math import isclose

import pandas as pd

from m1_surrogate_lift import (
    calculate_stage1_nominal_loss,
    calculate_stage2_sigma_loss,
    grid_search_stage1,
    grid_search_stage2,
    infer_median_compliance_targets,
)


def _public_surface() -> pd.DataFrame:
    rows = []
    # H=0 is deliberately present and must be excluded from fitting.
    for rho, sigma in ((0.95, 1.0), (0.975, 1.0), (0.99, 1.0)):
        rows.append(
            {
                "provider_id": "ProviderA",
                "region_id": "A95",
                "region_rho": 0.95,
                "rho": rho,
                "horizon": 0.0,
                "sigma_hat": sigma,
            }
        )

    # Bracketed median: linear interpolation between 0.975 @ 0.6 and 0.99 @ 0.3
    # gives rho_50 = 0.98.
    for rho, sigma in ((0.95, 0.8), (0.975, 0.6), (0.99, 0.3)):
        rows.append(
            {
                "provider_id": "ProviderA",
                "region_id": "A95",
                "region_rho": 0.95,
                "rho": rho,
                "horizon": 5.0,
                "sigma_hat": sigma,
            }
        )

    # Lower-censored: even rho=0.99 survives with probability >= 0.5.
    for rho, sigma in ((0.95, 0.9), (0.975, 0.8), (0.99, 0.6)):
        rows.append(
            {
                "provider_id": "ProviderA",
                "region_id": "A95",
                "region_rho": 0.95,
                "rho": rho,
                "horizon": 10.0,
                "sigma_hat": sigma,
            }
        )

    # Upper-censored: even rho=0.95 survives with probability < 0.5.
    for rho, sigma in ((0.95, 0.4), (0.975, 0.3), (0.99, 0.1)):
        rows.append(
            {
                "provider_id": "ProviderA",
                "region_id": "A95",
                "region_rho": 0.95,
                "rho": rho,
                "horizon": 15.0,
                "sigma_hat": sigma,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    public = _public_surface()
    targets = infer_median_compliance_targets(public)
    assert set(targets["horizon"].astype(float)) == {5.0, 10.0, 15.0}

    point = targets[targets["horizon"] == 5.0].iloc[0]
    assert point["target_kind"] == "point"
    assert isclose(float(point["median_target"]), 0.98, abs_tol=1e-12)

    lower = targets[targets["horizon"] == 10.0].iloc[0]
    assert lower["target_kind"] == "lower_censored"
    assert isclose(float(lower["lower_bound"]), 0.99, abs_tol=1e-12)

    upper = targets[targets["horizon"] == 15.0].iloc[0]
    assert upper["target_kind"] == "upper_censored"
    assert isclose(float(upper["upper_bound"]), 0.95, abs_tol=1e-12)

    deterministic = pd.DataFrame(
        [
            {
                "provider_id": "ProviderA",
                "region_id": "A95",
                "region_rho": 0.95,
                "horizon": 5.0,
                "compliance_fraction": 0.98,
            },
            {
                "provider_id": "ProviderA",
                "region_id": "A95",
                "region_rho": 0.95,
                "horizon": 10.0,
                "compliance_fraction": 0.995,
            },
            {
                "provider_id": "ProviderA",
                "region_id": "A95",
                "region_rho": 0.95,
                "horizon": 15.0,
                "compliance_fraction": 0.94,
            },
        ]
    )
    loss, detail = calculate_stage1_nominal_loss(deterministic, targets)
    assert isclose(loss, 0.0, abs_tol=1e-15)
    assert isclose(float(detail["squared_loss"].sum()), 0.0, abs_tol=1e-15)

    violating = deterministic.copy()
    violating.loc[violating["horizon"] == 10.0, "compliance_fraction"] = 0.98
    violating.loc[violating["horizon"] == 15.0, "compliance_fraction"] = 0.97
    violating_loss, _ = calculate_stage1_nominal_loss(violating, targets)
    expected = ((0.99 - 0.98) ** 2 + (0.97 - 0.95) ** 2) / 3.0
    assert isclose(violating_loss, expected, abs_tol=1e-15)

    simulated = public.copy()
    simulated["sigma_hat"] = simulated["sigma_hat"].astype(float) - 0.05
    metrics, comparison = calculate_stage2_sigma_loss(public, simulated)
    assert len(comparison) == 9  # three positive H values x three rho values
    assert isclose(metrics["mae"], 0.05, abs_tol=1e-12)
    assert isclose(metrics["mse"], 0.0025, abs_tol=1e-12)
    assert isclose(metrics["bias"], -0.05, abs_tol=1e-12)

    # Hand-check the generic search wrappers without a simulator dependency.
    def stage1_evaluator(mu: float, kappa: float) -> pd.DataFrame:
        frame = deterministic.copy()
        frame["compliance_fraction"] = frame["compliance_fraction"] - abs(mu - 1.0) - abs(kappa - 2.0)
        return frame

    stage1 = grid_search_stage1(
        [0.5, 1.0, 1.5], [1.0, 2.0, 3.0], stage1_evaluator, targets
    )
    assert stage1.best_parameters == {
        "mean_service_time": 1.0,
        "cost_rate": 2.0,
    }
    assert isclose(stage1.best_loss, 0.0, abs_tol=1e-15)

    def stage2_evaluator(cv: float) -> pd.DataFrame:
        frame = public.copy()
        frame["sigma_hat"] = frame["sigma_hat"].astype(float) + (cv - 0.5)
        return frame

    stage2 = grid_search_stage2([0.0, 0.5, 1.0], stage2_evaluator, public)
    assert stage2.best_parameters == {"service_cv": 0.5}
    assert isclose(stage2.best_loss, 0.0, abs_tol=1e-15)

    print("PHASE3_M1_SURROGATE_LIFT_TESTS_PASS")
    print("M1_MEDIAN_TARGET_INFERENCE_PASS")
    print("M1_CENSORED_STAGE1_LOSS_PASS")
    print("M1_FULL_SURFACE_STAGE2_LOSS_PASS")


if __name__ == "__main__":
    main()
