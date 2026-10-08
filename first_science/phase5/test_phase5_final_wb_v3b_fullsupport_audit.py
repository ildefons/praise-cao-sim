from pathlib import Path
import audit_phase5_final_wb_v3b_fullsupport as audit

HERE = Path(__file__).resolve().parent


def test_audit_targets_final_wb_namespace():
    assert audit.ROOT == HERE / "results" / "05_final_wb_v3b_fullsupport"


def test_audit_expected_frozen_statuses():
    assert audit.EXPECTED_BATTERY == "FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_BATTERY"
    assert audit.EXPECTED_CELL == "FROZEN_PHASE5_V3B_FULLSUPPORT_FINAL_WB_CELL"
    assert audit.EXPECTED_GLOBAL == "FROZEN_PHASE5_V3B_FULLSUPPORT_GLOBAL_PREDICTION_FREEZE"


def test_audit_is_pre_performance_analysis():
    source = Path(audit.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "m0_predictions.csv",
        "m1_predictions.csv",
        "m2_predictions.csv",
        "m3_predictions_full343_and_nested.csv",
    ):
        assert forbidden not in source
