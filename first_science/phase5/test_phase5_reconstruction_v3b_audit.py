from __future__ import annotations

import audit_phase5_reconstruction_v3b_selection as audit
from phase5_runtime_v2 import read_json


def test_v3b_audit_contract_target():
    cfg=read_json(audit.CFG)
    assert cfg["status"]==audit.EXPECTED_CFG
    assert cfg["selection_basis"]["ranking_metric"]=="rescore_rmse"
    assert cfg["selection_basis"]["replay_may_select_or_reorder"] is False
    assert cfg["selection_basis"]["behavioral_centroid_may_select_or_reorder"] is False


def test_v3b_audit_expected_cardinalities():
    cfg=read_json(audit.CFG)
    assert cfg["methods"]["M1"]["joint_models_per_world"]==1
    assert cfg["methods"]["M2"]["joint_models_per_world"]==27
    assert cfg["methods"]["M3"]["joint_support_size"]==343
    assert cfg["methods"]["M3"]["nested_readouts"]==["Top1","Top3","Top14"]
