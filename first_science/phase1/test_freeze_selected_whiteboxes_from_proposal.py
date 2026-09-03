"""Tests for exact-value freezing of the agreed SLA-native N=10 finalists."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from freeze_selected_whiteboxes_from_proposal import freeze_selected_whiteboxes


def build_test_proposal() -> dict:
    """Build a compact proposal with deliberately high-precision thresholds."""
    whiteboxes = []
    for role, region, l_max, c_max in (
        ("latency", "D330000000_d0.150_SLA_A0002", 0.674480123456789, 2.854752123456789),
        ("cost", "D330000000_d0.150_SLA_A0007", 240.0, 1.966112123456789),
        ("mixed", "D330000000_d0.150_SLA_A0028", 0.798021123456789, 2.071415123456789),
    ):
        whiteboxes.append({
            "case_id": f"WB_{role}",
            "selection_role": role,
            "physical_setting_id": "D330000000_d0.150",
            "source_region_id": region,
            "center_instruction_mean": 330000000.0,
            "dispersion": 0.15,
            "l_max": l_max,
            "c_max": c_max,
            "q_min": 0.5,
            "rho": 0.95,
            "accounting_origin": 0.0,
            "accounting_window": "cumulative_[0,H]_from_t0",
        })
    return {
        "status": "PROPOSED_FROM_N10_SLA_DISCOVERY_REQUIRES_REVIEW",
        "search_rho": 0.95,
        "accounting_window": "cumulative_[0,H]_from_t0",
        "paired_matched_physical_regime": True,
        "whiteboxes": whiteboxes,
    }


def test_freeze_preserves_exact_threshold_values() -> None:
    """Verify freezing copies float values rather than rounded console text."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        proposal_path = root / "proposal.json"
        output_path = root / "selected.json"
        proposal = build_test_proposal()
        proposal_path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
        frozen = freeze_selected_whiteboxes(proposal_path, output_path)
        assert frozen["status"] == "FROZEN_FOR_CONFIRMATION"
        for before, after in zip(proposal["whiteboxes"], frozen["whiteboxes"]):
            assert before["l_max"] == after["l_max"]
            assert before["c_max"] == after["c_max"]


def run_all_tests() -> None:
    """Run finalist-freeze tests."""
    test_freeze_preserves_exact_threshold_values()
    print("PHASE1_SLA_WHITEBOX_FREEZE_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
