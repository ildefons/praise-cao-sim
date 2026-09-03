"""Freeze the agreed Phase-1 SLA-native N=10 proposal for fresh N=100 confirmation.

The N=10 selector writes exact machine-precision thresholds into
``selected_whiteboxes_proposal.json``. This utility copies those exact values
into the tracked ``selected_whiteboxes.json`` manifest after checking that the
proposal is the agreed matched Dbar=330M, delta=0.15 latency/cost/mixed battery.
It never recomputes, rounds, or retunes A.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_SETTING_ID = "D330000000_d0.150"
EXPECTED_CENTER = 330000000.0
EXPECTED_DISPERSION = 0.15
EXPECTED_ROLES = {"latency", "cost", "mixed"}
EXPECTED_REGION_IDS = {
    "latency": "D330000000_d0.150_SLA_A0002",
    "cost": "D330000000_d0.150_SLA_A0007",
    "mixed": "D330000000_d0.150_SLA_A0028",
}


def freeze_selected_whiteboxes(proposal_path: Path, output_path: Path) -> dict:
    """Validate and freeze the exact N=10 SLA-native proposal.

    Args:
        proposal_path: Selector-produced proposal JSON containing exact values.
        output_path: Destination ``selected_whiteboxes.json``.

    Returns:
        Frozen manifest written to ``output_path``.

    Side effects:
        Writes the frozen selected-whitebox manifest.

    Called by:
        - ``main`` in this module.
        - ``test_freeze_selected_whiteboxes_from_proposal.py``.
    """
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    if proposal.get("status") != "PROPOSED_FROM_N10_SLA_DISCOVERY_REQUIRES_REVIEW":
        raise ValueError("proposal status is not the expected reviewed N=10 SLA proposal")
    if proposal.get("search_rho") != 0.95:
        raise ValueError("proposal rho must be exactly 0.95")
    if proposal.get("accounting_window") != "cumulative_[0,H]_from_t0":
        raise ValueError("proposal accounting window is inconsistent")
    if proposal.get("paired_matched_physical_regime") is not True:
        raise ValueError("agreed finalists must share one matched physical regime")

    whiteboxes = proposal.get("whiteboxes")
    if not isinstance(whiteboxes, list) or len(whiteboxes) != 3:
        raise ValueError("expected exactly three proposed whiteboxes")
    roles = {str(item["selection_role"]) for item in whiteboxes}
    if roles != EXPECTED_ROLES:
        raise ValueError(f"unexpected roles: {sorted(roles)}")

    for item in whiteboxes:
        role = str(item["selection_role"])
        if str(item["physical_setting_id"]) != EXPECTED_SETTING_ID:
            raise ValueError(f"{role}: unexpected physical setting")
        if abs(float(item["center_instruction_mean"]) - EXPECTED_CENTER) > 1e-6:
            raise ValueError(f"{role}: unexpected center instruction mean")
        if abs(float(item["dispersion"]) - EXPECTED_DISPERSION) > 1e-12:
            raise ValueError(f"{role}: unexpected dispersion")
        if str(item["source_region_id"]) != EXPECTED_REGION_IDS[role]:
            raise ValueError(f"{role}: unexpected SLA-native region id")
        if abs(float(item["rho"]) - 0.95) > 1e-12:
            raise ValueError(f"{role}: rho drift")
        if abs(float(item["accounting_origin"])) > 1e-12:
            raise ValueError(f"{role}: accounting origin drift")
        if item["accounting_window"] != "cumulative_[0,H]_from_t0":
            raise ValueError(f"{role}: accounting-window drift")

    frozen = dict(proposal)
    frozen["status"] = "FROZEN_FOR_CONFIRMATION"
    frozen["freeze_semantics"] = (
        "Exact machine-precision values copied unchanged from the reviewed N=10 "
        "SLA-native proposal. No A or rho recalibration is permitted on N=100."
    )
    frozen["confirmation_seed_bank"] = (
        "4000..4099 (configured separately in config_phase1_discovery_v1.json)"
    )
    output_path.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    print("PHASE1_SLA_WHITEBOX_FREEZE_PASS")
    print(f"output={output_path}")
    for item in frozen["whiteboxes"]:
        print(
            item["selection_role"],
            item["source_region_id"],
            f"L={float(item['l_max']):.17g}",
            f"C={float(item['c_max']):.17g}",
            f"Q={float(item['q_min']):.17g}",
        )
    return frozen


def main() -> None:
    """Command-line entry point for the one-time finalist freeze."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--proposal",
        type=Path,
        default=module_directory
        / "results"
        / "scientific_discovery_v1_full_domain_ar"
        / "whitebox_selection"
        / "selected_whiteboxes_proposal.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=module_directory / "selected_whiteboxes.json",
    )
    args = parser.parse_args()
    freeze_selected_whiteboxes(args.proposal.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
