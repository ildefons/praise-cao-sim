"""Simulator-independent tests for the Phase-2 I1 acquisition extractor."""
from __future__ import annotations

import pandas as pd

from i1_provider_acquisition import (
    extract_provider_local_ledgers_from_metric_rows,
)


def synthetic_configuration() -> dict:
    return {
        "topology": {
            "branch_bytes": 1000,
            "network_bw_mbps": 1000.0,
            "network_pr": 0.001,
        },
        "provider_family": {"cost_rate": 3.0},
    }


def synthetic_metric_rows() -> pd.DataFrame:
    delay = 0.001 + 1000.0 / (1000.0 * 1_000_000.0)
    rows = [
        # Two completed Fpre requests release one branch to every provider.
        {"id": 1, "module": "Fpre", "time_out": 0.100, "time_reception": 0.090, "service": 0.010, "qos": 0.5},
        {"id": 2, "module": "Fpre", "time_out": 0.300, "time_reception": 0.290, "service": 0.010, "qos": 0.5},
    ]
    for provider, extra in (("ProviderA", 0.00), ("ProviderB", 0.01), ("ProviderC", 0.02)):
        arrival1 = 0.100 + delay
        completion1 = arrival1 + 0.100 + extra
        rows.append(
            {
                "id": 1,
                "module": provider,
                "time_out": completion1,
                "time_reception": arrival1,
                "service": 0.100 + extra,
                "qos": 0.5,
            }
        )
        # Request 2 has arrived at the provider but has no service metric row.
        # The extractor must still retain it as an unresolved local request.
    return pd.DataFrame(rows)


def run_all_tests() -> None:
    ledgers = extract_provider_local_ledgers_from_metric_rows(
        synthetic_metric_rows(),
        synthetic_configuration(),
        trajectory=7,
        stop_time=1.0,
    )
    assert set(ledgers) == {"ProviderA", "ProviderB", "ProviderC"}
    delay = 0.001 + 1000.0 / (1000.0 * 1_000_000.0)

    for provider_index, provider in enumerate(("ProviderA", "ProviderB", "ProviderC")):
        ledger = ledgers[provider]
        assert list(ledger.columns) == [
            "trajectory", "request_id", "emission", "completion", "L", "C", "Q"
        ]
        assert len(ledger) == 2
        assert set(ledger["trajectory"].astype(int)) == {7}

        first = ledger[ledger["request_id"] == 1].iloc[0]
        expected_service = 0.100 + 0.01 * provider_index
        assert abs(float(first["emission"]) - (0.100 + delay)) < 1e-12
        assert abs(float(first["L"]) - expected_service) < 1e-12
        assert abs(float(first["C"]) - 3.0 * expected_service) < 1e-12
        assert abs(float(first["Q"]) - 0.5) < 1e-12

        second = ledger[ledger["request_id"] == 2].iloc[0]
        assert abs(float(second["emission"]) - (0.300 + delay)) < 1e-12
        assert pd.isna(second["completion"])
        assert pd.isna(second["L"])
        assert pd.isna(second["C"])
        assert pd.isna(second["Q"])

    # Native time_reception is a semantic audit, not an optional hint.
    broken = synthetic_metric_rows()
    idx = broken.index[broken["module"] == "ProviderA"][0]
    broken.loc[idx, "time_reception"] += 0.01
    try:
        extract_provider_local_ledgers_from_metric_rows(
            broken,
            synthetic_configuration(),
            trajectory=0,
            stop_time=1.0,
        )
    except RuntimeError as error:
        assert "disagrees with reconstructed arrival" in str(error)
    else:
        raise AssertionError("provider reception mismatch must fail acquisition")

    print("PHASE2_I1_PROVIDER_ACQUISITION_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
