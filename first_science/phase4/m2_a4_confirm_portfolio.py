"""Confirm and freeze the M2-A4 diverse public-I1-compatible portfolio.

The provisional portfolio order is frozen by the GP level-set stage before
confirmation. This runner re-evaluates those members on the established
100-trajectory confirmation bank, applies the pre-existing M2-A confirmation
ceiling, takes the first three passing members in the frozen order, and replays
those final members diagnostically. No graph information is read or generated.
"""
from __future__ import annotations

import argparse
import resource
import sys
import time
from pathlib import Path

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
from m2_a_confirm_candidates import _read_json, _seed_bank, _sha256, _write_json  # noqa: E402

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_CONTRACT_STATUS = "PHASE4_M2_A4_GP_LEVELSET_PORTFOLIO_CONTRACT_V1"
EXPECTED_SEARCH_STATUS = "PHASE4_M2_A4_GP_LEVELSET_SEARCH_COMPLETE_V1"
EXPECTED_PREVIOUS_CONFIRM_STATUS = "PHASE4_M2_A_CONFIRMATION_PASS"
TOL = 1e-12


def _evaluate_with_checkpoint(
    *,
    candidates: pd.DataFrame,
    metadata_by_provider: dict[str, dict[str, object]],
    surfaces: dict[str, pd.DataFrame],
    trajectory_seeds: tuple[int, ...],
    canonical_ipt: float,
    execution_fraction: float,
    output_root: Path,
    stage: str,
) -> pd.DataFrame:
    results_path = output_root / f"m2_a4_{stage}_results.csv"
    if results_path.exists():
        results = pd.read_csv(results_path)
        completed = set(results["candidate_id"].astype(str))
        print(f"M2-A4 {stage} resume: {len(completed)} candidates already evaluated", flush=True)
    else:
        results = pd.DataFrame()
        completed: set[str] = set()

    total = len(candidates)
    for ordinal, rec in enumerate(
        candidates.sort_values(["provider", "selection_order"]).itertuples(index=False),
        start=1,
    ):
        candidate_id = str(rec.candidate_id)
        if candidate_id in completed:
            continue
        provider = str(rec.provider)
        print(f"M2-A4 {stage} {ordinal}/{total} {candidate_id}", flush=True)
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
        row = {
            "provider": provider,
            "candidate_id": candidate_id,
            "selection_order": int(rec.selection_order),
            "portfolio_role": str(rec.portfolio_role),
            "source_stage": str(rec.source_stage),
            "mean_service_time": float(rec.mean_service_time),
            "cost_rate": float(rec.cost_rate),
            "service_cv": float(rec.service_cv),
            "z_log_mu": float(rec.z_log_mu),
            "z_log_kappa": float(rec.z_log_kappa),
            "z_cv": float(rec.z_cv),
            "local_search_mse": float(rec.local_mse),
            f"{stage}_mse": float(metrics["mse"]),
            f"{stage}_rmse": float(metrics["rmse"]),
            f"{stage}_mae": float(metrics["mae"]),
            f"{stage}_bias": float(metrics["bias"]),
            f"{stage}_max_abs_error": float(metrics["max_abs_error"]),
        }
        candidate_dir = output_root / f"{stage}_surfaces" / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        simulated.to_csv(candidate_dir / f"{stage}_sigma_surface.csv", index=False)
        comparison.to_csv(candidate_dir / f"{stage}_comparison.csv", index=False)

        results = pd.concat([results, pd.DataFrame([row])], ignore_index=True)
        results = results.drop_duplicates("candidate_id", keep="last").sort_values(
            ["provider", "selection_order"], kind="mergesort"
        )
        results.to_csv(results_path, index=False)
        completed.add(candidate_id)

    return results.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Confirm and freeze the M2-A4 diverse local portfolio"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_a4_gp_levelset_v1.json",
    )
    parser.add_argument(
        "--search-root",
        type=Path,
        default=HERE / "results" / "m2_a4_gp_levelset_v1",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_a4_portfolio_confirmation_v1",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    contract_path = args.contract.resolve()
    search_root = args.search_root.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected M2-A4 contract status")
    firewall = dict(contract["firewall"])
    for forbidden in (
        "rerun_optuna",
        "graph_simulation",
        "graph_prediction_read",
        "graph_whitebox_read",
        "private_phase2_provider_traces_read",
        "hidden_phase1_provider_parameters_read",
        "ppg_gp_performance_prediction_reused",
    ):
        if bool(firewall.get(forbidden)):
            raise RuntimeError(f"M2-A4 firewall unexpectedly allows {forbidden}")

    search_manifest_path = search_root / "m2_a4_search_manifest_v1.json"
    search_manifest = _read_json(search_manifest_path)
    if search_manifest.get("status") != EXPECTED_SEARCH_STATUS:
        raise RuntimeError("unexpected M2-A4 search manifest status")
    for key in (
        "graph_simulation",
        "graph_prediction_read",
        "graph_whitebox_read",
        "private_phase2_provider_traces_read",
        "ppg_gp_performance_prediction_reused",
    ):
        if bool(search_manifest.get(key)):
            raise RuntimeError(f"M2-A4 search provenance violates confirmation assumptions: {key}")

    provisional_path = search_root / "m2_a4_provisional_portfolio.csv"
    provisional = pd.read_csv(provisional_path)
    required = {
        "provider",
        "candidate_id",
        "selection_order",
        "portfolio_role",
        "source_stage",
        "mean_service_time",
        "cost_rate",
        "service_cv",
        "z_log_mu",
        "z_log_kappa",
        "z_cv",
        "local_mse",
    }
    missing = sorted(required.difference(provisional.columns))
    if missing:
        raise ValueError("M2-A4 provisional portfolio missing: " + ", ".join(missing))

    provisional_k = int(contract["provisional_portfolio"]["k_per_provider"])
    counts = provisional.groupby("provider").size().to_dict()
    if any(int(counts.get(p, 0)) != provisional_k for p in PROVIDERS):
        raise RuntimeError("provisional portfolio must contain exactly the frozen K per provider")
    for provider in PROVIDERS:
        orders = sorted(
            provisional[provisional["provider"].astype(str) == provider][
                "selection_order"
            ].astype(int).tolist()
        )
        if orders != list(range(1, provisional_k + 1)):
            raise RuntimeError(f"{provider}: provisional selection order is not 1..K")

    frozen_provisional_path = output_root / "m2_a4_frozen_provisional_portfolio.csv"
    provisional.to_csv(frozen_provisional_path, index=False)
    print("M2_A4_PROVISIONAL_PORTFOLIO_FROZEN_BEFORE_CONFIRMATION_PASS")
    print(
        provisional[
            [
                "provider",
                "selection_order",
                "candidate_id",
                "source_stage",
                "portfolio_role",
                "local_mse",
                "mean_service_time",
                "cost_rate",
                "service_cv",
            ]
        ].to_string(index=False)
    )

    inputs = dict(contract["inputs"])
    previous_manifest_path = (
        HERE / str(inputs["previous_m2a_confirmation_manifest"])
    ).resolve()
    previous_results_path = (
        HERE / str(inputs["previous_m2a_confirmation_results"])
    ).resolve()
    previous_manifest = _read_json(previous_manifest_path)
    if previous_manifest.get("status") != EXPECTED_PREVIOUS_CONFIRM_STATUS:
        raise RuntimeError("unexpected previous M2-A confirmation status")
    if bool(previous_manifest.get("graph_whitebox_read")):
        raise RuntimeError("previous M2-A confirmation unexpectedly read graph WB")

    previous_results = pd.read_csv(previous_results_path)
    previous_best = (
        previous_results.groupby("provider", as_index=False)["confirmation_mse"]
        .min()
        .rename(columns={"confirmation_mse": "previous_best_confirmation_mse"})
    )
    if set(previous_best["provider"].astype(str)) != set(PROVIDERS):
        raise RuntimeError("previous M2-A confirmation reference lacks providers")

    card_root = (HERE / str(inputs["public_i1_root"])).resolve()
    metadata_by_provider, surfaces, public_manifest = load_verified_public_i1_cards(
        card_root
    )
    closure_path = (HERE / str(inputs["pilot_closure_source"])).resolve()
    closure = _read_json(closure_path)
    canonical_ipt = float(closure["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(closure["pilot_scope"]["execution_fraction"])

    confirm_cfg = dict(contract["confirmation"])
    confirm_seeds = _seed_bank(
        int(confirm_cfg["trajectory_seed_start"]),
        int(confirm_cfg["n_trajectories"]),
    )
    confirmation = _evaluate_with_checkpoint(
        candidates=provisional,
        metadata_by_provider=metadata_by_provider,
        surfaces=surfaces,
        trajectory_seeds=confirm_seeds,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        output_root=output_root,
        stage="confirmation",
    )
    confirmation = confirmation.merge(
        previous_best, on="provider", how="left", validate="many_to_one"
    )
    ratio_max = float(
        confirm_cfg["compatibility_ratio_max_to_previous_m2a_best_confirmed"]
    )
    confirmation["frozen_confirmation_mse_ceiling"] = (
        ratio_max * confirmation["previous_best_confirmation_mse"]
    )
    confirmation["confirmation_mse_ratio_to_previous_best"] = (
        confirmation["confirmation_mse"]
        / confirmation["previous_best_confirmation_mse"]
    )
    confirmation["confirmation_compatible"] = (
        confirmation["confirmation_mse"]
        <= confirmation["frozen_confirmation_mse_ceiling"] + TOL
    )
    confirmation = confirmation.sort_values(
        ["provider", "selection_order"], kind="mergesort"
    ).reset_index(drop=True)
    confirmation.to_csv(
        output_root / "m2_a4_confirmation_results.csv", index=False
    )

    final_k = int(confirm_cfg["final_k_per_provider"])
    final_frames: list[pd.DataFrame] = []
    final_counts: dict[str, int] = {}
    for provider in PROVIDERS:
        passing = confirmation[
            (confirmation["provider"].astype(str) == provider)
            & (confirmation["confirmation_compatible"].astype(bool))
        ].sort_values("selection_order", kind="mergesort")
        selected = passing.head(final_k).copy()
        final_counts[provider] = int(len(selected))
        if not selected.empty:
            selected["final_portfolio_order"] = np.arange(
                1, len(selected) + 1, dtype=int
            )
            final_frames.append(selected)

    final = (
        pd.concat(final_frames, ignore_index=True)
        if final_frames
        else pd.DataFrame()
    )
    minimum = int(confirm_cfg["minimum_confirmed_candidates_per_provider"])
    gate_pass = all(
        int(final_counts.get(provider, 0)) >= minimum for provider in PROVIDERS
    )
    final_path = output_root / "m2_a4_final_confirmed_portfolio.csv"
    final.to_csv(final_path, index=False)

    replay = pd.DataFrame()
    if gate_pass:
        replay_cfg = dict(contract["independent_replay"])
        replay_seeds = _seed_bank(
            int(replay_cfg["trajectory_seed_start"]),
            int(replay_cfg["n_trajectories"]),
        )
        replay = _evaluate_with_checkpoint(
            candidates=final,
            metadata_by_provider=metadata_by_provider,
            surfaces=surfaces,
            trajectory_seeds=replay_seeds,
            canonical_ipt=canonical_ipt,
            execution_fraction=execution_fraction,
            output_root=output_root,
            stage="replay",
        )
        replay.to_csv(output_root / "m2_a4_replay_results.csv", index=False)

    elapsed = time.perf_counter() - started
    manifest = {
        "status": (
            "PHASE4_M2_A4_FINAL_PORTFOLIO_PASS_V1"
            if gate_pass
            else "PHASE4_M2_A4_FINAL_PORTFOLIO_GATE_FAIL_V1"
        ),
        "contract_sha256": _sha256(contract_path),
        "search_manifest_sha256": _sha256(search_manifest_path),
        "provisional_portfolio_sha256": _sha256(provisional_path),
        "previous_m2a_confirmation_manifest_sha256": _sha256(
            previous_manifest_path
        ),
        "previous_m2a_confirmation_results_sha256": _sha256(
            previous_results_path
        ),
        "public_i1_manifest_status": public_manifest.get("status"),
        "provisional_counts": {
            provider: int(counts.get(provider, 0)) for provider in PROVIDERS
        },
        "confirmed_compatible_counts": {
            provider: int(
                confirmation[
                    (confirmation["provider"].astype(str) == provider)
                    & (confirmation["confirmation_compatible"].astype(bool))
                ].shape[0]
            )
            for provider in PROVIDERS
        },
        "final_portfolio_counts": {
            provider: int(final_counts.get(provider, 0)) for provider in PROVIDERS
        },
        "confirmation_ratio_max_to_previous_m2a_best": ratio_max,
        "confirmation_seed_start": int(confirm_cfg["trajectory_seed_start"]),
        "confirmation_n_trajectories": int(confirm_cfg["n_trajectories"]),
        "replay_seed_start": int(contract["independent_replay"]["trajectory_seed_start"]),
        "replay_n_trajectories": int(contract["independent_replay"]["n_trajectories"]),
        "reran_optuna": False,
        "graph_simulation": False,
        "graph_prediction_read": False,
        "graph_whitebox_read": False,
        "private_phase2_provider_traces_read": False,
        "ppg_gp_performance_prediction_reused": False,
        "python_wall_seconds": float(elapsed),
        "peak_rss_platform_units": int(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        ),
        "outputs": {
            "frozen_provisional_portfolio": frozen_provisional_path.name,
            "confirmation_results": "m2_a4_confirmation_results.csv",
            "final_confirmed_portfolio": final_path.name,
            "replay_results": (
                "m2_a4_replay_results.csv" if gate_pass else None
            ),
            "confirmation_surfaces": "confirmation_surfaces/<candidate_id>/",
            "replay_surfaces": "replay_surfaces/<candidate_id>/",
        },
        "next_gate": (
            "Final M2-A4 three-per-provider portfolio is frozen. Design graph composition "
            "using this portfolio without graph-WB-informed candidate selection."
            if gate_pass
            else "Stop before graph composition. Do not add more candidates, change the "
            "level-set ceiling, or alter the confirmation rule automatically."
        ),
    }
    _write_json(
        output_root / "m2_a4_portfolio_confirmation_manifest_v1.json",
        manifest,
    )

    print("\nM2_A4_CONFIRMATION_RESULTS")
    print(
        confirmation[
            [
                "provider",
                "selection_order",
                "candidate_id",
                "source_stage",
                "confirmation_mse",
                "previous_best_confirmation_mse",
                "frozen_confirmation_mse_ceiling",
                "confirmation_mse_ratio_to_previous_best",
                "confirmation_compatible",
            ]
        ].to_string(index=False)
    )
    if gate_pass:
        print("\nM2_A4_FINAL_CONFIRMED_PORTFOLIO")
        print(
            final[
                [
                    "provider",
                    "final_portfolio_order",
                    "selection_order",
                    "candidate_id",
                    "source_stage",
                    "confirmation_mse",
                    "mean_service_time",
                    "cost_rate",
                    "service_cv",
                ]
            ].to_string(index=False)
        )
        print("\nM2_A4_REPLAY_RESULTS")
        print(
            replay[
                [
                    "provider",
                    "candidate_id",
                    "replay_mse",
                    "replay_mae",
                    "replay_bias",
                ]
            ].to_string(index=False)
        )
        print("M2_A4_FINAL_PORTFOLIO_PASS")
    else:
        print("M2_A4_FINAL_PORTFOLIO_GATE_FAIL")
        raise SystemExit(2)

    print(f"output={output_root}")


if __name__ == "__main__":
    main()
