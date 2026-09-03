"""Simulator-independent tests for the minimal Phase-2 I1 provider card."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from i1_provider_card import (
    I1_CARD_SCHEMA,
    build_i1_provider_card,
    load_i1_provider_card,
    query_i1_provider_card_exact,
    wilson_binomial_interval,
    write_i1_provider_card,
)


def synthetic_private_provider_ledgers() -> pd.DataFrame:
    """Two private trajectories; one has exactly one local latency failure."""
    rows = []
    for trajectory in (0, 1):
        for request_id in range(25):
            emission = float(request_id)
            latency = 0.4
            if trajectory == 1 and request_id == 10:
                latency = 0.6
            rows.append(
                {
                    "trajectory": trajectory,
                    "seed": 9000 + trajectory,
                    "request_id": request_id,
                    "emission": emission,
                    "completion": emission + latency,
                    "L": latency,
                    "C": 0.4,
                    "Q": 0.5,
                }
            )
    return pd.DataFrame(rows)


def run_all_tests() -> None:
    local_rho_equal_budget = 1.0 - 0.05 / 3.0
    metadata, surface = build_i1_provider_card(
        provider_id="ProviderA",
        private_provider_ledgers=synthetic_private_provider_ledgers(),
        local_regions=[
            {
                "region_id": "A_local_test",
                "l_max": 0.5,
                "c_max": 1.0,
                "q_min": 0.5,
            }
        ],
        rho_values=[0.95, local_rho_equal_budget],
        horizons=[0.0, 30.0],
        stop_time=30.0,
        workload_contract={
            "period": 1.0,
            "accounting_origin": 0.0,
            "horizon_max": 30.0,
            "description": "synthetic unit-test workload",
        },
    )

    assert metadata["schema"] == I1_CARD_SCHEMA
    assert metadata["phase"] == "phase2_step1"
    assert metadata["provider_id"] == "ProviderA"
    assert metadata["n_trajectories"] == 2
    assert "seed" not in surface.columns
    assert "center_instruction_mean" not in surface.columns
    assert "dispersion" not in surface.columns

    rho095 = query_i1_provider_card_exact(
        surface,
        l_max=0.5,
        c_max=1.0,
        q_min=0.5,
        rho=0.95,
        horizon=30.0,
    )
    rho_equal = query_i1_provider_card_exact(
        surface,
        l_max=0.5,
        c_max=1.0,
        q_min=0.5,
        rho=local_rho_equal_budget,
        horizon=30.0,
    )
    # Trajectory 1 has compliance 24/25=0.96: it passes rho=.95 but not
    # rho=1-.05/3. This verifies that rho_i must be part of I1.
    assert abs(float(rho095["sigma_hat"]) - 1.0) < 1e-12
    assert abs(float(rho_equal["sigma_hat"]) - 0.5) < 1e-12
    assert int(rho_equal["n_success"]) == 1
    assert int(rho_equal["n_trajectories"]) == 2
    assert (
        float(rho_equal["sigma_ci95_lower"])
        <= float(rho_equal["sigma_hat"])
        <= float(rho_equal["sigma_ci95_upper"])
    )

    lower, upper = wilson_binomial_interval(1, 2)
    assert 0.0 <= lower < 0.5 < upper <= 1.0

    try:
        query_i1_provider_card_exact(
            surface,
            l_max=0.51,
            c_max=1.0,
            q_min=0.5,
            rho=0.95,
            horizon=30.0,
        )
    except KeyError:
        pass
    else:
        raise AssertionError("I1 v1 must reject unsupported/interpolated queries")

    with tempfile.TemporaryDirectory() as temporary_directory:
        card_directory = Path(temporary_directory) / "ProviderA"
        write_i1_provider_card(metadata, surface, card_directory)
        loaded_metadata, loaded_surface = load_i1_provider_card(card_directory)
        assert loaded_metadata["schema"] == I1_CARD_SCHEMA
        assert len(loaded_surface) == len(surface)
        assert "seed" not in loaded_surface.columns

    print("PHASE2_I1_PROVIDER_CARD_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
