"""Confirm geometrically remote non-adaptive M2-A2 candidates using public I1 only.

This stage is deliberately local. It does not run Optuna, does not adaptively
sample parameters, does not simulate the graph, and does not read graph WB.
It selects the most remote LHS-compatible candidates found by M2-A2, evaluates
them on the already established 100-trajectory M2-A confirmation seed bank,
and compares them against the confirmation ceiling frozen before this stage.
"""
from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
if str(PHASE3) not in sys.path:
    sys.path.insert(0, str(PHASE3))

from run_m1_provider_lift_v2 import load_verified_public_i1_cards  # noqa: E402
from m2_a_confirm_candidates import (  # noqa: E402
    _evaluate_candidates,
    _read_json,
    _seed_bank,
    _sha256,
    _write_json,
)

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_CONTRACT_STATUS = "PHASE4_M2_A3_REMOTE_LHS_CONFIRMATION_CONTRACT_V1"
EXPECTED_A2_STATUS = "PHASE4_M2_A2_NONADAPTIVE_COVERAGE_AUDIT_COMPLETE_V1"
EXPECTED_PREVIOUS_CONFIRM_STATUS = "PHASE4_M2_A_CONFIRMATION_PASS"


def _select_remote_candidates(frame: pd.DataFrame, max_per_provider: int) -> pd.DataFrame:
    required = {
        "provider",
        "candidate_id",
        "lhs_index",
        "mean_service_time",
        "cost_rate",
        "service_cv",
        "lhs_mse",
        "lhs_compatible",
        "nearest_existing_compatible_distance",
        "distance_from_frozen_m1",
        "outside_existing_compatible_bbox",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError("M2-A2 compatible LHS file lacks fields: " + ", ".join(missing))

    frame = frame[frame["lhs_compatible"].astype(bool)].copy()
    selected: list[pd.DataFrame] = []
    for provider in PROVIDERS:
        pool = frame[frame["provider"] == provider].copy()
        if pool.empty:
            continue
        pool = pool.sort_values(
            [
                "nearest_existing_compatible_distance",
                "distance_from_frozen_m1",
                "lhs_mse",
                "candidate_id",
            ],
            ascending=[False, False, True, True],
            kind="mergesort",
        ).head(int(max_per_provider)).copy()
        pool["selection_role"] = [f"REMOTE_LHS{i+1}" for i in range(len(pool))]
        selected.append(pool)

    if not selected:
        raise RuntimeError("no M2-A2 compatible LHS candidates available")
    out = pd.concat(selected, ignore_index=True)
    out["trial_number"] = out["lhs_index"].astype(int)
    out["source_relpath"] = (
        "phase4/results/m2_a2_nonadaptive_coverage_v1/m2_a2_compatible_lhs.csv"
    )
    out["search_mse"] = out["lhs_mse"].astype(float)
    return out


def main() -> None:
    started = time.perf_counter()
    contract_path = HERE / "config_phase4_m2_a3_remote_confirmation_v1.json"
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected M2-A3 contract status")

    firewall = dict(contract["firewall"])
    for forbidden in (
        "rerun_optuna",
        "adaptive_sampling",
        "graph_simulation",
        "graph_prediction_read",
        "graph_whitebox_read",
        "private_phase2_provider_traces_read",
        "hidden_phase1_provider_parameters_read",
    ):
        if bool(firewall.get(forbidden)):
            raise RuntimeError(f"M2-A3 firewall unexpectedly allows {forbidden}")

    a2_manifest_path = HERE / str(contract["input_a2_manifest"])
    a2_manifest = _read_json(a2_manifest_path)
    if a2_manifest.get("status") != EXPECTED_A2_STATUS:
        raise RuntimeError("unexpected M2-A2 manifest status")
    if bool(a2_manifest.get("sampler_adaptive")) or bool(a2_manifest.get("graph_whitebox_read")):
        raise RuntimeError("M2-A2 provenance violates M2-A3 input assumptions")

    previous_manifest_path = HERE / str(contract["previous_m2a_confirmation_manifest"])
    previous_manifest = _read_json(previous_manifest_path)
    if previous_manifest.get("status") != EXPECTED_PREVIOUS_CONFIRM_STATUS:
        raise RuntimeError("unexpected previous M2-A confirmation manifest status")
    if bool(previous_manifest.get("graph_whitebox_read")):
        raise RuntimeError("previous M2-A confirmation unexpectedly read graph WB")

    lhs_path = HERE / str(contract["input_a2_compatible_lhs"])
    lhs = pd.read_csv(lhs_path)
    max_per_provider = int(contract["selection_rule"]["max_remote_candidates_per_provider"])
    selected = _select_remote_candidates(lhs, max_per_provider=max_per_provider)

    previous_results_path = HERE / str(contract["previous_m2a_confirmation_results"])
    previous_results = pd.read_csv(previous_results_path)
    previous_best = (
        previous_results.groupby("provider", as_index=False)["confirmation_mse"]
        .min()
        .rename(columns={"confirmation_mse": "previous_best_confirmation_mse"})
    )
    if set(previous_best["provider"]) != set(PROVIDERS):
        raise RuntimeError("previous M2-A confirmation results do not cover all providers")

    output_root = HERE / "results" / "m2_a3_remote_confirmation_v1"
    output_root.mkdir(parents=True, exist_ok=True)
    selected_path = output_root / "m2_a3_selected_remote_candidates.csv"
    selected.to_csv(selected_path, index=False)

    print("M2_A3_REMOTE_CANDIDATES_FROZEN_BEFORE_CONFIRMATION_PASS")
    print(
        selected[
            [
                "provider",
                "candidate_id",
                "selection_role",
                "lhs_mse",
                "nearest_existing_compatible_distance",
                "distance_from_frozen_m1",
                "outside_existing_compatible_bbox",
                "mean_service_time",
                "cost_rate",
                "service_cv",
            ]
        ].to_string(index=False)
    )

    card_root = PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public"
    metadata_by_provider, surfaces, public_manifest = load_verified_public_i1_cards(card_root)

    closure_path = (HERE / str(contract["pilot_closure_source"])).resolve()
    closure = _read_json(closure_path)
    canonical_ipt = float(closure["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(closure["pilot_scope"]["execution_fraction"])

    confirm_cfg = dict(contract["confirmation"])
    confirm_seeds = _seed_bank(
        int(confirm_cfg["trajectory_seed_start"]),
        int(confirm_cfg["n_trajectories"]),
    )
    confirmation = _evaluate_candidates(
        selected,
        metadata_by_provider=metadata_by_provider,
        surfaces=surfaces,
        trajectory_seeds=confirm_seeds,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        output_root=output_root / "confirmation_surfaces",
        stage="confirmation",
    )
    geometry_cols = [
        "candidate_id",
        "nearest_existing_compatible_distance",
        "distance_from_frozen_m1",
        "outside_existing_compatible_bbox",
        "lhs_mse",
    ]
    confirmation = confirmation.merge(
        selected[geometry_cols], on="candidate_id", how="left", validate="one_to_one"
    ).merge(previous_best, on="provider", how="left", validate="many_to_one")

    ratio_max = float(confirm_cfg["compatibility_ratio_max_to_previous_best_confirmed"])
    confirmation["frozen_confirmation_mse_ceiling"] = (
        ratio_max * confirmation["previous_best_confirmation_mse"]
    )
    confirmation["confirmation_mse_ratio_to_previous_best"] = (
        confirmation["confirmation_mse"] / confirmation["previous_best_confirmation_mse"]
    )
    confirmation["confirmation_compatible"] = (
        confirmation["confirmation_mse"]
        <= confirmation["frozen_confirmation_mse_ceiling"] + 1e-15
    )
    confirmation_path = output_root / "m2_a3_remote_confirmation_results.csv"
    confirmation.to_csv(confirmation_path, index=False)

    compatible = confirmation[confirmation["confirmation_compatible"]].copy()
    compatible_path = output_root / "m2_a3_confirmed_remote_candidates.csv"
    compatible.to_csv(compatible_path, index=False)

    replay = pd.DataFrame()
    if not compatible.empty:
        replay_cfg = dict(contract["independent_replay"])
        replay_seeds = _seed_bank(
            int(replay_cfg["trajectory_seed_start"]),
            int(replay_cfg["n_trajectories"]),
        )
        replay_screen = selected[
            selected["candidate_id"].isin(set(compatible["candidate_id"]))
        ].copy()
        replay = _evaluate_candidates(
            replay_screen,
            metadata_by_provider=metadata_by_provider,
            surfaces=surfaces,
            trajectory_seeds=replay_seeds,
            canonical_ipt=canonical_ipt,
            execution_fraction=execution_fraction,
            output_root=output_root / "replay_surfaces",
            stage="replay",
        )
        replay.to_csv(output_root / "m2_a3_remote_replay_results.csv", index=False)

    elapsed = time.perf_counter() - started
    peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    counts = compatible.groupby("provider").size().to_dict() if not compatible.empty else {}
    manifest = {
        "status": "PHASE4_M2_A3_REMOTE_LHS_CONFIRMATION_COMPLETE_V1",
        "contract_sha256": _sha256(contract_path),
        "a2_manifest_sha256": _sha256(a2_manifest_path),
        "a2_compatible_lhs_sha256": _sha256(lhs_path),
        "previous_m2a_confirmation_manifest_sha256": _sha256(previous_manifest_path),
        "previous_m2a_confirmation_results_sha256": _sha256(previous_results_path),
        "public_i1_manifest_status": public_manifest.get("status"),
        "selected_counts": selected.groupby("provider").size().astype(int).to_dict(),
        "confirmed_remote_counts": {p: int(counts.get(p, 0)) for p in PROVIDERS},
        "confirmation_ratio_max_to_previous_best": ratio_max,
        "confirmation_seed_start": int(confirm_cfg["trajectory_seed_start"]),
        "confirmation_n_trajectories": int(confirm_cfg["n_trajectories"]),
        "replay_seed_start": int(contract["independent_replay"]["trajectory_seed_start"]),
        "replay_n_trajectories_per_confirmed_candidate": int(contract["independent_replay"]["n_trajectories"]),
        "reran_optuna": False,
        "sampler_adaptive": False,
        "graph_simulation": False,
        "graph_prediction_read": False,
        "graph_whitebox_read": False,
        "private_phase2_provider_traces_read": False,
        "python_wall_seconds": float(elapsed),
        "peak_rss_platform_units": peak_rss,
        "outputs": {
            "selected_remote_candidates": selected_path.name,
            "confirmation_results": confirmation_path.name,
            "confirmed_remote_candidates": compatible_path.name,
            "replay_results": "m2_a3_remote_replay_results.csv" if not compatible.empty else None,
        },
        "next_gate": (
            "Only confirmed remote candidates may enter a new one-at-a-time graph diagnostic. "
            "If remote candidates fail confirmation, treat the M2-A2 25-trajectory compatibility as search-noise evidence rather than stable public-I1 ambiguity."
        ),
    }
    _write_json(output_root / "m2_a3_remote_confirmation_manifest_v1.json", manifest)

    print("\nM2_A3_REMOTE_CONFIRMATION_RESULTS")
    print(
        confirmation[
            [
                "provider",
                "candidate_id",
                "selection_role",
                "confirmation_mse",
                "previous_best_confirmation_mse",
                "frozen_confirmation_mse_ceiling",
                "confirmation_mse_ratio_to_previous_best",
                "confirmation_compatible",
                "nearest_existing_compatible_distance",
                "distance_from_frozen_m1",
            ]
        ].to_string(index=False)
    )
    if not replay.empty:
        print("\nM2_A3_REMOTE_REPLAY_RESULTS")
        print(
            replay[
                ["provider", "candidate_id", "selection_role", "replay_mse", "replay_mae", "replay_bias"]
            ].to_string(index=False)
        )
    print("M2_A3_REMOTE_LHS_CONFIRMATION_COMPLETE")
    print(f"output={output_root.resolve()}")


if __name__ == "__main__":
    main()
