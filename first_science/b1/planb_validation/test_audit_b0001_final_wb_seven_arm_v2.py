#!/usr/bin/env python3
"""Isolated gate-contract tests; no private files, reference data or simulator.

Run with: python -m unittest -v test_audit_b0001_final_wb_seven_arm_v2.py
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock


def load_under_stubs():
    gate = types.ModuleType("preflight_b0001_final_wb_v1")
    gate.STATUS = "PREFLIGHT_ONLY"
    gate.ROLES = ("P1", "P3", "P4")
    gate.WORLD_IDS = {
        "P1": "B0001_P1_A02", "P3": "B0001_P3_A01", "P4": "B0001_P4_A01",
    }
    gate.WB_START = 42_000_000
    gate.WB_N = 1000

    def require(condition, reason):
        if not condition:
            raise RuntimeError(reason)

    gate.require = require
    gate.save = Mock()
    guard = types.ModuleType("b0001_seven_arm_blind_reference_guard_v1")
    guard.verify = Mock(return_value={"n_algorithms_locked": 7})
    audit = types.ModuleType("audit_b0001_final_wb_v1")
    audit.STATUS = "REFERENCE_MECHANICAL_PASS"
    audit.verify = Mock(return_value={
        "n_reference_cells": 12,
        "n_reference_trajectories": 12000,
        "n_reference_curve_points": 8820,
        "all_reference_Wilson95_intervals_checked": True,
        "evaluation_authorized": True,
    })

    auth = {
        "status": gate.STATUS,
        "reference_execution_authorized": True,
        "analysis_authorized": False,
        "final_WB_outcomes_read": False,
        "all_seven_algorithms_blind_before_reference": True,
        "original_reference_runner_sha256": "runner-hash",
        "seven_arm_blind_evidence": {"n_algorithms_locked": 7},
        "selected_worlds": {
            role: {
                "candidate_id": candidate,
                "source_world_contract": f"/private/{role}.json",
                "world_contract_sha256": "world-hash",
            }
            for role, candidate in gate.WORLD_IDS.items()
        },
    }
    global_doc = {
        "evaluation_unlocked": False,
        "prediction_files_modified": False,
        "seven_method_plan_b_complete": False,
        "reference_method_source_sha256": "runner-hash",
    }

    def load(path):
        if path.name == "b0001_final_wb_authorization_freeze.json":
            return auth
        if path.name == "b0001_final_wb_global_freeze.json":
            return global_doc
        raise AssertionError(f"unexpected read: {path}")

    gate.load = load

    # Import without touching the actual repository's preflight/audit modules.
    old = {name: sys.modules.get(name) for name in (
        gate.__name__, guard.__name__, audit.__name__,
    )}
    sys.modules.update({
        gate.__name__: gate, guard.__name__: guard, audit.__name__: audit,
    })
    try:
        script = Path(__file__).with_name("audit_b0001_final_wb_seven_arm_v2.py")
        spec = importlib.util.spec_from_file_location("b0001_v2_under_test", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, prior in old.items():
            if prior is None:
                del sys.modules[name]
            else:
                sys.modules[name] = prior

    def sha(path):
        if path.name == "b0001_final_wb_global_freeze.json":
            return module.EXPECTED_REFERENCE_GLOBAL_FREEZE_SHA256
        if path.name == "run_phase5_final_wb_v3b_fullsupport.py":
            return "runner-hash"
        if path.name.endswith(".json"):
            return "world-hash"
        raise AssertionError(f"unexpected hash: {path}")

    gate.sha = Mock(side_effect=sha)
    return module, gate, guard, audit, auth, global_doc


def arguments():
    base = Path("/work/b0001").resolve()
    return argparse.Namespace(**{
        "authorization": base / "authorization",
        "reference": base / "final_reference",
        "graph": base / "frozen_graph",
        "staging": base / "staging",
        "audit": base / "old_postrun_audit",
        "seven_arm": base / "seven_arm",
        "four_arm": base / "four_arm",
        "out": base / "new_audit_v2",
    })


class AuditGateContractTests(unittest.TestCase):
    def setUp(self):
        self.module, self.gate, self.guard, self.audit, self.auth, self.freeze = load_under_stubs()
        self.args = arguments()

    def test_valid_freezes_are_checked_and_never_written_during_verify(self):
        self.module.require_separate_output(self.args)
        result = self.module.verify(self.args)
        self.assertEqual(result["status"], self.module.STATUS)
        self.assertTrue(result["seven_arm_postrun_equals_pre_WB_authorization"])
        self.assertTrue(result["evaluation_authorized"])
        self.assertFalse(result["seven_method_plan_b_complete"])
        self.guard.verify.assert_called_once()
        self.assertFalse(self.guard.verify.call_args.kwargs["deep"])
        self.audit.verify.assert_called_once()
        self.gate.save.assert_not_called()

    def test_modified_predictor_evidence_blocks_reference_audit(self):
        self.guard.verify.return_value = {"n_algorithms_locked": 6}
        with self.assertRaisesRegex(RuntimeError, "Seven-arm blind freeze"):
            self.module.verify(self.args)
        self.audit.verify.assert_not_called()

    def test_external_reference_freeze_hash_drift_blocks_audit(self):
        self.gate.sha = Mock(return_value="wrong-sha")
        with self.assertRaisesRegex(RuntimeError, "separately archived copy"):
            self.module.verify(self.args)
        self.guard.verify.assert_not_called()

    def test_original_method_drift_blocks_audit(self):
        self.freeze["reference_method_source_sha256"] = "other"
        with self.assertRaisesRegex(RuntimeError, "source contract altered"):
            self.module.verify(self.args)

    def test_output_nested_in_reference_is_rejected(self):
        self.args.out = self.args.reference / "new_audit"
        with self.assertRaisesRegex(RuntimeError, "overlaps frozen input"):
            self.module.require_separate_output(self.args)


if __name__ == "__main__":
    unittest.main()
