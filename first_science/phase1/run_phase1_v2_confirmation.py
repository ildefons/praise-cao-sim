"""Run the frozen Phase-1 v2 fresh paired N=100 confirmation.

This runner is versioned separately from the historical Phase-1 v1 confirmation
machinery because v2 selection intentionally used a stricter rho=0.99 stress
criterion. The v1 presearch contract forbids alternative rho values from driving
selection and therefore must not be silently reused for v2.

The v2 selection is already frozen before this runner executes. The fresh bank
may confirm or contradict the frozen design, but it may not retune A, rho, the
selection gates, source preference, or case membership.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import pandas as pd

MODULE_DIRECTORY = Path(__file__).resolve().parent
FIRST_SCIENCE_DIRECTORY = MODULE_DIRECTORY.parent
DIAGNOSTICS_DIRECTORY = FIRST_SCIENCE_DIRECTORY / "diagnostics"
if str(DIAGNOSTICS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(DIAGNOSTICS_DIRECTORY))

from phase1_v2_multi_rho_candidate_landscape import evaluate_candidate_landscape  # noqa: E402
from run_n100_matched_confirmation import execute_shared_physical_n100_trajectories  # noqa: E402

EXPECTED_PROTOCOL_STATUS = "FROZEN_PHASE1_V2_CONFIRMATION_PROTOCOL_V1"
EXPECTED_MANIFEST_STATUS = "FROZEN_PHASE1_V2_AR_SELECTION_V1"
EXPECTED_SETTING = "D300000000_d0.200"
EXPECTED_ROLES = {"latency", "cost", "mixed"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_v2_confirmation_inputs(
    base_configuration: dict[str, Any],
    protocol: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    """Validate all frozen v2 confirmation inputs without importing AICon/YAFS."""
    if protocol.get("status") != EXPECTED_PROTOCOL_STATUS:
        raise ValueError("unexpected Phase-1 v2 confirmation protocol status")
    if manifest.get("status") != EXPECTED_MANIFEST_STATUS:
        raise ValueError("Phase-1 v2 AR manifest is not frozen")

    setting = str(protocol.get("physical_setting_id"))
    if setting != EXPECTED_SETTING:
        raise ValueError("unexpected v2 confirmation physical setting")
    if str(manifest["physical_setting"]["physical_setting_id"]) != setting:
        raise ValueError("protocol/manifest physical setting mismatch")
    if manifest.get("paired_matched_physical_regime") is not True:
        raise ValueError("v2 confirmation requires one paired physical regime")

    whiteboxes = manifest.get("whiteboxes")
    if not isinstance(whiteboxes, list) or len(whiteboxes) != 3:
        raise ValueError("v2 confirmation requires exactly three frozen whiteboxes")
    if {str(w.get("selection_role")) for w in whiteboxes} != EXPECTED_ROLES:
        raise ValueError("v2 whiteboxes must contain latency, cost and mixed roles")
    if {str(w.get("physical_setting_id")) for w in whiteboxes} != {setting}:
        raise ValueError("all v2 whiteboxes must share the frozen physical setting")

    seeds = list(map(int, protocol.get("seed_bank", [])))
    manifest_seeds = list(map(int, manifest["fresh_confirmation"]["seed_bank"]))
    if len(seeds) != 100 or len(set(seeds)) != 100:
        raise ValueError("v2 confirmation requires exactly 100 unique seeds")
    if seeds != manifest_seeds:
        raise ValueError("protocol seed bank differs from frozen v2 AR manifest")
    if int(protocol.get("n_trajectories", -1)) != 100:
        raise ValueError("v2 confirmation protocol must declare N=100")

    rhos = tuple(map(float, protocol.get("rho_values", [])))
    if rhos != (0.95, 0.975, 0.99):
        raise ValueError("v2 confirmation rho grid must remain (0.95,0.975,0.99)")
    if abs(float(protocol.get("primary_rho")) - 0.95) > 1e-12:
        raise ValueError("v2 primary rho must remain 0.95")
    if abs(float(protocol.get("stress_rho")) - 0.99) > 1e-12:
        raise ValueError("v2 stress rho must remain 0.99")
    if protocol.get("accounting_window") != "cumulative_[0,H]_from_t0":
        raise ValueError("v2 accounting window must remain cumulative [0,H] from t=0")
    if abs(float(protocol.get("accounting_origin"))) > 1e-12:
        raise ValueError("v2 accounting origin must remain t=0")
    if abs(float(protocol.get("zero_decided_requests_compliance")) - 1.0) > 1e-12:
        raise ValueError("v2 zero-decided convention must remain one")

    rule = protocol.get("confirmation_rule", {})
    nominal = rule.get("nominal_health", {})
    stress = rule.get("stress_informativeness", {})
    if abs(float(nominal.get("rho", -1.0)) - 0.95) > 1e-12:
        raise ValueError("v2 nominal confirmation rho must be 0.95")
    if abs(float(nominal.get("minimum_R", -1.0)) - 0.95) > 1e-12:
        raise ValueError("v2 nominal confirmation gate must be R_0.95>=0.95")
    if abs(float(stress.get("rho", -1.0)) - 0.99) > 1e-12:
        raise ValueError("v2 stress confirmation rho must be 0.99")
    if abs(float(stress.get("minimum_R", -1.0)) - 0.50) > 1e-12:
        raise ValueError("v2 stress lower gate must be 0.50")
    if abs(float(stress.get("maximum_R", -1.0)) - 0.95) > 1e-12:
        raise ValueError("v2 stress upper gate must be 0.95")
    if rule.get("role_must_replicate") is not True:
        raise ValueError("v2 confirmation must require role replication")
    if rule.get("all_three_cases_must_pass") is not True:
        raise ValueError("v2 confirmation must require all three cases to pass")

    for key in ("recalibrate_A", "recalibrate_rho", "reopen_selection_gate", "replace_case_after_confirmation"):
        if protocol.get(key) is not False:
            raise ValueError(f"v2 confirmation protocol must freeze {key}=false")

    # Validate only the simulator/accounting facts that remain shared with v1.
    horizon = base_configuration.get("horizon", {})
    if abs(float(horizon.get("simulation_stop_time", -1.0)) - 240.0) > 1e-12:
        raise ValueError("Phase-1 v2 confirmation requires simulation_stop_time=240")
    workload = base_configuration.get("workload", {})
    if abs(float(workload.get("period", -1.0)) - 0.2) > 1e-12:
        raise ValueError("Phase-1 v2 confirmation requires workload period=0.2")
    provider = base_configuration.get("provider_family", {})
    if abs(float(provider.get("instruction_cv", -1.0)) - 0.3) > 1e-12:
        raise ValueError("Phase-1 v2 confirmation requires provider instruction_cv=0.3")
    if abs(float(provider.get("effective_ipt", -1.0)) - 1e9) > 1e-6:
        raise ValueError("Phase-1 v2 confirmation requires effective_ipt=1e9")


def build_effective_v2_confirmation_configuration(
    base_configuration: dict[str, Any],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    """Build an execution-only config without modifying historical v1 files."""
    effective = deepcopy(base_configuration)
    effective.setdefault("confirmation", {})["confirmation_seed_bank"] = list(
        map(int, protocol["seed_bank"])
    )
    effective["confirmation"]["n_trajectories_per_selected_whitebox"] = 100
    effective["phase1_v2_confirmation"] = {
        "status": protocol["status"],
        "physical_setting_id": protocol["physical_setting_id"],
        "rho_values": list(map(float, protocol["rho_values"])),
        "selection_already_frozen": True,
        "recalibration_forbidden": True,
    }
    return effective


def _regions_from_manifest(manifest: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for whitebox in manifest["whiteboxes"]:
        rows.append(
            {
                "physical_setting_id": str(whitebox["physical_setting_id"]),
                "region_id": str(whitebox["region_id"]),
                "l_max": float(whitebox["l_max"]),
                "c_max": float(whitebox["c_max"]),
                "q_min": float(whitebox["q_min"]),
                "selection_role": str(whitebox["selection_role"]),
                "source_family": str(whitebox["source_family"]),
            }
        )
    return pd.DataFrame(rows)


def assess_v2_confirmation_summary(
    wide_summary: pd.DataFrame,
    manifest: dict[str, Any],
    protocol: dict[str, Any],
) -> pd.DataFrame:
    """Apply the predeclared fresh-confirmation rule to computed metrics."""
    intended_role = {
        str(w["region_id"]): str(w["selection_role"])
        for w in manifest["whiteboxes"]
    }
    result = wide_summary.copy()
    result["selection_role"] = result["region_id"].astype(str).map(intended_role)
    if result["selection_role"].isna().any():
        raise RuntimeError("confirmation summary contains an unknown region_id")

    rule = protocol["confirmation_rule"]
    nominal_min = float(rule["nominal_health"]["minimum_R"])
    stress_min = float(rule["stress_informativeness"]["minimum_R"])
    stress_max = float(rule["stress_informativeness"]["maximum_R"])

    result["role_replication_pass"] = (
        result["descriptive_role"].astype(str) == result["selection_role"].astype(str)
    )
    result["nominal_health_pass"] = (
        result["area_rho_0p95"].astype(float) >= nominal_min
    )
    result["stress_informativeness_pass"] = (
        (result["area_rho_0p99"].astype(float) >= stress_min)
        & (result["area_rho_0p99"].astype(float) <= stress_max)
    )
    result["fresh_confirmation_pass"] = (
        result["role_replication_pass"].astype(bool)
        & result["nominal_health_pass"].astype(bool)
        & result["stress_informativeness_pass"].astype(bool)
    )

    role_order = pd.CategoricalDtype(["latency", "cost", "mixed"], ordered=True)
    result["_role_order"] = result["selection_role"].astype(role_order)
    result = result.sort_values("_role_order").drop(columns="_role_order").reset_index(drop=True)
    return result


def execute_phase1_v2_confirmation(
    base_config_path: Path,
    protocol_path: Path,
    manifest_path: Path,
    output_directory: Path,
    clean: bool,
) -> pd.DataFrame:
    """Execute one fresh physical N=100 bank and evaluate the three frozen A_G."""
    base = _load_json(base_config_path)
    protocol = _load_json(protocol_path)
    manifest = _load_json(manifest_path)
    validate_v2_confirmation_inputs(base, protocol, manifest)
    effective = build_effective_v2_confirmation_configuration(base, protocol)

    if clean and output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "effective_config.json").write_text(
        json.dumps(effective, indent=2), encoding="utf-8"
    )
    (output_directory / "v2_confirmation_protocol_frozen.json").write_text(
        json.dumps(protocol, indent=2), encoding="utf-8"
    )
    (output_directory / "v2_ar_manifest_frozen.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    ledgers = execute_shared_physical_n100_trajectories(
        effective, manifest, output_directory
    )

    regions = _regions_from_manifest(manifest)
    rhos = tuple(map(float, protocol["rho_values"]))
    horizons = tuple(map(float, protocol["report_horizons"]))
    stop_time = float(protocol["normalized_area_horizon"][1])
    dominance_ratio = float(protocol["role_dominance_ratio"])

    long_metrics, wide_summary = evaluate_candidate_landscape(
        regions,
        ledgers,
        rho_values=rhos,
        report_horizons=horizons,
        stop_time=stop_time,
        dominance_ratio=dominance_ratio,
        expected_trajectories=100,
    )
    assessed = assess_v2_confirmation_summary(wide_summary, manifest, protocol)

    role_map = {
        str(w["region_id"]): str(w["selection_role"])
        for w in manifest["whiteboxes"]
    }
    long_metrics["selection_role"] = long_metrics["region_id"].astype(str).map(role_map)

    long_metrics.to_csv(output_directory / "v2_confirmation_metrics_long.csv", index=False)
    assessed.to_csv(output_directory / "v2_confirmation_summary.csv", index=False)

    overall = bool(assessed["fresh_confirmation_pass"].all())
    display_columns = [
        "selection_role",
        "region_id",
        "descriptive_role",
        "area_rho_0p95",
        "area_rho_0p975",
        "area_rho_0p99",
        "sigma_120_rho_0p95",
        "sigma_240_rho_0p95",
        "sigma_120_rho_0p99",
        "sigma_240_rho_0p99",
        "latency_failure_count",
        "cost_failure_count",
        "role_replication_pass",
        "nominal_health_pass",
        "stress_informativeness_pass",
        "fresh_confirmation_pass",
    ]
    available = [column for column in display_columns if column in assessed.columns]

    print("PHASE1_V2_FRESH_CONFIRMATION_RUN_PASS")
    print("selection_reopened=false")
    print("recalibration_performed=false")
    print(assessed[available].to_string(index=False))
    print(f"scientific_confirmation_pass={str(overall).lower()}")
    if not overall:
        print("protocol_failure_action=report_and_stop_without_retuning")
    print(f"output={output_directory.resolve()}")
    return assessed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-config",
        type=Path,
        default=MODULE_DIRECTORY / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=MODULE_DIRECTORY / "config_phase1_v2_confirmation_v1.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MODULE_DIRECTORY / "phase1_v2_ar_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=MODULE_DIRECTORY / "results" / "phase1_v2_fresh_confirmation_v1",
    )
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    execute_phase1_v2_confirmation(
        args.base_config.resolve(),
        args.protocol.resolve(),
        args.manifest.resolve(),
        args.output.resolve(),
        clean=bool(args.clean),
    )


if __name__ == "__main__":
    main()
