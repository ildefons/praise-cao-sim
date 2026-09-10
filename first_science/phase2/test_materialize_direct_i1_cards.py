"""Simulator-independent tests for final direct-I1 materialization helpers."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from materialize_direct_i1_cards import (
    CARD_CONTRACT,
    DIRECT_CONTRACT,
    REGION_RULE,
    derive_frozen_local_region,
    empirical_higher_quantile,
)


def main() -> None:
    rule = json.loads(Path(REGION_RULE).read_text(encoding="utf-8"))
    direct = json.loads(Path(DIRECT_CONTRACT).read_text(encoding="utf-8"))
    card = json.loads(Path(CARD_CONTRACT).read_text(encoding="utf-8"))

    assert rule["status"] == "FROZEN_PHASE2_I1_LOCAL_REGION_RULE_V1"
    assert rule["A_G_is_input"] is False
    assert rule["global_budget_split_allowed"] is False
    assert rule["M0_result_used"] is False
    assert rule["M1_result_used"] is False
    assert rule["local_sigma_gate_used_for_selection"] is False
    assert direct["finalization"]["A_i_rule_frozen"] is True
    assert direct["finalization"]["final_cards_hash_frozen"] is False
    assert card["A_i_selection"]["owner"] == "Phase2 information construction"
    assert card["A_i_selection"]["A_G_is_input"] is False

    ledger = pd.DataFrame(
        {
            "trajectory": [0] * 10,
            "request_id": list(range(10)),
            "emission": [float(x) for x in range(10)],
            "completion": [float(x) + 0.1 for x in range(10)],
            "L": [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0],
            "C": [1,2,3,4,5,6,7,8,9,10],
            "Q": [0.5] * 10,
        }
    )
    assert empirical_higher_quantile(ledger["L"], 0.99) == 1.0
    assert empirical_higher_quantile(ledger["C"], 0.99) == 10.0

    region = derive_frozen_local_region("ProviderX", ledger, rule)
    assert region == {
        "region_id": "ProviderX_DIRECT_P99_L_P99_C_MINQ_V1",
        "l_max": 1.0,
        "c_max": 10.0,
        "q_min": 0.5,
    }
    assert "A_G" not in region
    assert "rho" not in region

    assert card["R"]["values"] == [0.95, 0.975, 0.9833333333333333, 0.99, 1.0]
    assert len(card["H"]["values"]) == 49
    assert card["H"]["values"][0] == 0.0
    assert card["H"]["values"][-1] == 240.0

    print("PHASE2_DIRECT_I1_MATERIALIZATION_TESTS_PASS")
    print("P99_LOCAL_REGION_RULE_PASS")
    print("DIRECT_I1_CARD_SUPPORT_PASS")


if __name__ == "__main__":
    main()
