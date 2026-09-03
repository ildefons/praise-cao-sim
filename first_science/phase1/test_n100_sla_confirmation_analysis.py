"""Simulator-independent tests for N=100 SLA confirmation analysis."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from run_n100_matched_confirmation import analyze_and_plot_n100_confirmation


def build_configuration():
    return {
        "sla_compliance": {
            "search_rho": 0.95,
            "accounting_origin": 0.0,
            "zero_decided_requests_compliance": 1.0,
            "accounting_window": "cumulative_[0,H]_from_t0",
            "rolling_windows_allowed": False,
        },
        "selection_quality_gate": {
            "metric": "normalized_sla_compliance_area",
            "normalized_sla_compliance_area": {
                "horizon_min": 0.0,
                "horizon_max": 20.0,
                "minimum": 0.2,
                "maximum": 0.9,
                "optimize_to_midpoint": False,
            },
            "role_evidence": {"dominance_ratio": 2.0},
        },
        "horizon": {
            "simulation_stop_time": 20.0,
            "grid": [0.0, 5.0, 10.0, 15.0, 20.0],
        },
        "admissibility_calibration": {"anchor_horizon": 10.0},
    }


def build_manifest():
    return {
        "whiteboxes": [
            {
                "case_id": "WB_L",
                "selection_role": "latency",
                "physical_setting_id": "P",
                "center_instruction_mean": 1.0,
                "dispersion": 0.0,
                "l_max": 2.0,
                "c_max": 10.0,
                "q_min": 0.5,
            },
            {
                "case_id": "WB_C",
                "selection_role": "cost",
                "physical_setting_id": "P",
                "center_instruction_mean": 1.0,
                "dispersion": 0.0,
                "l_max": 5.0,
                "c_max": 1.5,
                "q_min": 0.5,
            },
            {
                "case_id": "WB_M",
                "selection_role": "mixed",
                "physical_setting_id": "P",
                "center_instruction_mean": 1.0,
                "dispersion": 0.0,
                "l_max": 2.0,
                "c_max": 1.5,
                "q_min": 0.5,
            },
        ]
    }


def build_ledgers():
    rows = []
    for trajectory in range(100):
        for request_id in range(16):
            emission = float(request_id)
            late = request_id % 4 == 0
            high_cost = request_id % 4 == 1
            latency = 3.0 if late else 1.0
            rows.append(
                {
                    "physical_setting_id": "P",
                    "center_instruction_mean": 1.0,
                    "dispersion": 0.0,
                    "trajectory": trajectory,
                    "seed": 4000 + trajectory,
                    "request_id": request_id,
                    "emission": emission,
                    "completion": emission + latency,
                    "completed_by_stop": True,
                    "status": "completed",
                    "L": latency,
                    "C": 2.0 if high_cost else 1.0,
                    "Q": 0.5,
                    "stop_time": 20.0,
                }
            )
    return pd.DataFrame(rows)


def test_analysis_writes_sla_sigma_and_visual_outputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        summary = analyze_and_plot_n100_confirmation(
            build_configuration(), build_manifest(), build_ledgers(), output
        )
        assert len(summary) == 3
        assert set(summary["observed_request_failure_role"]) == {"latency", "cost", "mixed"}
        assert (output / "sigma_curves.csv").exists()
        assert (output / "sla_request_decisions.csv").exists()
        assert (output / "n100_matched_sla_sigma_curves.png").exists()
        assert (output / "n100_final_trajectory_compliance_ecdf.png").exists()


def run_all_tests() -> None:
    test_analysis_writes_sla_sigma_and_visual_outputs()
    print("PHASE1_N100_SLA_CONFIRMATION_ANALYSIS_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
