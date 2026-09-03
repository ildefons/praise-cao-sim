"""Prepare the untouched final Phase-1 N=100 confirmation inputs.

This step is run only after the top-five N=10 shortlist has been screened on the
separate N=100 stability/calibration bank. It freezes the selected matched
latency/cost/mixed battery and constructs an effective confirmation
configuration using the predeclared untouched final seed bank.

No simulation is executed here and no A, rho, or SLA-area gate is recalibrated.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

REQUIRED_ROLES = {"latency", "cost", "mixed"}
EXPECTED_SELECTED_STATUS = (
    "SELECTED_AFTER_N100_STABILITY_CALIBRATION_REQUIRES_FRESH_FINAL_CONFIRMATION"
)
EXPECTED_PROTOCOL_STATUS = "FROZEN_PHASE1_N100_SHORTLIST_CALIBRATION_V1"


def _seed_set(values: Any) -> set[int]:
    if not isinstance(values, list):
        return set()
    return set(map(int, values))


def build_final_confirmation_inputs(
    discovery: dict[str, Any],
    protocol: dict[str, Any],
    selected: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate calibration output and build frozen final inputs."""
    if protocol.get("status") != EXPECTED_PROTOCOL_STATUS:
        raise ValueError("unexpected shortlist calibration protocol status")
    if selected.get("status") != EXPECTED_SELECTED_STATUS:
        raise ValueError(
            "selected calibration manifest is not ready for final confirmation"
        )

    whiteboxes = selected.get("whiteboxes")
    if not isinstance(whiteboxes, list) or len(whiteboxes) != 3:
        raise ValueError("final matched battery must contain exactly 3 whiteboxes")
    if {str(w.get("selection_role")) for w in whiteboxes} != REQUIRED_ROLES:
        raise ValueError("final battery must contain latency, cost and mixed roles")
    setting_ids = {str(w.get("physical_setting_id")) for w in whiteboxes}
    if len(setting_ids) != 1:
        raise ValueError("final whiteboxes must share one physical setting")
    selected_setting = str(selected.get("physical_setting_id"))
    if setting_ids != {selected_setting}:
        raise ValueError("selected physical setting disagrees with whiteboxes")

    calibration_seeds = list(map(int, protocol["calibration"]["seed_bank"]))
    final_seeds = list(map(int, protocol["final_confirmation"]["seed_bank"]))
    if len(calibration_seeds) != 100 or len(set(calibration_seeds)) != 100:
        raise ValueError("shortlist calibration must contain 100 unique seeds")
    if len(final_seeds) != 100 or len(set(final_seeds)) != 100:
        raise ValueError("final confirmation must contain 100 unique seeds")

    manifest_final_seeds = list(
        map(int, selected.get("final_confirmation_seed_bank", []))
    )
    if manifest_final_seeds != final_seeds:
        raise ValueError(
            "selected manifest final seed bank differs from frozen protocol"
        )
    manifest_calibration_seeds = list(
        map(int, selected.get("calibration_seed_bank", []))
    )
    if manifest_calibration_seeds != calibration_seeds:
        raise ValueError(
            "selected manifest calibration bank differs from frozen protocol"
        )

    old_confirmation = list(
        map(int, discovery["confirmation"]["confirmation_seed_bank"])
    )
    prior_banks = {
        "development_smoke": list(
            map(int, discovery["development_smoke"]["seed_bank"])
        ),
        "n10_discovery": list(
            map(int, discovery["discovery_search"]["calibration_seed_bank"])
        ),
        "first_passage_exploratory": list(
            map(
                int,
                discovery.get("confirmation_round_1_exploratory", {}).get(
                    "seed_bank", []
                ),
            )
        ),
        "sla_protocol_v1_n100": old_confirmation,
        "n100_shortlist_calibration_v1": calibration_seeds,
    }
    final_set = set(final_seeds)
    for name, bank in prior_banks.items():
        if final_set.intersection(bank):
            raise ValueError(
                f"final confirmation seeds overlap previously inspected bank {name}"
            )

    final_manifest = deepcopy(selected)
    final_manifest["status"] = "FROZEN_FOR_CONFIRMATION"
    final_manifest["paired_matched_physical_regime"] = True
    final_manifest["freeze_semantics"] = (
        "Selected solely by the predeclared N10 ordering plus the N100 shortlist "
        "stability gate. A, rho and the SLA-area gate are frozen. The final "
        "5000..5099 bank is untouched and may not be used for recalibration."
    )
    final_manifest["prior_calibration_status"] = EXPECTED_SELECTED_STATUS

    final_config = deepcopy(discovery)
    final_config["confirmation"]["confirmation_seed_bank"] = final_seeds
    final_config["confirmation"]["seed_bank_status"] = (
        "FROZEN_UNTOUCHED_AFTER_N100_SHORTLIST_CALIBRATION"
    )
    final_config["confirmation"]["purpose"] = (
        "untouched final paired N100 confirmation after N10 discovery and "
        "N100 shortlist stability calibration; no recalibration of A or rho"
    )
    final_config["confirmation"]["frozen_after_selection"] = selected_setting
    final_config["prior_inspected_seed_banks"] = prior_banks
    final_config["final_confirmation_provenance"] = {
        "selected_shortlist_rank": int(selected["selected_shortlist_rank"]),
        "selected_triplet_score": int(selected["selected_triplet_score"]),
        "physical_setting_id": selected_setting,
        "shortlist_calibration_seed_bank": calibration_seeds,
        "final_confirmation_seed_bank": final_seeds,
        "selection_rule": selected.get("selection_rule"),
    }
    return final_config, final_manifest


