"""Structural guards for the rho-conditioned Phase-2 I1 materialization."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    contract = json.loads(
        (HERE / "config_phase2_i1_provider_card_v3_rho_conditioned.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["status"] == "PHASE2_I1_RHO_CONDITIONED_CONTRACT_V1"
    region_rho = tuple(float(x) for x in contract["region_rho"]["values"])
    query_rho = tuple(float(x) for x in contract["query_rho"]["values"])
    assert region_rho == (0.95, 0.975, 0.9833333333333333, 0.99, 0.995)
    assert query_rho == region_rho
    assert 1.0 not in region_rho
    assert contract["region_rho"]["nested_regions_required"] is True
    assert contract["joint_model"]["family"] == "GaussianMixture"
    assert contract["joint_model"]["coordinates"] == ["log_L", "log_C"]
    assert contract["joint_model"]["component_selection"] == "minimum_BIC"
    assert contract["joint_model"]["fit_uses_phase1_whitebox"] is False

    source = (HERE / "materialize_rho_conditioned_i1_cards.py").read_text(
        encoding="utf-8"
    )
    assert "derive_nested_rho_regions" in source
    assert "rho_conditioned_regions" in source
    assert "region_rho" in source
    assert "i1_cards_v2_rho_conditioned" in source
    assert "derive_local_regions_from_traces" not in source
    assert "H_star" not in source
    assert "sigma_target" not in source
    assert "rho_anchor" not in source
    assert "local_regions=regions" in source
    assert "same_materialized_I1_for_M0_and_M1" in source

    print("PHASE2_RHO_CONDITIONED_I1_CONTRACT_TESTS_PASS")
    print("OLD_H120_SINGLE_A_I_CALIBRATION_BLOCKED_PASS")
    print("RHO_REGION_SUPPORT_FINITE_GMM_PASS")
    print("MULTI_A_I_PUBLIC_CARD_MATERIALIZATION_PASS")
    print("SAME_CORRECTED_I1_FOR_M0_M1_CONTRACT_PASS")


if __name__ == "__main__":
    main()
