from __future__ import annotations

import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CFG=HERE/"config_phase5_evaluation_v3b_fullsupport.json"


def test_primary_methods_and_window_are_frozen():
    c=json.loads(CFG.read_text())
    assert c["status"]=="FROZEN_PHASE5_V3B_FULLSUPPORT_EVALUATION_CONTRACT"
    assert c["primary_methods"]==["M0","M1","M2","M3_FULL343"]
    assert c["primary_window"]["H_min_seconds"]==60
    assert c["primary_window"]["H_max_seconds"]==240
    assert c["primary_window"]["horizon_count_per_query"]==37


def test_registered_p2_topology_contrast_is_not_silently_replaced():
    c=json.loads(CFG.read_text())
    t=c["topology_sensitivity"]
    assert t["registered_Delta_het_status"]=="NOT_ESTIMABLE_UNDER_PROSPECTIVE_STEP0_GATE"
    assert t["no_P4_only_substitution"] is True


def test_adapter_frozen_before_performance_readout():
    c=json.loads(CFG.read_text())
    p=c["provenance"]
    assert p["prediction_curves_read_before_freeze"] is False
    assert p["method_performance_computed_before_freeze"] is False
    assert c["M3"]["primary"]=="M3_FULL343"
    assert c["M3"]["full_support_truncation_bound"]==0.0
