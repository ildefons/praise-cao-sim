from __future__ import annotations

from phase5_runtime_v2 import read_json
import freeze_phase5_reconstruction_v3b_selection as freeze


def test_v3b_contract_is_best_by_common_rescore_rmse():
    cfg=read_json(freeze.CFG)
    assert cfg["status"]==freeze.EXPECTED_CFG
    basis=cfg["selection_basis"]
    assert basis["ranking_metric"]=="rescore_rmse"
    assert basis["replay_may_select_or_reorder"] is False
    assert basis["behavioral_centroid_may_select_or_reorder"] is False
    assert basis["hard_rmse_compatibility_gate"] is False


def test_v3b_method_nesting_and_cardinalities():
    cfg=read_json(freeze.CFG)
    methods=cfg["methods"]
    assert methods["M1"]["members_per_provider"]==1
    assert methods["M2"]["members_per_provider"]==3
    assert methods["M2"]["joint_models_per_world"]==27
    assert methods["M3"]["joint_support_size"]==343
    assert methods["M3"]["nested_readouts"]==["Top1","Top3","Top14"]


def test_v3b_is_selection_only():
    cfg=read_json(freeze.CFG)
    p=cfg["provenance"]
    assert p["no_new_provider_simulation"] is True
    assert p["v3_outputs_are_not_overwritten"] is True
