"""Regression tests for direct provider-local A_i diagnostic helpers."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1"
if str(PHASE1) not in sys.path:
    sys.path.insert(0, str(PHASE1))

from diagnose_direct_i1_local_ar import (  # noqa: E402
    REPORT_HORIZONS,
    _trajectory_arrays,
    build_local_mixed_candidates,
    empirical_higher_quantile,
    evaluate_candidate_fast,
)
from sla_compliance_analysis import (  # noqa: E402
    SlaComplianceDefinition,
    build_request_sla_decision_table,
    calculate_empirical_sla_sigma_from_decision_tables,
    calculate_exact_empirical_sla_compliance_area,
)


def main() -> None:
    ledger = pd.DataFrame(
        {
            "trajectory": [0, 0, 0, 0, 0],
            "request_id": [1, 2, 3, 4, 5],
            "emission": [0.0, 1.0, 2.0, 3.0, 4.0],
            "completion": [0.1, 1.2, 2.3, 3.4, 4.5],
            "L": [0.1, 0.2, 0.3, 0.4, 0.5],
            "C": [1.0, 2.0, 3.0, 4.0, 5.0],
            "Q": [0.5, 0.5, 0.5, 0.5, 0.5],
        }
    )

    assert empirical_higher_quantile(ledger["L"], 0.50) == 0.3
    assert empirical_higher_quantile(ledger["C"], 0.90) == 5.0

    levels = [0.50, 0.90]
    candidates = build_local_mixed_candidates(ledger, "ProviderX", levels)
    assert len(candidates) == 4
    assert all(candidate["provider"] == "ProviderX" for candidate in candidates)
    assert all(candidate["q_min"] == 0.5 for candidate in candidates)

    expected = {
        (0.50, 0.50): (0.3, 3.0),
        (0.50, 0.90): (0.3, 5.0),
        (0.90, 0.50): (0.5, 3.0),
        (0.90, 0.90): (0.5, 5.0),
    }
    for candidate in candidates:
        key = (candidate["latency_quantile"], candidate["cost_quantile"])
        assert (candidate["l_max"], candidate["c_max"]) == expected[key]
        assert "A_G" not in candidate
        assert "rho" not in candidate

    # Numerical-equivalence regression: the fast NumPy path must reproduce the
    # frozen Phase-1 request decision, exact-area and sigma semantics.
    two_trajectory_ledger = pd.concat(
        [
            ledger.assign(trajectory=0),
            ledger.assign(
                trajectory=1,
                completion=[0.15, 1.25, 2.8, 3.45, np.nan],
                L=[0.15, 0.25, 0.8, 0.45, np.nan],
                C=[1.2, 1.8, 3.5, 4.1, np.nan],
            ),
        ],
        ignore_index=True,
    )
    candidate = {
        "provider": "ProviderX",
        "candidate_id": "equivalence",
        "latency_quantile": 0.0,
        "cost_quantile": 0.0,
        "l_max": 0.4,
        "c_max": 3.0,
        "q_min": 0.5,
    }
    rho_values = (0.50, 0.75, 0.95)
    stop_time = 240.0
    fast = evaluate_candidate_fast(
        _trajectory_arrays(two_trajectory_ledger),
        candidate,
        rho_values,
        stop_time,
    )

    reference_tables = []
    for _, trajectory in two_trajectory_ledger.groupby("trajectory", sort=True):
        reference_tables.append(
            build_request_sla_decision_table(
                trajectory,
                latency_threshold=float(candidate["l_max"]),
                cost_threshold=float(candidate["c_max"]),
                quality_threshold=float(candidate["q_min"]),
                stop_time=stop_time,
            )
        )

    for rho in rho_values:
        definition = SlaComplianceDefinition(
            rho=rho, accounting_origin=0.0, zero_decision_compliance=1.0
        )
        _, reference_area = calculate_exact_empirical_sla_compliance_area(
            reference_tables, definition, 0.0, stop_time
        )
        tag = str(rho).replace(".", "p")
        assert abs(fast[f"R_{tag}"] - reference_area) < 1e-12

        reference_sigma, _ = calculate_empirical_sla_sigma_from_decision_tables(
            reference_tables, REPORT_HORIZONS, definition
        )
        by_h = reference_sigma.set_index("horizon")["sigma"]
        assert abs(fast[f"sigma120_{tag}"] - float(by_h.loc[120.0])) < 1e-12
        assert abs(fast[f"sigma240_{tag}"] - float(by_h.loc[240.0])) < 1e-12

    print("PHASE2_DIRECT_LOCAL_AR_DIAGNOSTIC_TESTS_PASS")
    print("FAST_PATH_EQUIVALENCE_TO_FROZEN_ACCOUNTING_PASS")


if __name__ == "__main__":
    main()
