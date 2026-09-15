"""Native AICon/YAFS smoke test for the M1 single-provider lift adapter."""
from __future__ import annotations

import pandas as pd

from m1_single_provider_simulator import (
    SingleProviderSurrogateParameters,
    execute_one_single_provider_trajectory,
    nominal_instruction_mean,
    simulate_deterministic_compliance_surface,
    simulate_stochastic_sigma_surface,
)


def _fake_public_card() -> tuple[dict[str, object], pd.DataFrame]:
    metadata: dict[str, object] = {
        "provider_id": "ProviderA",
        "workload_contract": {
            "period": 0.2,
            "accounting_origin": 0.0,
            "horizon_max": 2.0,
        },
        "supported_horizons": [0.0, 0.5, 1.0, 2.0],
        "supported_query_rho_values": [0.95, 0.99],
        "rho_conditioned_regions": [
            {
                "region_id": "A95",
                "region_rho": 0.95,
                "l_max": 0.11,
                "c_max": 0.21,
                "q_min": 0.5,
            }
        ],
    }
    rows = []
    for rho in metadata["supported_query_rho_values"]:
        for horizon in metadata["supported_horizons"]:
            rows.append(
                {
                    "provider_id": "ProviderA",
                    "region_id": "A95",
                    "region_rho": 0.95,
                    "l_max": 0.11,
                    "c_max": 0.21,
                    "q_min": 0.5,
                    "rho": float(rho),
                    "horizon": float(horizon),
                    "sigma_hat": 1.0,
                }
            )
    return metadata, pd.DataFrame(rows)


def main() -> None:
    instruction_mean = nominal_instruction_mean(
        0.1, canonical_ipt=1_000_000.0, execution_fraction=0.5
    )
    assert abs(instruction_mean - 200_000.0) <= 1e-12

    workload = {"period": 0.2, "accounting_origin": 0.0, "horizon_max": 2.0}
    ledger = execute_one_single_provider_trajectory(
        provider_id="ProviderA",
        parameters=SingleProviderSurrogateParameters(
            mean_service_time=0.1,
            cost_rate=2.0,
            service_cv=0.0,
        ),
        workload_contract=workload,
        trajectory_seed=123,
    )
    assert len(ledger) == 10
    completed = ledger[ledger["completed_by_stop"]].copy()
    assert not completed.empty
    assert (completed["L"].astype(float) > 0.0).all()
    assert (completed["Q"].astype(float) == 0.5).all()
    assert (completed["C"].astype(float) > 0.0).all()

    metadata, public_surface = _fake_public_card()
    deterministic = simulate_deterministic_compliance_surface(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=0.1,
        cost_rate=2.0,
    )
    assert len(deterministic) == 4
    assert set(deterministic["provider_id"]) == {"ProviderA"}
    assert deterministic["compliance_fraction"].between(0.0, 1.0).all()

    stochastic = simulate_stochastic_sigma_surface(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=0.1,
        cost_rate=2.0,
        service_cv=0.2,
        trajectory_seeds=[100, 101, 102],
    )
    assert len(stochastic) == 8
    assert stochastic["sigma_hat"].between(0.0, 1.0).all()
    assert set(stochastic["n_trajectories"].astype(int)) == {3}

    print("PHASE3_M1_SINGLE_PROVIDER_SIMULATOR_SMOKE_PASS")
    print("M1_NATIVE_SERVICE_TIME_MAPPING_PASS")
    print("M1_PROVIDER_LOCAL_LEDGER_PASS")
    print("M1_STOCHASTIC_LOCAL_SIGMA_SURFACE_PASS")


if __name__ == "__main__":
    main()
