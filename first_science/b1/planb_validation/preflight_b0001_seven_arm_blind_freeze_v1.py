#!/usr/bin/env python3
"""Bind seven B0001 predictor variants before final-WB/reference access.

The original three predictors and four additional Top1/Top14 predictors must
all have frozen blind graph predictions on the same 12 physical cells. This
script independently verifies all 48 new cells, binds the original three-arm
post-run audit, and records the nine-policy comparison sources. It NEVER
imports a simulator or accesses WB data. A successful preflight is NOT
authorization to open the white-box reference; a separate reference gate is
required and must consume this freeze.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_b0001_four_arm_postrun_readonly_v1 import (
    GLOBAL_STATUS, audit_method, check, expected_rows, read, sha,
)


STATUS = "B0001_SEVEN_ARM_84_BLIND_PREDICTION_FINGERPRINTS_FROZEN_WB_BLOCKED"
ORIGINAL_STATUS = "B0001_FULL343_POSTRUN_INTEGRITY_AUDIT_PASS_FINAL_WB_EMBARGOED"
ORIGINAL_GLOBAL_STATUS = "B0001_FULL343_12_CELL_GRAPH_PREDICTIONS_FROZEN"
CONDITIONS = {f"{world}__{graph}" for world in ("P1", "P3", "P4")
              for graph in ("G_PAR", "G_PARSEQ", "G_SEQ", "G_SEQPAR")}
POLICY_FILES = (
    "B1_EXECUTABLE_POLICY_FREEZE_V1.md",
    "B1_KG_ONE_STEP_SPECIFICATION_V1.md",
    "b1_budget_comparison_v1.py",
    "b1_kg_one_step_v1.py",
    "b1_condition_selection_controlled_v1.py",
)


def audit(original_audit: Path, graph: Path, four_arm: Path) -> dict:
    old_path = original_audit / "b0001_full343_postrun_integrity_audit.json"
    old = read(old_path)
    check(old.get("status") == ORIGINAL_STATUS and
          old.get("audited_cell_count") == 12 and
          old.get("ledger_files_verified") == 4452 and
          old.get("trajectories_verified") == 50400 and
          old.get("final_whitebox_read") is False and
          old.get("final_whitebox_authorized") is False,
          "original-three prediction audit status/coverage")
    old_global_path = graph / "scientific" / "b0001_full343_global_prediction_freeze.json"
    og = read(old_global_path)
    check(sha(old_global_path) == old.get("global_prediction_freeze_sha256"),
          "original global freeze changed since audit")
    check(og.get("status") == ORIGINAL_GLOBAL_STATUS and
          og.get("n_frozen_cells") == 12 and og.get("final_WB_read") is False,
          "original global freeze status")
    old_manifests = og.get("prediction_manifest_sha256_by_cell", {})
    check(set(old_manifests) == CONDITIONS, "original 12-cell inventory")
    for cell, fingerprint in old_manifests.items():
        check(sha(graph / "scientific" / cell / "prediction_manifest.json") == fingerprint,
              "original prediction manifest changed: " + cell)

    new_plan_path = four_arm / "b0001_four_arm_science_execution_plan.json"
    plan = read(new_plan_path)
    rows = expected_rows(plan)
    new_global_path = (four_arm / "scientific" /
                       "b0001_four_arm_global_prediction_freeze.json")
    ng = read(new_global_path)
    check(ng.get("status") == GLOBAL_STATUS and
          ng.get("n_method_cells") == 48 and ng.get("graph_trajectories") == 67200 and
          ng.get("whitebox_reference_read") is False and
          ng.get("seven_arm_independent_confirmation_complete") is False,
          "four-arm global completion/status")
    check(ng.get("execution_plan_sha256") == sha(new_plan_path),
          "four-arm global plan SHA")
    new_manifests = ng.get("method_cell_manifest_sha256", {})
    check(set(new_manifests) == set(rows), "four-arm complete 48-cell inventory")
    for key, row in rows.items():
        manifest = four_arm / "scientific" / row["method"] / row["cell"] / "prediction_manifest.json"
        check(sha(manifest) == new_manifests[key], "four-arm global SHA: " + key)
        audit_method(four_arm, row)
    check({key.split("/", 1)[1] for key in rows} == CONDITIONS,
          "new four-arm condition set differs from original")

    here = Path(__file__).resolve().parent
    policy_fingerprints = {name: sha(here / name) for name in POLICY_FILES}
    return {
        "status": STATUS,
        "purpose": "Blind pre-reference seven-algorithm matrix and nine-policy replay source lock",
        "original_method_ids": ["M1", "M2", "M3_FULL343"],
        "supplementary_method_ids": sorted({row["method"] for row in rows.values()}),
        "n_methods": 7,
        "n_conditions": 12,
        "n_method_condition_pairs": 84,
        "n_additional_method_cells_independently_audited": 48,
        "n_additional_graph_trajectories_independently_audited": 67200,
        "reference_cell_ids": sorted(CONDITIONS),
        "original_three_arm_integrity_audit_sha256": sha(old_path),
        "original_three_arm_global_freeze_sha256": sha(old_global_path),
        "original_three_arm_prediction_manifests_sha256": old_manifests,
        "supplementary_four_arm_execution_plan_sha256": sha(new_plan_path),
        "supplementary_four_arm_global_freeze_sha256": sha(new_global_path),
        "supplementary_four_arm_prediction_manifests_sha256": new_manifests,
        "policy_source_sha256": policy_fingerprints,
        "nine_selection_policies": ["Random", "Balanced", "Informed", "Top2 joint",
                                    "KG joint", "Top2 uniform", "Top2 adaptive",
                                    "KG uniform", "KG adaptive"],
        "evaluation_budgets": [10, 15, 20, 30, 40],
        "primary_outcome": "terminal simple regret of selected algorithm based on equal-weight condition-average MAE",
        "secondary_outcome": "reference-best algorithm selection rate",
        "policy_replay_forbidden_until_independent_reference_mechanical_audit": True,
        "final_whitebox_reference_read": False,
        "reference_execution_authorized": False,
        "new_simulations_run": 0,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-audit", required=True, type=Path)
    p.add_argument("--graph", required=True, type=Path)
    p.add_argument("--four-arm", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--check", action="store_true", help="Verify without writing any file")
    a = p.parse_args()
    for name in ("original_audit", "graph", "four_arm", "out"):
        setattr(a, name, getattr(a, name).expanduser().resolve())
    check(all(a.out != d and a.out not in d.parents and d not in a.out.parents
              for d in (a.original_audit, a.graph, a.four_arm)),
          "attestation directory overlaps frozen inputs")
    result = audit(a.original_audit, a.graph, a.four_arm)
    print("B0001_SEVEN_ARM_PRE_WB_INDEPENDENT_AUDIT_PASS 84 cells 7 methods", flush=True)
    print("ORIGINAL_36_PLUS_NEW_48 / NO_WHITEBOX_READ / NO_SIMULATIONS", flush=True)
    if a.check:
        print("NO_WRITES / REFERENCE_STILL_BLOCKED", flush=True)
        return
    path = a.out / "b0001_seven_arm_pre_wb_blind_freeze.json"
    check(not path.exists(), "refusing to overwrite existing blind freeze")
    check(not a.out.exists(), "freeze output directory must be new: " + str(a.out))
    a.out.mkdir(parents=True, exist_ok=False)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("B0001_SEVEN_ARM_BLIND_FREEZE_CREATED", path, flush=True)
    print("REFERENCE_EXECUTION_NOT_AUTHORIZED", flush=True)


if __name__ == "__main__":
    main()
