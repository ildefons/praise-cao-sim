"""Simulator-independent validation of the frozen Phase-1 v2 AR manifest."""
from __future__ import annotations

import json
from pathlib import Path

EXPECTED_STATUS = "FROZEN_PHASE1_V2_AR_SELECTION_V1"
EXPECTED_SETTING = "D300000000_d0.200"
EXPECTED_ROLES = {"latency", "cost", "mixed"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_all_tests() -> None:
    here = Path(__file__).resolve().parent
    manifest = _load(here / "phase1_v2_ar_freeze_manifest_v1.json")
    discovery = _load(here / "config_phase1_discovery_v1.json")
    shortlist = _load(here / "config_phase1_n100_shortlist_calibration_v1.json")
    phase2 = _load(here.parent / "phase2" / "config_phase2_i1_acquisition_v1.json")

    assert manifest["status"] == EXPECTED_STATUS
    assert manifest["physical_setting"]["physical_setting_id"] == EXPECTED_SETTING
    assert manifest["paired_matched_physical_regime"] is True

    sigma = manifest["sigma_query"]
    assert abs(float(sigma["primary_rho"]) - 0.95) < 1e-12
    assert abs(float(sigma["stress_rho"]) - 0.99) < 1e-12
    assert abs(float(sigma["intermediate_diagnostic_rho"]) - 0.975) < 1e-12
    assert sigma["accounting_window"] == "cumulative_[0,H]_from_t0"
    assert abs(float(sigma["accounting_origin"])) < 1e-12

    policy = manifest["selection_policy"]
    assert policy["revision"] == "HEALTHY_NOMINAL_PLUS_STRESS_MULTI_RHO_V2"
    assert abs(float(policy["nominal_health_gate"]["minimum"]) - 0.95) < 1e-12
    assert abs(float(policy["stress_informativeness_gate"]["minimum"]) - 0.50) < 1e-12
    assert abs(float(policy["stress_informativeness_gate"]["maximum"]) - 0.95) < 1e-12
    assert policy["intermediate_rho_is_selection_gate"] is False
    assert policy["midpoint_optimization"] is False
    assert abs(float(policy["role_dominance_ratio"]) - 2.0) < 1e-12
    assert abs(float(policy["threshold_relative_epsilon"]) - 1e-9) < 1e-18
    assert policy["selection_may_not_be_reopened_after_fresh_confirmation"] is True

    whiteboxes = manifest["whiteboxes"]
    assert len(whiteboxes) == 3
    assert {str(w["selection_role"]) for w in whiteboxes} == EXPECTED_ROLES
    assert {str(w["physical_setting_id"]) for w in whiteboxes} == {EXPECTED_SETTING}
    assert {float(w["center_instruction_mean"]) for w in whiteboxes} == {300000000.0}
    assert {float(w["dispersion"]) for w in whiteboxes} == {0.2}
    assert {float(w["rho"]) for w in whiteboxes} == {0.95}

    expected = {
        "latency": (
            "D300000000_d0.200_FDC_00026",
            "FULL_DOMAIN_LOOSE_COST",
            0.68855284199994315,
            2.60390295517990822,
        ),
        "cost": (
            "D300000000_d0.200_A00933",
            "ORIGINAL_ANCHOR_INFORMED",
            0.74739413900001495,
            2.13979268099999986,
        ),
        "mixed": (
            "D300000000_d0.200_A00936",
            "ORIGINAL_ANCHOR_INFORMED",
            0.74739413900001495,
            2.17409932499999980,
        ),
    }

    nominal_min = float(policy["nominal_health_gate"]["minimum"])
    stress_min = float(policy["stress_informativeness_gate"]["minimum"])
    stress_max = float(policy["stress_informativeness_gate"]["maximum"])

    for whitebox in whiteboxes:
        role = str(whitebox["selection_role"])
        region_id, source, l_max, c_max = expected[role]
        assert whitebox["region_id"] == region_id
        assert whitebox["source_family"] == source
        assert abs(float(whitebox["l_max"]) - l_max) < 1e-15
        assert abs(float(whitebox["c_max"]) - c_max) < 1e-15
        assert abs(float(whitebox["q_min"]) - 0.5) < 1e-12
        assert float(whitebox["calibration_R_0p95"]) >= nominal_min
        assert stress_min <= float(whitebox["calibration_R_0p99"]) <= stress_max

    calibration = manifest["calibration_provenance"]
    assert calibration["request_ledger_bank_has_been_inspected"] is True
    assert calibration["request_ledger_bank_may_be_reused_for_v2_final_confirmation"] is False
    assert int(calibration["n_distinct_candidates"]) == 1056

    confirmation = manifest["fresh_confirmation"]
    seeds = list(map(int, confirmation["seed_bank"]))
    assert confirmation["required"] is True
    assert int(confirmation["n_trajectories"]) == 100
    assert seeds == list(range(7000, 7100))
    assert len(set(seeds)) == 100
    assert confirmation["recalibrate_A"] is False
    assert confirmation["recalibrate_rho"] is False
    assert confirmation["reopen_selection_gate"] is False

    prior: set[int] = set(map(int, discovery["development_smoke"]["seed_bank"]))
    prior |= set(map(int, discovery["discovery_search"]["calibration_seed_bank"]))
    prior |= set(map(int, discovery.get("confirmation_round_1_exploratory", {}).get("seed_bank", [])))
    prior |= set(map(int, discovery["confirmation"]["confirmation_seed_bank"]))
    prior |= set(map(int, shortlist["calibration"]["seed_bank"]))
    prior |= set(map(int, shortlist["final_confirmation"]["seed_bank"]))
    phase2_start = int(phase2["acquisition"]["seed_start"])
    phase2_end = int(phase2["acquisition"]["seed_end_inclusive"])
    prior |= set(range(phase2_start, phase2_end + 1))
    assert not prior.intersection(seeds)

    print("PHASE1_V2_AR_FREEZE_MANIFEST_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
