"""Simulator-independent tests for final Phase-1 N=100 preparation."""
from __future__ import annotations

import json
from pathlib import Path

from prepare_final_n100_confirmation import build_final_confirmation_inputs


def build_selected(protocol: dict) -> dict:
    whiteboxes = []
    for role, l_max, c_max in (
        ("latency", 1.0, 10.0),
        ("cost", 240.0, 2.0),
        ("mixed", 1.2, 2.2),
    ):
        whiteboxes.append(
            {
                "case_id": f"S4_{role}",
                "selection_role": role,
                "physical_setting_id": "D300000000_d0.200",
                "center_instruction_mean": 300000000.0,
                "dispersion": 0.2,
                "l_max": l_max,
                "c_max": c_max,
                "q_min": 0.5,
                "rho": 0.95,
                "accounting_origin": 0.0,
                "accounting_window": "cumulative_[0,H]_from_t0",
            }
        )
    return {
        "status": (
            "SELECTED_AFTER_N100_STABILITY_CALIBRATION_"
            "REQUIRES_FRESH_FINAL_CONFIRMATION"
        ),
        "selection_rule": "first passing battery in frozen N10 order",
        "selected_shortlist_rank": 4,
        "selected_triplet_score": 20,
        "physical_setting_id": "D300000000_d0.200",
        "calibration_seed_bank": protocol["calibration"]["seed_bank"],
        "final_confirmation_seed_bank": protocol["final_confirmation"]["seed_bank"],
        "rho": 0.95,
        "accounting_window": "cumulative_[0,H]_from_t0",
        "whiteboxes": whiteboxes,
    }


def run_all_tests() -> None:
    module_directory = Path(__file__).resolve().parent
    discovery = json.loads(
        (module_directory / "config_phase1_discovery_v1.json").read_text(
            encoding="utf-8"
        )
    )
    protocol = json.loads(
        (
            module_directory
            / "config_phase1_n100_shortlist_calibration_v1.json"
        ).read_text(encoding="utf-8")
    )
    selected = build_selected(protocol)
    final_config, final_manifest = build_final_confirmation_inputs(
        discovery, protocol, selected
    )
    assert final_manifest["status"] == "FROZEN_FOR_CONFIRMATION"
    assert final_manifest["physical_setting_id"] == "D300000000_d0.200"
    assert len(final_manifest["whiteboxes"]) == 3
    assert final_config["confirmation"]["confirmation_seed_bank"] == list(
        range(5000, 5100)
    )
    assert set(final_config["confirmation"]["confirmation_seed_bank"]).isdisjoint(
        final_config["prior_inspected_seed_banks"]["sla_protocol_v1_n100"]
    )
    assert set(final_config["confirmation"]["confirmation_seed_bank"]).isdisjoint(
        final_config["prior_inspected_seed_banks"][
            "n100_shortlist_calibration_v1"
        ]
    )
    print("PHASE1_FINAL_N100_PREPARATION_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
