"""Simulator-independent smoke tests for the Phase-1 SLA sigma revision."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from selection_policy import load_sla_compliance_area_selection_policy
from sla_compliance_analysis import (
    SlaComplianceDefinition,
    calculate_exact_trajectory_sla_compliance_area,
    calculate_trajectory_cumulative_sla_curve,
)


def test_frozen_search_semantics() -> None:
    """Verify rho*=0.95, cumulative [0,H] and the configured area gate."""
    configuration = json.loads(
        Path(__file__).with_name("config_phase1_discovery_v1.json").read_text(
            encoding="utf-8"
        )
    )
    policy = load_sla_compliance_area_selection_policy(configuration)
    assert abs(policy.sla_definition.rho - 0.95) < 1e-12
    assert abs(policy.sla_definition.accounting_origin) < 1e-12
    assert policy.sla_definition.zero_decision_compliance == 1.0
    assert policy.horizon_min == 0.0
    assert policy.horizon_max == 240.0
    assert policy.area_min == 0.5
    assert policy.area_max == 0.75
    assert policy.optimize_to_midpoint is False


def test_cumulative_sla_can_fail_and_recover() -> None:
    """Verify the new sigma state is not forced to be monotone survival."""
    definition = SlaComplianceDefinition(rho=0.95)
    decision_times = list(range(1, 21))
    compliant = [False] + [True] * 19
    decisions = pd.DataFrame(
        {
            "decision_time": decision_times,
            "compliant": pd.array(compliant, dtype="boolean"),
        }
    )
    curve = calculate_trajectory_cumulative_sla_curve(
        decisions,
        horizons=[0.0, 1.0, 19.0, 20.0, 24.0],
        sla_definition=definition,
    )
    assert list(curve["sla_compliant"].astype(bool)) == [True, False, False, True, True]
    area_seconds, normalized = calculate_exact_trajectory_sla_compliance_area(
        decisions,
        definition,
        horizon_min=0.0,
        horizon_max=24.0,
    )
    assert abs(area_seconds - 5.0) < 1e-12
    assert abs(normalized - 5.0 / 24.0) < 1e-12


def run_all_tests() -> None:
    """Run the Phase-1 SLA semantic smoke tests."""
    test_frozen_search_semantics()
    test_cumulative_sla_can_fail_and_recover()
    print("PHASE1_SLA_REVISION_SMOKE_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
