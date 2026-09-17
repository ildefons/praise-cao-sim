"""Confirm diverse M2-A candidates using only the frozen public I1 surfaces.

This stage does not rerun Optuna and does not read graph predictions or graph
white-box data. It takes the existing M1-v2 search landscape, applies a frozen
public-I1-only screening rule, re-evaluates the selected candidates on a common
100-trajectory local confirmation bank, freezes the compatible set, and then
replays that set on an independent local bank for diagnostics only.
"""
from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"

if str(PHASE3) not in sys.path:
    sys.path.insert(0, str(PHASE3))

from run_m1_provider_lift_v2 import (  # noqa: E402
    _simulate_and_score,
    load_verified_public_i1_cards,
)

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_LANDSCAPE_STATUS = "PHASE4_M2_A_LOCAL_LANDSCAPE_INSPECTION_V1"
EXPECTED_FREEZE_STATUS = "FROZEN_PHASE3_I1_M1_V2_PILOT"
EXPECTED_CONTRACT_STATUS = "PHASE4_M2_A_CONFIRMATION_CONTRACT_V1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _seed_bank(start: int, n: int) -> tuple[int, ...]:
    return tuple(range(int(start), int(start) + int(n)))


def _candidate_id(provider: str, role: str, source_relpath: str, trial_number: int) -> str:
    source_tag = "expanded" if "expanded" in source_relpath else "base"
    return f"{provider}_{role}_{source_tag}_trial{int(trial_number):03d}"


def _frozen_anchor_row(pool: pd.DataFrame, provider: str, freeze: dict[str, Any]) -> pd.Series:
    rec = freeze["provider_surrogates"][provider]
    mu = float(rec["mean_service_time"])
    kappa = float(rec["cost_rate"])
    cv = float(rec["service_cv"])

    score = (
        np.abs(np.log(pool["mean_service_time"].astype(float) / mu))
        + np.abs(np.log(pool["cost_rate"].astype(float) / kappa))
        + np.abs(pool["service_cv"].astype(float) - cv)
    )
    idx = score.idxmin()
    row = pool.loc[idx]
    if float(score.loc[idx]) > 1e-8:
        raise RuntimeError(
            f"{provider}: frozen M1 surrogate not found in screened search landscape"
        )
    return row


