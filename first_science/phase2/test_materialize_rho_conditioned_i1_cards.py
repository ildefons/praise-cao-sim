"""Structural guards for the rho-conditioned Phase-2 I1 materialization."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from materialize_rho_conditioned_i1_cards import assert_disjoint_evidence_sources

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
    assert contract["joint_model"]["fit_uses_sigma_estimation_corpus"] is False
    assert contract["sigma_semantics"]["estimation_corpus"] == "independent T_i^sigma only"
    assert contract["sigma_semantics"][
        "region_construction_corpus_forbidden_for_sigma_estimation"
    ] is True
    assert contract["evidence_partition"][
        "trajectory_seed_banks_must_be_disjoint"
    ] is True
    assert contract["evidence_partition"]["same_public_I1_for_M0_and_M1"] is True

    region_acquisition = json.loads(
        (HERE / "config_phase2_i1_acquisition_v1.json").read_text(encoding="utf-8")
    )
    sigma_acquisition = json.loads(
        (HERE / "config_phase2_i1_sigma_acquisition_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert sigma_acquisition["corpus_role"] == "sigma_estimation_only"
    assert sigma_acquisition["acquisition"]["seed_start"] == 6100
    assert sigma_acquisition["acquisition"]["seed_end_inclusive"] == 6199
    assert sigma_acquisition["acquisition"]["forbidden_seed_max_inclusive"] == 6099

    sigma_manifest = {
        "seed_bank": list(range(6100, 6200)),
    }
    assert_disjoint_evidence_sources(
        region_acquisition, sigma_manifest, sigma_acquisition
    )

    overlapping_contract = copy.deepcopy(sigma_acquisition)
    overlapping_contract["acquisition"]["seed_start"] = 6099
    overlapping_contract["acquisition"]["seed_end_inclusive"] = 6198
    overlapping_manifest = {"seed_bank": list(range(6099, 6199))}
    try:
        assert_disjoint_evidence_sources(
            region_acquisition, overlapping_manifest, overlapping_contract
        )
    except RuntimeError as error:
        assert "overlap" in str(error)
    else:
        raise AssertionError("overlapping T_i^Gamma/T_i^sigma seed banks were accepted")

    source = (HERE / "materialize_rho_conditioned_i1_cards.py").read_text(
        encoding="utf-8"
    )
    assert "derive_nested_rho_regions" in source
    assert "region_ledgers[provider]" in source
    assert "private_provider_ledgers=sigma_ledgers[provider]" in source
    assert "assert_disjoint_evidence_sources" in source
    assert "_assert_distinct_corpus_hashes" in source
    assert "sigma_acquisition_manifest" in source
    assert "region_and_sigma_evidence_are_trajectory_disjoint" in source
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
    print("TRAJECTORY_DISJOINT_REGION_SIGMA_CONTRACT_PASS")
    print("REGION_CORPUS_FOR_SIGMA_ESTIMATION_BLOCKED_PASS")
    print("SAME_CORRECTED_I1_FOR_M0_M1_CONTRACT_PASS")


if __name__ == "__main__":
    main()
