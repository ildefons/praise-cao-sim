"""Tests for Phase-1 atlas configuration that do not execute AICon/YAFS."""
from __future__ import annotations

import ast
import json
from pathlib import Path


def test_whitebox_runner_parses_as_python() -> None:
    """Verify the native runner is syntactically valid without importing YAFS.

    Called by:
        - ``execute_all_whitebox_atlas_configuration_tests`` in this module.
    """
    runner_path = Path(__file__).with_name("whitebox_atlas.py")
    ast.parse(runner_path.read_text(encoding="utf-8"))


def test_development_atlas_budget_and_physical_grid_are_explicit() -> None:
    """Verify N=10 and the exploratory Dbar/delta grid are explicit and non-scientific.

    Called by:
        - ``execute_all_whitebox_atlas_configuration_tests`` in this module.
    """
    configuration_path = Path(__file__).with_name("config_phase1_atlas_smoke.json")
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    assert configuration["configuration_status"] == "DEVELOPMENT_ATLAS_SMOKE_ONLY"
    assert configuration["scientific_evidence"] is False
    assert configuration["development_trajectory_count"] == 10
    assert len(configuration["development_seeds"]) == 10
    assert len(configuration["physical_atlas"]["center_instruction_means"]) == 3
    assert len(configuration["physical_atlas"]["dispersions"]) == 3
    assert configuration["admissibility_scan"]["anchor_horizon"] == 120.0
    assert configuration["horizon"]["maximum"] == 240.0


def test_new_phase1_functions_follow_descriptive_documentation_requirement() -> None:
    """Verify non-trivial functions have descriptive names and Called-by docstrings.

    Called by:
        - ``execute_all_whitebox_atlas_configuration_tests`` in this module.
    """
    forbidden_generic_names = {"run", "process", "handle", "calc", "helper", "main"}
    for source_name in ("whitebox_atlas.py", "atlas_analysis.py"):
        source_path = Path(__file__).with_name(source_name)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in {"get_path", "initial_allocation"}:
                    continue
                assert node.name not in forbidden_generic_names, (source_name, node.name)
                documentation = ast.get_docstring(node)
                assert documentation is not None, (source_name, node.name)
                assert "Called by:" in documentation, (source_name, node.name)


def execute_all_whitebox_atlas_configuration_tests() -> None:
    """Execute all simulator-independent native-runner configuration tests.

    Called by:
        - Python ``__main__`` entry point of this module.
    """
    test_whitebox_runner_parses_as_python()
    test_development_atlas_budget_and_physical_grid_are_explicit()
    test_new_phase1_functions_follow_descriptive_documentation_requirement()
    print("PHASE1_WHITEBOX_ATLAS_CONFIGURATION_TESTS_PASS")


if __name__ == "__main__":
    execute_all_whitebox_atlas_configuration_tests()
