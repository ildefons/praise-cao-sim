#!/usr/bin/env python3
"""Prepare-only gate for the fixed-graph G0/G1/G2 sigma-regime battery.

This stage generates no white-box trajectories. It verifies that the new
battery changes only the global admissibility query, not the graph, workload,
provider process, I1, or prediction methods.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE1 = FIRST_SCIENCE / "phase1"
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
for directory in (PHASE1, PHASE2, PHASE3, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from m0_phase1_benchmark_adapter import build_phase1_g0_full_m0_boundary
from m1_graph_simulator_v2 import validate_public_graph_spec
from run_m1_graph_prediction_v2 import _common_workload_contract
from m2_b2_remote_graph import _read_json, _sha256
from m2_g2_step0_calibration import _validate_hidden_model

EXPECTED_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_BATTERY_STEP0_V1"
TOL = 1e-12


def _scale_grid(spec: dict[str, Any]) -> np.ndarray:
    low = float(spec["minimum"])
    high = float(spec["maximum"])
    step = float(spec["step"])
    if low <= 0 or high < low or step <= 0:
        raise RuntimeError("invalid frozen scale grid")
    n = int(round((high - low) / step))
    grid = low + step * np.arange(n + 1, dtype=float)
    if abs(float(grid[-1]) - high) > 1e-10:
        raise RuntimeError("scale-grid endpoint does not match step")
    return np.round(grid, 12)


def _fixed_graph_spec(m0_contract: dict[str, Any]) -> dict[str, Any]:
    if m0_contract.get("status") != "FROZEN_PHASE3_M0_BASELINE_V2_SAME_RHO":
        raise RuntimeError("unexpected M0 contract status")
    adapter = dict(m0_contract["phase1_benchmark_adapter"])
    spec = {
        "graph": str(adapter["graph"]),
        "network_model": dict(adapter["network_model"]),
        "fixed_service_model": dict(adapter["fixed_service_model"]),
    }
    validate_public_graph_spec(spec)
    if spec["graph"] != "Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost":
        raise RuntimeError("logical graph changed")
    net = spec["network_model"]
    if abs(float(net["PR"]) - 0.001) > TOL:
        raise RuntimeError("fixed battery must use exact G0 PR=0.001 s")
    if abs(float(net["BW_mbps"]) - 1000.0) > TOL:
        raise RuntimeError("fixed battery bandwidth changed")
    for key in ("request_bytes", "branch_bytes", "join_bytes"):
        if int(net[key]) != 1000:
            raise RuntimeError(f"fixed G0 field changed: {key}")
    return spec


def _base_regions(
    phase1_config: dict[str, Any],
    metadata: dict[str, dict[str, object]],
    rho_values: list[float],
) -> pd.DataFrame:
    rows = []
    for rho in rho_values:
        local = provider_boundaries_at_region_rho(metadata, float(rho))
        base, breakdown = build_phase1_g0_full_m0_boundary(phase1_config, local)
        rows.append(
            {
                "rho_global": float(rho),
                "base_l_max": float(base.l_max),
                "base_c_max": float(base.c_max),
                "base_q_min": float(base.q_min),
                "fixed_latency_outside_provider": float(
                    breakdown.fixed_latency_outside_provider
                ),
                "fixed_cost_outside_provider": float(
                    breakdown.fixed_cost_outside_provider
                ),
            }
        )
    return pd.DataFrame(rows)


def _validate_seed_banks(contract: dict[str, Any]) -> None:
    step0 = dict(contract["step0_calibration"])
    pred = dict(contract["blind_prediction_protocol_after_calibration"])
    final = dict(contract["final_whitebox_evaluation"])
    specs = [
        ("selection", step0["selection_seed_start"], step0["selection_seed_end_inclusive"], step0["selection_n_trajectories"]),
        ("confirmation", step0["confirmation_seed_start"], step0["confirmation_seed_end_inclusive"], step0["confirmation_n_trajectories"]),
        ("prediction", pred["prediction_seed_start"], pred["prediction_seed_end_inclusive"], pred["n_prediction_trajectories_per_variant"]),
        ("final", final["trajectory_seed_start"], final["trajectory_seed_end_inclusive"], final["n_trajectories"]),
    ]
    banks = []
    for label, start, end, n in specs:
        bank = set(range(int(start), int(end) + 1))
        if len(bank) != int(n):
            raise RuntimeError(f"{label} seed-bank length mismatch")
        banks.append((label, bank))
    for i, (name_i, bank_i) in enumerate(banks):
        for name_j, bank_j in banks[i + 1:]:
            if bank_i.intersection(bank_j):
                raise RuntimeError(f"seed banks overlap: {name_i}/{name_j}")


def run(args: argparse.Namespace) -> None:
    contract = _read_json(args.contract.resolve())
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected sigma-regime contract status")

    freeze = dict(contract["method_freeze"])
    required_true = (
        "I1_unchanged",
        "M0_semantics_unchanged",
        "M1_parameters_unchanged",
        "M2_provider_members_unchanged",
    )
    for key in required_true:
        if not bool(freeze.get(key)):
            raise RuntimeError(f"method freeze false: {key}")
    if bool(freeze["step0_may_read_or_run_M0_M1_M2"]):
        raise RuntimeError("Step-0 predictor firewall is open")
    if int(freeze["M2_joint_members"]) != 27:
        raise RuntimeError("M2 member count changed")
    if str(freeze["M2_member_weight"]) != "1/27":
        raise RuntimeError("M2 weights changed")

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    rho_values = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)

    step0 = dict(contract["step0_calibration"])
    window = dict(step0["diagnostic_horizon_window"])
    hmin = float(window["minimum_horizon_seconds"])
    hmax = float(window["maximum_horizon_seconds"])
    diagnostic_horizons = [
        float(h) for h in horizons if hmin - TOL <= float(h) <= hmax + TOL
    ]
    if not diagnostic_horizons:
        raise RuntimeError("empty diagnostic horizon window")
    if abs(diagnostic_horizons[0] - hmin) > TOL:
        raise RuntimeError("diagnostic Hmin not on frozen support")
    if abs(diagnostic_horizons[-1] - hmax) > TOL:
        raise RuntimeError("diagnostic Hmax not on frozen support")
    if abs(float(max(horizons)) - float(workload["horizon_max"])) > TOL:
        raise RuntimeError("I1 Hmax/workload mismatch")

    regimes = dict(step0["regimes"])
    expected_bands = {
        "G0": (0.95, 1.00, 0.975),
        "G1": (0.75, 0.90, 0.825),
        "G2": (0.40, 0.75, 0.575),
    }
    if tuple(regimes.keys()) != ("G0", "G1", "G2"):
        raise RuntimeError("regimes must be ordered G0,G1,G2")
    for name, (low, high, center) in expected_bands.items():
        rec = dict(regimes[name])
        if (
            abs(float(rec["sigma_lower"]) - low) > TOL
            or abs(float(rec["sigma_upper"]) - high) > TOL
            or abs(float(rec["target_center"]) - center) > TOL
        ):
            raise RuntimeError(f"{name} frozen sigma band changed")

    scales = _scale_grid(dict(step0["candidate_family"]["scale_grid"]))
    _validate_seed_banks(contract)

    phase1_config = _read_json(args.phase1_config.resolve())
    m0_contract = _read_json(args.m0_contract.resolve())
    graph_spec = _fixed_graph_spec(m0_contract)
    _, _, provenance = _validate_hidden_model(
        contract, phase1_config_path=args.phase1_config.resolve()
    )
    if str(provenance["case_id"]) != "D300000000_d0.200":
        raise RuntimeError("provider process is not matched D300")
    if not bool(provenance["matched_i1_provider_process"]):
        raise RuntimeError("hidden provider process is not matched to I1")

    base = _base_regions(phase1_config, metadata, rho_values)

    print("SIGMA_REGIME_STEP0_PREPARE_PASS_NO_WHITEBOX")
    print("graph_changed_across_regimes=false")
    print(f"fixed_graph={graph_spec['graph']}")
    print(f"fixed_PR_seconds={graph_spec['network_model']['PR']}")
    print(f"provider_process={provenance['case_id']}")
    print(f"provider_process_sha256={provenance['provider_process_sha256']}")
    print(f"rho_values={rho_values}")
    print(
        f"diagnostic_horizons={diagnostic_horizons[0]:g}.."
        f"{diagnostic_horizons[-1]:g} n={len(diagnostic_horizons)}"
    )
    print(
        f"scale_grid={float(scales[0]):g}..{float(scales[-1]):g} "
        f"step={float(scales[1]-scales[0]):g} n={len(scales)}"
    )
    print("sigma_bands=" + json.dumps(expected_bands))
    print("\nBASE_G0_GRAPH_REGIONS")
    print(base.to_string(index=False))
    print("\nSEED_BANKS")
    print(
        f"selection={step0['selection_seed_start']}.."
        f"{step0['selection_seed_end_inclusive']}"
    )
    print(
        f"confirmation={step0['confirmation_seed_start']}.."
        f"{step0['confirmation_seed_end_inclusive']}"
    )
    pred = contract["blind_prediction_protocol_after_calibration"]
    final = contract["final_whitebox_evaluation"]
    print(
        f"prediction={pred['prediction_seed_start']}.."
        f"{pred['prediction_seed_end_inclusive']}"
    )
    print(
        f"final_WB={final['trajectory_seed_start']}.."
        f"{final['trajectory_seed_end_inclusive']}"
    )
    print("\nHASHES")
    print(f"contract_sha256={_sha256(args.contract.resolve())}")
    print(f"m0_contract_sha256={_sha256(args.m0_contract.resolve())}")
    print(f"public_i1_manifest_sha256={_sha256(args.i1_manifest.resolve())}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare fixed-graph three-sigma-regime Step-0 calibration"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_sigma_regime_battery_step0_v1.json",
    )
    parser.add_argument(
        "--phase1-config",
        type=Path,
        default=PHASE1 / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--m0-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m0_contract_v1.json",
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    parser.add_argument("--prepare-only", action="store_true", required=True)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
