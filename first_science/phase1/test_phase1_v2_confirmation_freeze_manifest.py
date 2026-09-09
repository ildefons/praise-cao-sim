"""Simulator-independent validation of the frozen Phase-1 v2 confirmation result."""
from __future__ import annotations

import json
from pathlib import Path

EXPECTED_STATUS = "FROZEN_PHASE1_V2_CONFIRMED_V1"
EXPECTED_SETTING = "D300000000_d0.200"
EXPECTED_ROLES = {"latency", "cost", "mixed"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_all_tests() -> None:
    here = Path(__file__).resolve().parent
    result = _load(here / "phase1_v2_confirmation_freeze_manifest_v1.json")
    ar = _load(here / "phase1_v2_ar_freeze_manifest_v1.json")
    protocol = _load(here / "config_phase1_v2_confirmation_v1.json")

    assert result["status"] == EXPECTED_STATUS
    assert result["physical_setting_id"] == EXPECTED_SETTING
    assert result["scientific_confirmation_pass"] is True
    assert result["selection_reopened"] is False
    assert result["recalibration_performed"] is False
    assert int(result["n_trajectories"]) == 100
    assert int(result["seed_bank_start"]) == 7000
    assert int(result["seed_bank_end_inclusive"]) == 7099
    assert result["common_seed_bank_across_three_regions"] is True

    assert ar["status"] == "FROZEN_PHASE1_V2_AR_SELECTION_V1"
    assert protocol["status"] == "FROZEN_PHASE1_V2_CONFIRMATION_PROTOCOL_V1"
    assert list(map(int, protocol["seed_bank"])) == list(range(7000, 7100))
    assert list(map(int, ar["fresh_confirmation"]["seed_bank"])) == list(range(7000, 7100))

    cases = result["cases"]
    assert len(cases) == 3
    assert {str(c["selection_role"]) for c in cases} == EXPECTED_ROLES
    assert {str(c["descriptive_role"]) for c in cases} == EXPECTED_ROLES

    frozen_regions = {
        str(w["selection_role"]): str(w["region_id"])
        for w in ar["whiteboxes"]
    }

    for case in cases:
        role = str(case["selection_role"])
        assert str(case["region_id"]) == frozen_regions[role]
        assert case["role_replication_pass"] is True
        assert case["nominal_health_pass"] is True
        assert case["stress_informativeness_pass"] is True
        assert case["fresh_confirmation_pass"] is True
        assert float(case["area_rho_0p95"]) >= 0.95
        assert 0.50 <= float(case["area_rho_0p99"]) <= 0.95

    by_role = {str(c["selection_role"]): c for c in cases}
    assert int(by_role["latency"]["latency_failure_count"]) >= 2 * max(
        int(by_role["latency"]["cost_failure_count"]), 1
    )
    assert int(by_role["cost"]["cost_failure_count"]) >= 2 * max(
        int(by_role["cost"]["latency_failure_count"]), 1
    )
    mixed_l = int(by_role["mixed"]["latency_failure_count"])
    mixed_c = int(by_role["mixed"]["cost_failure_count"])
    assert mixed_l > 0 and mixed_c > 0
    assert mixed_l < 2 * mixed_c
    assert mixed_c < 2 * mixed_l

    print("PHASE1_V2_CONFIRMATION_FREEZE_MANIFEST_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
