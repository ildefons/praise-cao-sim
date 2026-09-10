"""Regression tests for direct provider-local A_i diagnostic helpers."""
from __future__ import annotations

import pandas as pd

from diagnose_direct_i1_local_ar import (
    build_local_mixed_candidates,
    empirical_higher_quantile,
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

    print("PHASE2_DIRECT_LOCAL_AR_DIAGNOSTIC_TESTS_PASS")


if __name__ == "__main__":
    main()
