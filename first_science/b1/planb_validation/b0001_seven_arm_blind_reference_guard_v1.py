#!/usr/bin/env python3
"""Pure read-only guard binding all seven B0001 predictors before/while WB runs.

No simulator is imported and no reference data is accessed. The deep gate
re-audits the 48 supplementary cells; the fast per-reference-cell guard
rechecks their frozen source/data hashes, plus the original three-arm outputs.
"""

from __future__ import annotations

from pathlib import Path

from audit_b0001_four_arm_postrun_readonly_v1 import (
    GLOBAL_STATUS, audit_method, check, expected_rows, read, sha,
)
from preflight_b0001_seven_arm_blind_freeze_v1 import (
    CONDITIONS, ORIGINAL_GLOBAL_STATUS, ORIGINAL_STATUS, POLICY_FILES, STATUS,
)

OLD_FILES = {
    "m0_predictions": "m0_predictions.csv",
    "m1_predictions": "m1_predictions.csv",
    "m2_member_curves": "m2_member_curves.csv",
    "m2_predictions": "m2_predictions.csv",
    "m3_fullsupport_allocation": "m3_fullsupport_allocation.csv",
    "m3_member_curves": "m3_member_curves.csv",
    "m3_predictions_full343_and_nested": "m3_predictions_full343_and_nested.csv",
    "prediction_ledger_hashes": "prediction_ledger_hashes.csv",
}
FOUR = {"FIXED_CV_TOP1", "FIXED_CV_TOP14", "ORIGINAL_TOP14_B1400", "ORIGINAL_TOP1_B1400"}
NINE = ["Random", "Balanced", "Informed", "Top2 joint", "KG joint",
        "Top2 uniform", "Top2 adaptive", "KG uniform", "KG adaptive"]


def verify(*, original_audit: Path, graph: Path, four_arm: Path,
           seven_arm: Path, wb_seed_start: int, wb_seed_n: int, deep: bool) -> dict:
    dirs = (original_audit, graph, four_arm, seven_arm)
    check(all(d.is_dir() for d in dirs), "missing original/four-arm/seven-arm audit directory")

    frozen_path = seven_arm / "b0001_seven_arm_pre_wb_blind_freeze.json"
    freeze = read(frozen_path)
    check(freeze.get("status") == STATUS and
          freeze.get("n_methods") == 7 and
          freeze.get("n_conditions") == 12 and
          freeze.get("n_method_condition_pairs") == 84 and
          freeze.get("n_additional_method_cells_independently_audited") == 48 and
          freeze.get("n_additional_graph_trajectories_independently_audited") == 67200 and
          freeze.get("original_method_ids") == ["M1", "M2", "M3_FULL343"] and
          set(freeze.get("supplementary_method_ids", [])) == FOUR and
          freeze.get("nine_selection_policies") == NINE and
          freeze.get("evaluation_budgets") == [10, 15, 20, 30, 40] and
          freeze.get("final_whitebox_reference_read") is False and
          freeze.get("reference_execution_authorized") is False and
          freeze.get("policy_replay_forbidden_until_independent_reference_mechanical_audit") is True,
          "seven-arm frozen contract/embargo changed")
    check(set(freeze.get("reference_cell_ids", [])) == CONDITIONS,
          "seven-arm conditions changed")

    old_path = original_audit / "b0001_full343_postrun_integrity_audit.json"
    old = read(old_path)
    check(old.get("status") == ORIGINAL_STATUS and
          old.get("audited_cell_count") == 12 and
          old.get("ledger_files_verified") == 4452 and
          old.get("trajectories_verified") == 50400 and
          old.get("final_whitebox_read") is False and
          old.get("final_whitebox_authorized") is False and
          sha(old_path) == freeze["original_three_arm_integrity_audit_sha256"],
          "original-three-arm independent audit drift")
    old_global_path = graph / "scientific" / "b0001_full343_global_prediction_freeze.json"
    og = read(old_global_path)
    check(og.get("status") == ORIGINAL_GLOBAL_STATUS and
          og.get("n_frozen_cells") == 12 and og.get("final_WB_read") is False and
          sha(old_global_path) == old["global_prediction_freeze_sha256"] ==
          freeze["original_three_arm_global_freeze_sha256"],
          "original-three global freeze drift")
    old_manifests = og["prediction_manifest_sha256_by_cell"]
    check(set(old_manifests) == CONDITIONS and
          old_manifests == freeze["original_three_arm_prediction_manifests_sha256"],
          "original-three per-cell hashes drift")
    for cell, digest in old_manifests.items():
        root = graph / "scientific" / cell
        mf = read(root / "prediction_manifest.json")
        check(sha(root / "prediction_manifest.json") == digest,
              "original-three manifest changed: " + cell)
        check(set(mf.get("output_hashes_sha256", {})) == set(OLD_FILES),
              "original-three output inventory changed: " + cell)
        for key, name in OLD_FILES.items():
            check(sha(root / name) == mf["output_hashes_sha256"][key],
                  "original-three prediction output changed: " + cell + "/" + name)

    plan_path = four_arm / "b0001_four_arm_science_execution_plan.json"
    rows = expected_rows(read(plan_path))
    four_global_path = four_arm / "scientific" / "b0001_four_arm_global_prediction_freeze.json"
    fg = read(four_global_path)
    check(sha(plan_path) == fg.get("execution_plan_sha256") ==
          freeze["supplementary_four_arm_execution_plan_sha256"],
          "four-arm plan SHA drift")
    check(fg.get("status") == GLOBAL_STATUS and
          fg.get("n_method_cells") == 48 and
          fg.get("graph_trajectories") == 67200 and
          fg.get("whitebox_reference_read") is False and
          sha(four_global_path) == freeze["supplementary_four_arm_global_freeze_sha256"],
          "four-arm global freeze drift")
    new_manifests = fg["method_cell_manifest_sha256"]
    check(set(new_manifests) == set(rows) and
          new_manifests == freeze["supplementary_four_arm_prediction_manifests_sha256"],
          "four-arm 48-cell manifest inventory changed")
    lo, hi = int(wb_seed_start), int(wb_seed_start) + int(wb_seed_n) - 1
    check(0 < lo <= hi < 2**32, "invalid reference seed range")
    for key, row in rows.items():
        root = four_arm / "scientific" / row["method"] / row["cell"]
        mf_path = root / "prediction_manifest.json"
        check(sha(mf_path) == new_manifests[key], "four-arm manifest hash drift: " + key)
        mf = read(mf_path)
        for field, name in (("member_curves_sha256", "member_curves.csv"),
                            ("predictions_sha256", "predictions.csv")):
            check(sha(root / name) == mf[field], "four-arm output drift: " + key + "/" + name)
        for variant in row["variants"]:
            start, end = int(variant["seed_start"]), int(variant["seed_end"])
            check(hi < start or lo > end, "reference seed collision with four-arm: " + key)
        if deep:
            audit_method(four_arm, row)

    here = Path(__file__).resolve().parent
    for name in POLICY_FILES:
        check(sha(here / name) == freeze["policy_source_sha256"][name],
              "nine-policy source changed after blind freeze: " + name)
    return {
        "seven_arm_blind_freeze_sha256": sha(frozen_path),
        "supplementary_four_arm_global_freeze_sha256": sha(four_global_path),
        "supplementary_four_arm_execution_plan_sha256": sha(plan_path),
        "original_three_arm_integrity_audit_sha256": sha(old_path),
        "blind_reference_guard_source_sha256": sha(Path(__file__)),
        "n_algorithms_locked": 7,
        "n_method_condition_values_locked": 84,
        "n_conditions": 12,
    }
