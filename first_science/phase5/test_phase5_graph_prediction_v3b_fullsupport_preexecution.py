from __future__ import annotations

import json
from pathlib import Path

import freeze_phase5_graph_prediction_v3b_fullsupport_preexecution as prep

HERE=Path(__file__).resolve().parent


def test_fullsupport_preexecution_namespace_and_support():
    cfg=json.loads((HERE/"config_phase5_graph_prediction_v3b_fullsupport.json").read_text())
    assert prep.DEFAULT_ROOT==HERE/"results"/"04_prediction_v3b_fullsupport"
    assert prep.SUPPORT_SIZE==343
    assert prep.BUDGET==1400
    assert cfg["methods"]["M3"]["primary_method_id"]=="M3_FULL343"


def test_fullsupport_preexecution_requires_new_smoke():
    assert prep.SMOKE.name=="phase5_v3b_fullsupport_graph_adapter_smoke_manifest.json"
    cfg=json.loads((HERE/"config_phase5_graph_prediction_v3b_fullsupport.json").read_text())
    assert cfg["execution_gate"].startswith("A new full-support graph-adapter smoke")


def test_fullsupport_preexecution_does_not_read_final_wb_namespace():
    source=Path(prep.__file__).read_text(encoding="utf-8")
    assert '"05_final_wb"' not in source
    assert "'05_final_wb'" not in source
    seeds=json.loads((HERE/"config_phase5_seed_registry_v3b_fullsupport.json").read_text())
    assert seeds["final_whitebox"]["start"]==54000
    assert seeds["final_whitebox"]["end_inclusive"]==54999