def _select_screen_candidates(
    candidates: pd.DataFrame,
    freeze: dict[str, Any],
    *,
    loss_ratio_max: float,
    n_candidates: int,
) -> pd.DataFrame:
    selected_rows: list[pd.Series] = []

    for provider in PROVIDERS:
        frame = candidates[candidates["provider"] == provider].copy()
        if frame.empty:
            raise RuntimeError(f"{provider}: no landscape candidates")
        best = float(frame["search_mse"].min())
        pool = frame[
            frame["search_mse"].astype(float) <= best * float(loss_ratio_max) + 1e-15
        ].copy()
        if len(pool) < int(n_candidates):
            raise RuntimeError(
                f"{provider}: only {len(pool)} candidates inside {loss_ratio_max}x loss band"
            )

        anchor = _frozen_anchor_row(pool, provider, freeze)
        chosen_indices = [anchor.name]
        roles = ["M1"]

        while len(chosen_indices) < int(n_candidates):
            remaining = pool.drop(index=chosen_indices).copy()
            selected_coords = pool.loc[
                chosen_indices, ["z_log_mu", "z_log_kappa", "z_cv"]
            ].to_numpy(dtype=float)
            candidate_coords = remaining[
                ["z_log_mu", "z_log_kappa", "z_cv"]
            ].to_numpy(dtype=float)
            distances = np.linalg.norm(
                candidate_coords[:, None, :] - selected_coords[None, :, :], axis=2
            )
            remaining["_min_distance"] = distances.min(axis=1)
            remaining = remaining.sort_values(
                ["_min_distance", "search_mse", "trial_number", "source_relpath"],
                ascending=[False, True, True, True],
            )
            chosen_indices.append(remaining.index[0])
            roles.append(f"ALT{len(chosen_indices)-1}")

        chosen = pool.loc[chosen_indices].copy()
        chosen["selection_role"] = roles
        chosen["screen_loss_ratio_max"] = float(loss_ratio_max)
        chosen["candidate_id"] = [
            _candidate_id(
                provider,
                role,
                str(row.source_relpath),
                int(row.trial_number),
            )
            for role, row in zip(roles, chosen.itertuples(index=False))
        ]

        coords = chosen[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(float)
        anchor_coord = coords[0]
        chosen["distance_from_frozen_m1"] = np.linalg.norm(
            coords - anchor_coord[None, :], axis=1
        )
        selected_rows.extend([row for _, row in chosen.iterrows()])

    out = pd.DataFrame(selected_rows).reset_index(drop=True)
    return out


def _evaluate_candidates(
    screen: pd.DataFrame,
    *,
    metadata_by_provider: dict[str, dict[str, object]],
    surfaces: dict[str, pd.DataFrame],
    trajectory_seeds: tuple[int, ...],
    canonical_ipt: float,
    execution_fraction: float,
    output_root: Path,
    stage: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for rec in screen.itertuples(index=False):
        provider = str(rec.provider)
        candidate_id = str(rec.candidate_id)
        print(f"{stage} {candidate_id}", flush=True)
        metrics, simulated, comparison = _simulate_and_score(
            metadata=metadata_by_provider[provider],
            public_surface=surfaces[provider],
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
            trajectory_seeds=trajectory_seeds,
            canonical_ipt=float(canonical_ipt),
            execution_fraction=float(execution_fraction),
            quiet=True,
        )
        candidate_dir = output_root / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        simulated.to_csv(candidate_dir / f"{stage}_sigma_surface.csv", index=False)
        comparison.to_csv(candidate_dir / f"{stage}_comparison.csv", index=False)
        rows.append(
            {
                "provider": provider,
                "candidate_id": candidate_id,
                "selection_role": str(rec.selection_role),
                "trial_number": int(rec.trial_number),
                "source_relpath": str(rec.source_relpath),
                "mean_service_time": float(rec.mean_service_time),
                "cost_rate": float(rec.cost_rate),
                "service_cv": float(rec.service_cv),
                "search_mse": float(rec.search_mse),
                f"{stage}_mse": float(metrics["mse"]),
                f"{stage}_rmse": float(metrics["rmse"]),
                f"{stage}_mae": float(metrics["mae"]),
                f"{stage}_bias": float(metrics["bias"]),
                f"{stage}_max_abs_error": float(metrics["max_abs_error"]),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    started = time.perf_counter()

    contract_path = HERE / "config_phase4_m2_a_confirmation_v1.json"
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected M2-A confirmation contract status")

    landscape_root = HERE / str(contract["input_landscape"])
    landscape_manifest_path = landscape_root / "m2_a_landscape_manifest_v1.json"
    all_candidates_path = landscape_root / "m2_a_all_candidates.csv"
    landscape_manifest = _read_json(landscape_manifest_path)
    if landscape_manifest.get("status") != EXPECTED_LANDSCAPE_STATUS:
        raise RuntimeError("unexpected M2-A landscape manifest status")
    if landscape_manifest.get("reran_optuna") is not False:
        raise RuntimeError("M2-A landscape unexpectedly reran Optuna")
    if landscape_manifest.get("graph_whitebox_read") is not False:
        raise RuntimeError("M2-A landscape unexpectedly read graph WB")
    if landscape_manifest.get("graph_prediction_read_for_selection") is not False:
        raise RuntimeError("M2-A landscape unexpectedly read graph predictions")

    freeze_path = (HERE / str(contract["frozen_m1_source"])).resolve()
    freeze = _read_json(freeze_path)
    if freeze.get("status") != EXPECTED_FREEZE_STATUS:
        raise RuntimeError("unexpected frozen M1-v2 manifest status")

    candidates = pd.read_csv(all_candidates_path)
    screen_cfg = dict(contract["screening_rule"])
    screen = _select_screen_candidates(
        candidates,
        freeze,
        loss_ratio_max=float(screen_cfg["search_loss_ratio_max"]),
        n_candidates=int(screen_cfg["n_candidates_per_provider"]),
    )

    output_root = HERE / "results" / "m2_a_confirmation_v1"
    output_root.mkdir(parents=True, exist_ok=True)
    screen_path = output_root / "m2_a_screen_candidates.csv"
    screen.to_csv(screen_path, index=False)
    print("M2_A_SCREEN_SET_MATERIALIZED_BEFORE_CONFIRMATION_PASS")
    print(screen[
        [
            "provider",
            "candidate_id",
            "selection_role",
            "trial_number",
            "search_mse",
            "loss_ratio_to_best",
            "mean_service_time",
            "cost_rate",
            "service_cv",
            "distance_from_frozen_m1",
        ]
    ].to_string(index=False))

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
        screen,
        metadata_by_provider=metadata_by_provider,
        surfaces=surfaces,
        trajectory_seeds=confirm_seeds,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        output_root=output_root / "confirmation_surfaces",
        stage="confirmation",
    )

    ratio_max = float(
        confirm_cfg["compatibility_mse_ratio_max_to_best_confirmed_in_provider_screen_set"]
    )
    confirmation["best_confirmation_mse_in_provider"] = confirmation.groupby("provider")[
        "confirmation_mse"
    ].transform("min")
    confirmation["confirmation_mse_ratio_to_best"] = (
        confirmation["confirmation_mse"]
        / confirmation["best_confirmation_mse_in_provider"]
    )
    confirmation["confirmation_compatible"] = (
        confirmation["confirmation_mse_ratio_to_best"] <= ratio_max + 1e-15
    )
    confirmation_path = output_root / "m2_a_confirmation_results.csv"
    confirmation.to_csv(confirmation_path, index=False)

    compatible = confirmation[confirmation["confirmation_compatible"]].copy()
    compatible_path = output_root / "m2_a_confirmed_compatible_candidates.csv"
    compatible.to_csv(compatible_path, index=False)

    counts = compatible.groupby("provider").size().to_dict()
    minimum_required = int(confirm_cfg["minimum_confirmed_compatible_candidates_per_provider"])
    gate_pass = all(int(counts.get(provider, 0)) >= minimum_required for provider in PROVIDERS)

    replay = pd.DataFrame()
    if gate_pass:
        replay_cfg = dict(contract["independent_replay"])
        replay_seeds = _seed_bank(
            int(replay_cfg["trajectory_seed_start"]),
            int(replay_cfg["n_trajectories"]),
        )
        replay_screen = screen[
            screen["candidate_id"].isin(set(compatible["candidate_id"]))
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
        replay.to_csv(output_root / "m2_a_replay_results.csv", index=False)

    elapsed = time.perf_counter() - started
    peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    n_confirmation = len(screen) * len(confirm_seeds)
    n_replay = 0
    if gate_pass:
        n_replay = len(compatible) * int(contract["independent_replay"]["n_trajectories"])

    manifest = {
        "status": (
            "PHASE4_M2_A_CONFIRMATION_PASS"
            if gate_pass
            else "PHASE4_M2_A_CONFIRMATION_DIVERSITY_GATE_FAIL"
        ),
        "scientific_stage": "M2-A local public-I1 compatibility confirmation; no graph composition",
        "contract": {"path": str(contract_path), "sha256": _sha256(contract_path)},
        "landscape_manifest": {
            "path": str(landscape_manifest_path),
            "sha256": _sha256(landscape_manifest_path),
        },
        "all_candidates": {"path": str(all_candidates_path), "sha256": _sha256(all_candidates_path)},
        "frozen_m1_manifest": {"path": str(freeze_path), "sha256": _sha256(freeze_path)},
        "public_i1_manifest_status": public_manifest.get("status"),
        "selection_rule": screen_cfg,
        "confirmation_rule": confirm_cfg,
        "confirmed_counts": {provider: int(counts.get(provider, 0)) for provider in PROVIDERS},
        "graph_simulation_read_or_run": False,
        "graph_prediction_read": False,
        "graph_whitebox_read": False,
        "reran_optuna": False,
        "private_phase2_provider_traces_read": False,
        "cost": {
            "screen_candidates": int(len(screen)),
            "confirmation_local_trajectories": int(n_confirmation),
            "replay_local_trajectories": int(n_replay),
            "total_local_trajectories": int(n_confirmation + n_replay),
            "wall_seconds_python": float(elapsed),
            "peak_rss_platform_units": peak_rss,
        },
        "outputs": {
            "screen_candidates": screen_path.name,
            "confirmation_results": confirmation_path.name,
            "compatible_candidates": compatible_path.name,
            "replay_results": "m2_a_replay_results.csv" if gate_pass else None,
        },
        "next_gate": (
            "Freeze these public-I1-compatible candidates before any graph composition. Then run one-at-a-time and predeclared combination graph predictions without consulting graph WB for selection."
            if gate_pass
            else "Stop before graph composition. Revisit the local-I1-only screening/compatibility rule explicitly; do not widen automatically."
        ),
    }
    _write_json(output_root / "m2_a_confirmation_manifest_v1.json", manifest)

    print("\nCONFIRMATION RESULTS")
    print(
        confirmation[
            [
                "provider",
                "candidate_id",
                "selection_role",
                "confirmation_mse",
                "confirmation_mse_ratio_to_best",
                "confirmation_compatible",
            ]
        ].to_string(index=False)
    )
    if gate_pass:
        print("\nREPLAY RESULTS")
        print(
            replay[
                ["provider", "candidate_id", "selection_role", "replay_mse", "replay_mae", "replay_bias"]
            ].to_string(index=False)
        )
        print("M2_A_LOCAL_CONFIRMATION_PASS")
    else:
        print("M2_A_LOCAL_CONFIRMATION_DIVERSITY_GATE_FAIL")
        raise SystemExit(2)

    print(f"output={output_root.resolve()}")


if __name__ == "__main__":
    main()