def execute_prepare(
    discovery_config_path: Path,
    shortlist_config_path: Path,
    selected_calibration_path: Path,
    final_config_path: Path,
    final_selected_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    discovery = json.loads(discovery_config_path.read_text(encoding="utf-8"))
    protocol = json.loads(shortlist_config_path.read_text(encoding="utf-8"))
    selected = json.loads(selected_calibration_path.read_text(encoding="utf-8"))
    final_config, final_manifest = build_final_confirmation_inputs(
        discovery, protocol, selected
    )
    final_config_path.write_text(
        json.dumps(final_config, indent=2), encoding="utf-8"
    )
    final_selected_path.write_text(
        json.dumps(final_manifest, indent=2), encoding="utf-8"
    )
    print("PHASE1_FINAL_N100_PREPARATION_PASS")
    print(
        f"selected_shortlist_rank={final_manifest['selected_shortlist_rank']} "
        f"physical_setting_id={final_manifest['physical_setting_id']}"
    )
    print(
        "final_seed_bank="
        f"{final_config['confirmation']['confirmation_seed_bank'][0]}.."
        f"{final_config['confirmation']['confirmation_seed_bank'][-1]}"
    )
    print(f"final_config={final_config_path.resolve()}")
    print(f"final_selected={final_selected_path.resolve()}")
    return final_config, final_manifest


def main() -> None:
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--discovery-config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--shortlist-config",
        type=Path,
        default=module_directory
        / "config_phase1_n100_shortlist_calibration_v1.json",
    )
    parser.add_argument(
        "--selected-calibration",
        type=Path,
        default=module_directory
        / "selected_whiteboxes_after_n100_calibration.json",
    )
    parser.add_argument(
        "--final-config",
        type=Path,
        default=module_directory / "config_phase1_final_confirmation_v1.json",
    )
    parser.add_argument(
        "--final-selected",
        type=Path,
        default=module_directory
        / "selected_whiteboxes_final_confirmation_v1.json",
    )
    args = parser.parse_args()
    execute_prepare(
        args.discovery_config.resolve(),
        args.shortlist_config.resolve(),
        args.selected_calibration.resolve(),
        args.final_config.resolve(),
        args.final_selected.resolve(),
    )


if __name__ == "__main__":
    main()
