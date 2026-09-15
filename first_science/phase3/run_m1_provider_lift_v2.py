"""Execute the Phase-3 M1-v2 direct public-I1 -> native-surrogate lift.

M1-v2 jointly searches (mean service time, cost rate, service CV) against the
complete public provider-local I1 sigma surface. The search consumes only the
frozen public I1 card, W_i, and declared closure conventions. No graph-level
white-box result is read by this runner.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
if str(PHASE2) not in sys.path:
    sys.path.insert(0, str(PHASE2))

from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card  # noqa: E402
from m1_joint_lift_v2 import (  # noqa: E402
    boundary_diagnostics,
    build_search_bounds,
    calculate_full_surface_loss,
)
from m1_single_provider_simulator import simulate_stochastic_sigma_surface  # noqa: E402

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_CONTRACT_STATUS = "IMPLEMENTATION_CANDIDATE_PHASE3_M1_LIFT_V2_NOT_FROZEN"
EXPECTED_I1_MANIFEST_STATUS = "PHASE2_I1_RHO_CONDITIONED_CARD_INSTANCES_V1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(repository_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
        ).strip()
    except Exception:
        return None


def _load_optuna():
    try:
        import optuna
    except ImportError as exc:
        raise RuntimeError(
            "M1-v2 requires Optuna. Install it in the praise-cao environment with "
            "`python -m pip install optuna`."
        ) from exc
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    return optuna


def load_verified_public_i1_cards(
    card_root: Path,
) -> tuple[dict[str, dict[str, object]], dict[str, pd.DataFrame], dict[str, Any]]:
    """Load the exact frozen public cards and verify their materialized hashes."""
    manifest_path = card_root / "i1_rho_conditioned_manifest_v1.json"
    manifest = _read_json(manifest_path)
    if manifest.get("status") != EXPECTED_I1_MANIFEST_STATUS:
        raise ValueError("unexpected rho-conditioned public I1 manifest status")
    cards = manifest.get("cards")
    if not isinstance(cards, dict) or set(cards) != set(PROVIDERS):
        raise ValueError("public I1 manifest must contain ProviderA/B/C")

    metadata_by_provider: dict[str, dict[str, object]] = {}
    surfaces: dict[str, pd.DataFrame] = {}
    for provider in PROVIDERS:
        record = dict(cards[provider])
        directory = card_root / str(record["directory"])
        card_json = directory / "card.json"
        surface_csv = directory / "sigma_surface.csv"
        if _sha256(card_json) != str(record["card_json_sha256"]):
            raise RuntimeError(f"{provider} public card.json hash mismatch")
        if _sha256(surface_csv) != str(record["sigma_surface_sha256"]):
            raise RuntimeError(f"{provider} public sigma surface hash mismatch")
        metadata, surface = load_rho_conditioned_i1_provider_card(directory)
        if str(metadata.get("provider_id")) != provider:
            raise RuntimeError(f"{provider} provider_id mismatch")
        metadata_by_provider[provider] = metadata
        surfaces[provider] = surface
    return metadata_by_provider, surfaces, manifest


def _seed_bank(start: int, count: int) -> tuple[int, ...]:
    if int(count) <= 0:
        raise ValueError("trajectory seed-bank count must be positive")
    return tuple(range(int(start), int(start) + int(count)))


def _effective_budget(contract: dict[str, Any], smoke: bool) -> dict[str, int]:
    optimization = dict(contract["joint_full_surface_lift"]["optimization"])
    calibration = dict(optimization["calibration_common_random_numbers"])
    confirmation = dict(optimization["shortlist_confirmation"])
    replay = dict(optimization["independent_replay"])

    budget = {
        "n_trials": int(optimization["n_trials"]),
        "n_startup_trials": int(optimization["n_startup_trials"]),
        "calibration_n_trajectories": int(calibration["n_trajectories"]),
        "shortlist_top_k": int(confirmation["top_k"]),
        "confirmation_n_trajectories": int(confirmation["n_trajectories"]),
        "independent_replay_n_trajectories": int(replay["n_trajectories"]),
    }
    if smoke:
        smoke_cfg = dict(contract["smoke_mode"])
        for key in budget:
            budget[key] = int(smoke_cfg[key])

    if budget["n_trials"] <= 0:
        raise ValueError("M1-v2 n_trials must be positive")
    if not 0 <= budget["n_startup_trials"] <= budget["n_trials"]:
        raise ValueError("M1-v2 n_startup_trials must lie in [0,n_trials]")
    if not 1 <= budget["shortlist_top_k"] <= budget["n_trials"]:
        raise ValueError("M1-v2 shortlist_top_k must lie in [1,n_trials]")
    return budget


def _simulate_surface(
    *,
    metadata: dict[str, object],
    public_surface: pd.DataFrame,
    mean_service_time: float,
    cost_rate: float,
    service_cv: float,
    trajectory_seeds: Iterable[int],
    canonical_ipt: float,
    execution_fraction: float,
    quiet: bool,
) -> pd.DataFrame:
    kwargs = dict(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=float(mean_service_time),
        cost_rate=float(cost_rate),
        service_cv=float(service_cv),
        trajectory_seeds=tuple(int(seed) for seed in trajectory_seeds),
        canonical_ipt=float(canonical_ipt),
        execution_fraction=float(execution_fraction),
    )
    if not quiet:
        return simulate_stochastic_sigma_surface(**kwargs)

    with open(os.devnull, "w", encoding="utf-8") as devnull:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            return simulate_stochastic_sigma_surface(**kwargs)


def _simulate_and_score(
    *,
    metadata: dict[str, object],
    public_surface: pd.DataFrame,
    mean_service_time: float,
    cost_rate: float,
    service_cv: float,
    trajectory_seeds: Iterable[int],
    canonical_ipt: float,
    execution_fraction: float,
    quiet: bool,
) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    simulated = _simulate_surface(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=mean_service_time,
        cost_rate=cost_rate,
        service_cv=service_cv,
        trajectory_seeds=trajectory_seeds,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        quiet=quiet,
    )
    metrics, comparison = calculate_full_surface_loss(public_surface, simulated)
    return metrics, simulated, comparison


def _study_trial_table(study) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for trial in study.trials:
        if trial.value is None or not trial.params:
            continue
        rows.append(
            {
                "trial_number": int(trial.number),
                "state": str(trial.state.name),
                "search_mse": float(trial.value),
                "mean_service_time": float(trial.params["mean_service_time"]),
                "cost_rate": float(trial.params["cost_rate"]),
                "service_cv": float(trial.params["service_cv"]),
                "search_mae": float(trial.user_attrs.get("mae", np.nan)),
                "search_bias": float(trial.user_attrs.get("bias", np.nan)),
                "search_max_abs_error": float(
                    trial.user_attrs.get("max_abs_error", np.nan)
                ),
                "duration_seconds": (
                    float(trial.duration.total_seconds())
                    if trial.duration is not None
                    else np.nan
                ),
            }
        )
    if not rows:
        raise RuntimeError("M1-v2 optimizer produced no completed trials")
    return pd.DataFrame(rows).sort_values(
        ["search_mse", "trial_number"]
    ).reset_index(drop=True)


def run_joint_lift_for_provider(
    *,
    provider: str,
    metadata: dict[str, object],
    public_surface: pd.DataFrame,
    contract: dict[str, Any],
    output_directory: Path,
    smoke: bool,
    quiet_simulator: bool,
) -> dict[str, Any]:
    """Jointly fit (mu,kappa,CV) to the complete public local I1 sigma surface."""
    optuna = _load_optuna()
    output_directory.mkdir(parents=True, exist_ok=True)

    optimization = dict(contract["joint_full_surface_lift"]["optimization"])
    calibration_cfg = dict(optimization["calibration_common_random_numbers"])
    confirmation_cfg = dict(optimization["shortlist_confirmation"])
    replay_cfg = dict(optimization["independent_replay"])
    budget = _effective_budget(contract, smoke)
    bounds = build_search_bounds(metadata, contract)

    calibration_seeds = _seed_bank(
        int(calibration_cfg["trajectory_seed_start"]),
        budget["calibration_n_trajectories"],
    )
    confirmation_seeds = _seed_bank(
        int(confirmation_cfg["trajectory_seed_start"]),
        budget["confirmation_n_trajectories"],
    )
    replay_seeds = _seed_bank(
        int(replay_cfg["trajectory_seed_start"]),
        budget["independent_replay_n_trajectories"],
    )
    if set(calibration_seeds) & set(confirmation_seeds):
        raise ValueError("M1-v2 calibration and confirmation seed banks overlap")
    if set(calibration_seeds) & set(replay_seeds):
        raise ValueError("M1-v2 calibration and replay seed banks overlap")
    if set(confirmation_seeds) & set(replay_seeds):
        raise ValueError("M1-v2 confirmation and replay seed banks overlap")

    canonical_ipt = float(contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(contract["pilot_scope"]["execution_fraction"])
    sampler_seed = int(optimization["sampler_seed"])

    sampler = optuna.samplers.TPESampler(
        seed=sampler_seed,
        n_startup_trials=budget["n_startup_trials"],
    )
    study = optuna.create_study(direction="minimize", sampler=sampler)

    best_seen = [float("inf")]

    def objective(trial) -> float:
        mu = trial.suggest_float(
            "mean_service_time",
            bounds.mean_service_time_lower,
            bounds.mean_service_time_upper,
            log=True,
        )
        kappa = trial.suggest_float(
            "cost_rate",
            bounds.cost_rate_lower,
            bounds.cost_rate_upper,
            log=True,
        )
        cv = trial.suggest_float(
            "service_cv",
            bounds.service_cv_lower,
            bounds.service_cv_upper,
            log=False,
        )
        metrics, _, _ = _simulate_and_score(
            metadata=metadata,
            public_surface=public_surface,
            mean_service_time=mu,
            cost_rate=kappa,
            service_cv=cv,
            trajectory_seeds=calibration_seeds,
            canonical_ipt=canonical_ipt,
            execution_fraction=execution_fraction,
            quiet=quiet_simulator,
        )
        trial.set_user_attr("mae", float(metrics["mae"]))
        trial.set_user_attr("bias", float(metrics["bias"]))
        trial.set_user_attr("max_abs_error", float(metrics["max_abs_error"]))
        return float(metrics["mse"])

    def report_improvement(_, trial) -> None:
        if trial.value is None:
            return
        value = float(trial.value)
        if value < best_seen[0] - 1e-15:
            best_seen[0] = value
            print(
                f"{provider} M1-v2 search best trial={trial.number} "
                f"mse={value:.8g} mu={trial.params['mean_service_time']:.8g} "
                f"kappa={trial.params['cost_rate']:.8g} "
                f"cv={trial.params['service_cv']:.8g}",
                flush=True,
            )

    study.optimize(
        objective,
        n_trials=budget["n_trials"],
        callbacks=[report_improvement],
        show_progress_bar=False,
    )

    trials = _study_trial_table(study)
    trials.to_csv(output_directory / "m1_v2_search_trials.csv", index=False)
    shortlist = trials.head(budget["shortlist_top_k"]).copy()

    confirmation_rows: list[dict[str, object]] = []
    selected_payload: tuple[
        tuple[float, float, int],
        pd.Series,
        dict[str, float],
        pd.DataFrame,
        pd.DataFrame,
    ] | None = None

    for row in shortlist.itertuples(index=False):
        metrics, simulated, comparison = _simulate_and_score(
            metadata=metadata,
            public_surface=public_surface,
            mean_service_time=float(row.mean_service_time),
            cost_rate=float(row.cost_rate),
            service_cv=float(row.service_cv),
            trajectory_seeds=confirmation_seeds,
            canonical_ipt=canonical_ipt,
            execution_fraction=execution_fraction,
            quiet=quiet_simulator,
        )
        confirmation_rows.append(
            {
                "trial_number": int(row.trial_number),
                "search_mse": float(row.search_mse),
                "mean_service_time": float(row.mean_service_time),
                "cost_rate": float(row.cost_rate),
                "service_cv": float(row.service_cv),
                "confirmation_mse": float(metrics["mse"]),
                "confirmation_rmse": float(metrics["rmse"]),
                "confirmation_mae": float(metrics["mae"]),
                "confirmation_bias": float(metrics["bias"]),
                "confirmation_max_abs_error": float(metrics["max_abs_error"]),
            }
        )
        selection_key = (
            float(metrics["mse"]),
            float(row.search_mse),
            int(row.trial_number),
        )
        if selected_payload is None or selection_key < selected_payload[0]:
            selected_payload = (
                selection_key,
                pd.Series(row._asdict()),
                metrics,
                simulated,
                comparison,
            )

    if selected_payload is None:
        raise RuntimeError("M1-v2 shortlist confirmation produced no candidate")

    confirmation_table = pd.DataFrame(confirmation_rows).sort_values(
        ["confirmation_mse", "search_mse", "trial_number"]
    ).reset_index(drop=True)
    confirmation_table.to_csv(
        output_directory / "m1_v2_shortlist_confirmation.csv", index=False
    )

    _, selected_row, confirmation_metrics, confirmation_surface, confirmation_comparison = (
        selected_payload
    )
    selected_mu = float(selected_row["mean_service_time"])
    selected_kappa = float(selected_row["cost_rate"])
    selected_cv = float(selected_row["service_cv"])
    selected_trial_number = int(selected_row["trial_number"])

    confirmation_surface.to_csv(
        output_directory / "m1_v2_selected_confirmation_sigma_surface.csv",
        index=False,
    )
    confirmation_comparison.to_csv(
        output_directory / "m1_v2_selected_confirmation_comparison.csv",
        index=False,
    )

    replay_metrics, replay_surface, replay_comparison = _simulate_and_score(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=selected_mu,
        cost_rate=selected_kappa,
        service_cv=selected_cv,
        trajectory_seeds=replay_seeds,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        quiet=quiet_simulator,
    )
    replay_surface.to_csv(
        output_directory / "m1_v2_independent_replay_sigma_surface.csv",
        index=False,
    )
    replay_comparison.to_csv(
        output_directory / "m1_v2_independent_replay_comparison.csv",
        index=False,
    )

    boundary = boundary_diagnostics(
        mean_service_time=selected_mu,
        cost_rate=selected_kappa,
        service_cv=selected_cv,
        bounds=bounds,
        boundary_fraction=float(optimization["boundary_fraction"]),
    )
    selected_search_row = trials.loc[
        trials["trial_number"] == selected_trial_number
    ].iloc[0]

    result = {
        "provider_id": provider,
        "status": "M1_V2_JOINT_LOCAL_FIT_COMPLETE_NOT_FROZEN",
        "parameters": {
            "mean_service_time": selected_mu,
            "cost_rate": selected_kappa,
            "service_cv": selected_cv,
        },
        "selected_trial_number": selected_trial_number,
        "optimizer": {
            "method": "Optuna TPESampler",
            "sampler_seed": sampler_seed,
            "n_trials": budget["n_trials"],
            "n_startup_trials": budget["n_startup_trials"],
            "search_bounds": bounds.as_dict(),
            "search_best_trial_number": int(study.best_trial.number),
            "search_best_mse": float(study.best_value),
            "selected_trial_search_mse": float(selected_search_row["search_mse"]),
        },
        "calibration_common_random_numbers": {
            "seed_start": int(calibration_seeds[0]),
            "seed_end_inclusive": int(calibration_seeds[-1]),
            "n_trajectories": len(calibration_seeds),
        },
        "shortlist_confirmation": {
            "top_k": budget["shortlist_top_k"],
            "seed_start": int(confirmation_seeds[0]),
            "seed_end_inclusive": int(confirmation_seeds[-1]),
            "n_trajectories": len(confirmation_seeds),
            "metrics": confirmation_metrics,
        },
        "independent_replay": {
            "used_for_selection": False,
            "seed_start": int(replay_seeds[0]),
            "seed_end_inclusive": int(replay_seeds[-1]),
            "n_trajectories": len(replay_seeds),
            "metrics": replay_metrics,
        },
        "boundary_diagnostics": boundary,
        "workload_period": float(metadata["workload_contract"]["period"]),
        "canonical_IPT": canonical_ipt,
        "pilot_execution_fraction": execution_fraction,
        "smoke_mode": bool(smoke),
        "graph_level_whitebox_used": False,
    }
    _write_json(output_directory / "m1_v2_best.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Directly lift frozen public I1 provider cards into M1-v2 native surrogates"
    )
    parser.add_argument(
        "--card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase3_m1_contract_v2.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m1_provider_lift_v2",
    )
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help="optional single-provider run",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="small TPE/trajectory budget for implementation testing only",
    )
    parser.add_argument(
        "--verbose-simulator",
        action="store_true",
        help="do not suppress repetitive AICon/YAFS per-trajectory output",
    )
    args = parser.parse_args()

    contract_path = args.contract.resolve()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise ValueError("unexpected M1-v2 implementation contract status")

    metadata_by_provider, surfaces, i1_manifest = load_verified_public_i1_cards(
        args.card_root.resolve()
    )
    selected = (args.provider,) if args.provider is not None else PROVIDERS
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {}
    for provider in selected:
        print(f"M1-v2 lifting {provider} ...", flush=True)
        results[provider] = run_joint_lift_for_provider(
            provider=provider,
            metadata=metadata_by_provider[provider],
            public_surface=surfaces[provider],
            contract=contract,
            output_directory=output_root / provider,
            smoke=bool(args.smoke),
            quiet_simulator=not bool(args.verbose_simulator),
        )

    optuna = _load_optuna()
    manifest = {
        "status": "PHASE3_M1_V2_PROVIDER_LIFT_RUN_NOT_FROZEN",
        "providers": list(selected),
        "smoke_mode": bool(args.smoke),
        "contract_path": str(contract_path),
        "contract_sha256": _sha256(contract_path),
        "public_i1_manifest_sha256": _sha256(
            args.card_root.resolve() / "i1_rho_conditioned_manifest_v1.json"
        ),
        "public_i1_same_for_m0_and_m1": bool(
            i1_manifest.get("same_materialized_I1_for_M0_and_M1")
        ),
        "optimizer_package": "optuna",
        "optimizer_version": str(optuna.__version__),
        "results": results,
        "graph_level_whitebox_used": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    _write_json(output_root / "m1_v2_provider_lift_manifest.json", manifest)

    print("PHASE3_M1_V2_PROVIDER_LIFT_RUN_COMPLETE_NOT_FROZEN")
    print("M1_V2_PUBLIC_I1_FIREWALL_PASS")
    print("M1_V2_FULL_SURFACE_JOINT_INVERSE_LIFT_COMPLETE")
    print(f"output={output_root}")


if __name__ == "__main__":
    main()
