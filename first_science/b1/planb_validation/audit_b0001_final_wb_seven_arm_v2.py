#!/usr/bin/env python3
"""B0001 post-white-box mechanical audit with the seven-arm firewall rechecked.

This is a read-only verification of frozen sources. It creates ONLY a new audit
JSON under --out, never modifies reference ledgers, curves, prediction files,
authorization, or policy code. It imports no simulator and runs no trajectories.

The pre-existing B0001 final-reference mechanical audit independently checks
the 12 reference-cell manifests, trajectory identities/seeds, query/horizon
grids, empirical success/count relationships and Wilson intervals. This v2
gate additionally re-verifies the seven-arm blind prediction evidence *after*
reference generation, its original authorization, and the externally retained
SHA-256 of the global reference freeze.

This is a mechanical/provenance audit, NOT an independent scientific rescore of
the raw physical ledger and NOT a comparison of algorithms' prediction error.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import audit_b0001_final_wb_v1 as reference_audit
import b0001_seven_arm_blind_reference_guard_v1 as seven_guard
import preflight_b0001_final_wb_v1 as gate


STATUS = "B0001_FINAL_WB_SEVEN_ARM_POSTRUN_MECHANICAL_AUDIT_V2_PASS"

# Obtained from the global-freeze JSON supplied independently on 2026-11-19.
# The runner wrote canonical sorted/indented JSON; this pins its exact bytes.
EXPECTED_REFERENCE_GLOBAL_FREEZE_SHA256 = (
    "37a0bb58a31593ed62e72b88e3f693ee5e20d2e421d6e3d9e7a601627f8101ff"
)


def require_separate_output(a: argparse.Namespace) -> None:
    """Refuse every output/input overlap, including parent-child overlaps."""
    for name in (
        "authorization", "reference", "graph", "staging", "audit",
        "seven_arm", "four_arm",
    ):
        source = getattr(a, name)
        gate.require(
            a.out != source and a.out not in source.parents
            and source not in a.out.parents,
            "Postrun audit output overlaps frozen input: " + name,
        )


def verify(a: argparse.Namespace) -> dict:
    auth_path = a.authorization / "b0001_final_wb_authorization_freeze.json"
    auth = gate.load(auth_path)
    gate.require(
        auth.get("status") == gate.STATUS
        and auth.get("reference_execution_authorized") is True
        and auth.get("analysis_authorized") is False
        and auth.get("final_WB_outcomes_read") is False
        and auth.get("all_seven_algorithms_blind_before_reference") is True,
        "Original seven-arm reference-only authorization invalid",
    )

    global_path = a.reference / "b0001_final_wb_global_freeze.json"
    global_sha = gate.sha(global_path)
    gate.require(
        global_sha == EXPECTED_REFERENCE_GLOBAL_FREEZE_SHA256,
        "Final reference global freeze differs from separately archived copy",
    )
    global_doc = gate.load(global_path)
    gate.require(
        global_doc.get("evaluation_unlocked") is False
        and global_doc.get("prediction_files_modified") is False
        and global_doc.get("seven_method_plan_b_complete") is False
        and global_doc.get("reference_method_source_sha256") ==
        auth.get("original_reference_runner_sha256"),
        "Final reference frozen status/source contract altered",
    )

    # Rehash the original scientific simulator SOURCE, without importing it.
    phase5_runner = (
        Path(__file__).resolve().parents[2] / "phase5" /
        "run_phase5_final_wb_v3b_fullsupport.py"
    )
    gate.require(
        gate.sha(phase5_runner) ==
        global_doc["reference_method_source_sha256"],
        "Original white-box generation method changed",
    )

    # Read only bytes for a SHA-256 digest; do not parse hidden-world fields.
    for role in gate.ROLES:
        world = auth["selected_worlds"][role]
        gate.require(
            world["candidate_id"] == gate.WORLD_IDS[role]
            and gate.sha(Path(world["source_world_contract"])) ==
            world["world_contract_sha256"],
            "Selected physical-world contract drift: " + role,
        )

    # Verify *every* original-three-arm and supplementary-four-arm blind file
    # against its pre-white-box freeze. deep=False performs complete file-hash
    # reconciliation without rescoring the 48 previously audited method cells.
    seven_evidence = seven_guard.verify(
        original_audit=a.audit,
        graph=a.graph,
        four_arm=a.four_arm,
        seven_arm=a.seven_arm,
        wb_seed_start=gate.WB_START,
        wb_seed_n=gate.WB_N,
        deep=False,
    )
    gate.require(
        seven_evidence == auth["seven_arm_blind_evidence"],
        "Seven-arm blind freeze is not identical to pre-WB authorization",
    )
    print("B0001_SEVEN_ARM_POSTRUN_BLIND_HASH_GUARD_PASS", flush=True)

    # The original reference-mechanical auditor reads no predictor values and
    # recomputes Wilson intervals; we invoke its verify() without its writer.
    mechanical = reference_audit.verify(a)
    gate.require(
        mechanical["n_reference_cells"] == 12
        and mechanical["n_reference_trajectories"] == 12000
        and mechanical["n_reference_curve_points"] == 8820
        and mechanical["all_reference_Wilson95_intervals_checked"] is True
        and mechanical["evaluation_authorized"] is True,
        "Reference mechanical audit did not pass all expected conditions",
    )

    # Preserve the original mechanical checklist and add audited cross-freeze
    # bindings. Do not copy white-box values or any prediction values here.
    return {
        **mechanical,
        "status": STATUS,
        "reference_mechanical_audit_status": reference_audit.STATUS,
        "reference_global_freeze_sha256": global_sha,
        "seven_arm_postrun_evidence": seven_evidence,
        "seven_arm_postrun_equals_pre_WB_authorization": True,
        "seven_blind_algorithms_unchanged": 7,
        "method_condition_predictions_unchanged": 84,
        "original_reference_method_source_rechecked": True,
        "selected_hidden_world_contract_hashes_rechecked": True,
        "generation_or_prediction_replay_performed": False,
        "mechanical_audit_only": True,
        "evaluation_authorized": True,
        "seven_method_plan_b_complete": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "authorization", "reference", "graph", "staging", "audit",
        "seven-arm", "four-arm", "out",
    ):
        parser.add_argument("--" + name, required=True, type=Path)
    a = parser.parse_args()
    for name in (
        "authorization", "reference", "graph", "staging", "audit",
        "seven_arm", "four_arm", "out",
    ):
        setattr(a, name, getattr(a, name).expanduser().resolve())
    require_separate_output(a)
    result = verify(a)
    output = a.out / "b0001_final_reference_seven_arm_postrun_audit_v2.json"
    gate.save(output, result)  # Refuses to overwrite an existing audit file.
    print("B0001_SEVEN_ARM_FINAL_REFERENCE_MECHANICAL_AUDIT_V2_PASS", flush=True)
    print("EVALUATION_UNLOCKED_AFTER_SEVEN_ARM_REFERENCE_AUDIT", flush=True)
    print("NO_SIMULATIONS / NO_PREDICTOR_CHANGES / NO_REFERENCE_CHANGES", flush=True)
    print("AUDIT", output, flush=True)


if __name__ == "__main__":
    main()
