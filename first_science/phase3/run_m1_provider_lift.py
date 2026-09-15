"""Execute the staged public-I1 -> native-surrogate M1 provider lift.

This runner mirrors the Phase-3 M0 organization but stops before graph-level
white-box evaluation. It consumes only frozen public rho-conditioned I1 cards,
performs Stage 1 deterministic nominal calibration, then Stage 2 stochastic CV
calibration, and writes auditable local reconstruction artifacts.

No Phase-1 white-box result is read anywhere in this file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
if str(PHASE2) not in sys.path:
    sys.path.insert(0, str(PHASE2))

from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card  # noqa: E402
from m1_single_provider_simulator import (  # noqa: E402
    DEFAULT_CANONICAL_IPT,
    DEFAULT_PILOT_EXECUTION_FRACTION,
    simulate_deterministic_compliance_surface,
    simulate_stochastic_sigma_surface,
)
from m1_surrogate_lift import (  # noqa: E402
    calculate_stage1_nominal_loss,
    calculate_stage2_sigma_loss,
    grid_search_stage1,
    grid_search_stage2,
    infer_median_compliance_targets,
)

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


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


def load_verified_public_i1_cards(
    card_root: Path,
) -> tuple[dict[str, dict[str, object]], dict[str, pd.DataFrame], dict[str, Any]]:
    """Load the exact frozen public cards and verify their materialized hashes."""
    manifest_path = card_root / "i1_rho_conditioned_manifest_v1.json"
    manifest = _read_json(manifest_path)
    if manifest.get("status") != "PHASE2_I1_RHO_CONDITIONED_CARD_INSTANCES_V1":
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


def _public_cost_rate_reference(metadata: dict[str, object]) -> float:
    """Construct only a search scale from public A_i boundaries."""
    regions = metadata.get("rho_conditioned_regions")
    if not isinstance(regions, list) or not regions:
        raise ValueError("public card lacks rho_conditioned_regions")
    ratios = []
    for region_object in regions:
        region = dict(region_object)
        latency = max(float(region["l_max"]), 1e-12)
        cost = float(region["c_max"])
        ratios.append(cost / latency)
    reference = float(np.median(np.asarray(ratios, dtype=float)))
    if not np.isfinite(reference) or reference <= 0.0:
        raise RuntimeError("public A_i boundaries do not define a positive cost-rate scale")
    return reference


def _grid(lower: float, upper: float, points: int) -> np.ndarray:
    if not (np.isfinite(lower) and np.isfinite(upper) and 0.0 <= lower < upper):
        raise ValueError(f"invalid grid bounds [{lower}, {upper}]")
    if int(points) < 2:
        raise ValueError("grid requires at least two points")
    return np.linspace(float(lower), float(upper), int(points), dtype=float)


def _refine_bounds(
    lower: float,
    upper: float,
    best: float,
    fraction: float,
    *,
    nonnegative: bool,
    strictly_positive: bool = False,
) -> tuple[float, float]:
    width = float(upper) - float(lower)
    new_width = width * float(fraction)
    new_lower = float(best) - 0.5 * new_width
    new_upper = float(best) + 0.5 * new_width
    if strictly_positive:
        new_lower = max(new_lower, np.finfo(float).eps)
    elif nonnegative:
        new_lower = max(new_lower, 0.0)
    if new_upper <= new_lower:
        new_upper = new_lower + max(new_width, 1e-12)
    return float(new_lower), float(new_upper)


def _is_on_boundary(value: float, lower: float, upper: float, tolerance: float = 1e-12) -> bool:
    return bool(
        abs(float(value) - float(lower)) <= tolerance
        or abs(float(value) - float(upper)) <= tolerance
    )


def run_stage1_for_provider(
    *,
    provider: str,
    metadata: dict[str, object],
    public_surface: pd.DataFrame,
    contract: dict[str, Any],
    output_directory: Path,
    smoke: bool,
) -> dict[str, Any]:
    """Fit deterministic (mu,kappa) using the public median-compliance targets."""
    stage = dict(contract["stage1_deterministic_nominal_lift"])
    optimization = dict(stage["optimization"])
    targets = infer_median_compliance_targets(public_surface)
    output_directory.mkdir(parents=True, exist_ok=True)
    targets.to_csv(output_directory / "median_compliance_targets.csv", index=False)

    workload = dict(metadata["workload_contract"])
    period = float(workload["period"])
    mu_factor_lower, mu_factor_upper = map(
        float, optimization["mu_over_workload_period_bounds"]
    )
    mu_lower = mu_factor_lower * period
    mu_upper = mu_factor_upper * period

    kappa_reference = _public_cost_rate_reference(metadata)
    kappa_factor_lower, kappa_factor_upper = map(
        float, optimization["cost_rate_reference_multiplier_bounds"]
    )
    kappa_lower = kappa_factor_lower * kappa_reference
    kappa_upper = kappa_factor_upper * kappa_reference

    points = int(optimization["grid_points_per_axis"])
    refinement_rounds = int(optimization["refinement_rounds"])
    refinement_fraction = float(
        optimization["refinement_fraction_of_previous_width"]
    )
    if smoke:
        points = min(points, 5)
        refinement_rounds = 0

    all_candidates: list[pd.DataFrame] = []
    best_mu = np.nan
    best_kappa = np.nan
    best_loss = np.inf
    final_bounds: dict[str, float] = {}

    for round_index in range(refinement_rounds + 1):
        mu_grid = _grid(mu_lower, mu_upper, points)
        kappa_grid = _grid(kappa_lower, kappa_upper, points)

        def evaluator(mu: float, kappa: float) -> pd.DataFrame:
            return simulate_deterministic_compliance_surface(
                metadata=metadata,
                public_surface=public_surface,
                mean_service_time=mu,
                cost_rate=kappa,
                canonical_ipt=float(contract["fixed_closure_conventions"]["canonical_IPT"]),
                execution_fraction=float(contract["pilot_scope"]["execution_fraction"]),
            )

        search = grid_search_stage1(mu_grid, kappa_grid, evaluator, targets)
        round_candidates = search.candidates.copy()
        round_candidates.insert(0, "round", int(round_index))
        all_candidates.append(round_candidates)
        best_mu = float(search.best_parameters["mean_service_time"])
        best_kappa = float(search.best_parameters["cost_rate"])
        best_loss = float(search.best_loss)
        final_bounds = {
            "mu_lower": float(mu_lower),
            "mu_upper": float(mu_upper),
            "kappa_lower": float(kappa_lower),
            "kappa_upper": float(kappa_upper),
        }
        if round_index < refinement_rounds:
            mu_lower, mu_upper = _refine_bounds(
                mu_lower,
                mu_upper,
                best_mu,
                refinement_fraction,
                nonnegative=False,
                strictly_positive=True,
            )
            kappa_lower, kappa_upper = _refine_bounds(
                kappa_lower,
                kappa_upper,
                best_kappa,
                refinement_fraction,
                nonnegative=True,
            )

    candidate_table = pd.concat(all_candidates, ignore_index=True)
    candidate_table.to_csv(output_directory / "stage1_search.csv", index=False)
    best_compliance = simulate_deterministic_compliance_surface(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=best_mu,
        cost_rate=best_kappa,
        canonical_ipt=float(contract["fixed_closure_conventions"]["canonical_IPT"]),
        execution_fraction=float(contract["pilot_scope"]["execution_fraction"]),
    )
    best_loss_check, loss_detail = calculate_stage1_nominal_loss(
        best_compliance, targets
    )
    if abs(best_loss_check - best_loss) > 1e-12:
        raise RuntimeError("Stage-1 best-point loss changed on deterministic replay")
    best_compliance.to_csv(
        output_directory / "stage1_best_compliance.csv", index=False
    )
    loss_detail.to_csv(output_directory / "stage1_best_loss_detail.csv", index=False)

    boundary_hit = bool(
        _is_on_boundary(best_mu, final_bounds["mu_lower"], final_bounds["mu_upper"])
        or _is_on_boundary(
            best_kappa, final_bounds["kappa_lower"], final_bounds["kappa_upper"]
        )
    )
    target_counts = {
        str(key): int(value)
        for key, value in targets["target_kind"].value_counts().to_dict().items()
    }
    result = {
        "provider_id": provider,
        "status": "STAGE1_LOCAL_FIT_COMPLETE_NOT_FROZEN",
        "mean_service_time": best_mu,
        "cost_rate": best_kappa,
        "service_cv": 0.0,
        "loss_mse": best_loss,
        "target_counts": target_counts,
        "search_boundary_hit": boundary_hit,
        "final_search_bounds": final_bounds,
        "workload_period": period,
        "cost_rate_public_reference": kappa_reference,
        "smoke_mode": bool(smoke),
    }
    _write_json(output_directory / "stage1_best.json", result)
    return result


def run_stage2_for_provider(
    *,
    provider: str,
    metadata: dict[str, object],
    public_surface: pd.DataFrame,
    contract: dict[str, Any],
    output_directory: Path,
    stage1_result: dict[str, Any],
    smoke: bool,
) -> dict[str, Any]:
    """Fit only the Gamma service CV while keeping Stage-1 mu/kappa fixed."""
    stage = dict(contract["stage2_stochastic_variability_lift"])
    optimization = dict(stage["optimization"])
    cv_lower, cv_upper = map(float, optimization["cv_bounds"])
    points = int(optimization["grid_points"])
    refinement_rounds = int(optimization["refinement_rounds"])
    refinement_fraction = float(
        optimization["refinement_fraction_of_previous_width"]
    )
    seed_start = int(optimization["trajectory_seed_start"])
    seed_end = int(optimization["trajectory_seed_end_inclusive"])
    seeds = tuple(range(seed_start, seed_end + 1))
    if len(seeds) != int(optimization["n_trajectories"]):
        raise ValueError("M1 Stage-2 seed range does not match n_trajectories")
    if smoke:
        points = min(points, 5)
        refinement_rounds = 0
        seeds = seeds[: min(5, len(seeds))]

    mu = float(stage1_result["mean_service_time"])
    kappa = float(stage1_result["cost_rate"])
    all_candidates: list[pd.DataFrame] = []
    best_cv = np.nan
    best_mse = np.inf
    final_bounds: dict[str, float] = {}

    for round_index in range(refinement_rounds + 1):
        cv_grid = _grid(cv_lower, cv_upper, points)

        def evaluator(cv: float) -> pd.DataFrame:
            return simulate_stochastic_sigma_surface(
                metadata=metadata,
                public_surface=public_surface,
                mean_service_time=mu,
                cost_rate=kappa,
                service_cv=cv,
                trajectory_seeds=seeds,
                canonical_ipt=float(contract["fixed_closure_conventions"]["canonical_IPT"]),
                execution_fraction=float(contract["pilot_scope"]["execution_fraction"]),
            )

        search = grid_search_stage2(cv_grid, evaluator, public_surface)
        round_candidates = search.candidates.copy()
        round_candidates.insert(0, "round", int(round_index))
        all_candidates.append(round_candidates)
        best_cv = float(search.best_parameters["service_cv"])
        best_mse = float(search.best_loss)
        final_bounds = {
            "cv_lower": float(cv_lower),
            "cv_upper": float(cv_upper),
        }
        if round_index < refinement_rounds:
            cv_lower, cv_upper = _refine_bounds(
                cv_lower,
                cv_upper,
                best_cv,
                refinement_fraction,
                nonnegative=True,
            )

    output_directory.mkdir(parents=True, exist_ok=True)
    pd.concat(all_candidates, ignore_index=True).to_csv(
        output_directory / "stage2_search.csv", index=False
    )
    best_surface = simulate_stochastic_sigma_surface(
        metadata=metadata,
        public_surface=public_surface,
        mean_service_time=mu,
        cost_rate=kappa,
        service_cv=best_cv,
        trajectory_seeds=seeds,
        canonical_ipt=float(contract["fixed_closure_conventions"]["canonical_IPT"]),
        execution_fraction=float(contract["pilot_scope"]["execution_fraction"]),
    )
    metrics, comparison = calculate_stage2_sigma_loss(public_surface, best_surface)
    if abs(float(metrics["mse"]) - best_mse) > 1e-12:
        raise RuntimeError("Stage-2 best-point loss changed on common-seed replay")
    best_surface.to_csv(output_directory / "stage2_best_sigma_surface.csv", index=False)
    comparison.to_csv(output_directory / "stage2_best_comparison.csv", index=False)

    boundary_hit = _is_on_boundary(
        best_cv, final_bounds["cv_lower"], final_bounds["cv_upper"]
    )
    result = {
        "provider_id": provider,
        "status": "STAGE2_LOCAL_FIT_COMPLETE_NOT_FROZEN",
        "mean_service_time": mu,
        "cost_rate": kappa,
        "service_cv": best_cv,
        "local_reconstruction": metrics,
        "search_boundary_hit": bool(boundary_hit),
        "final_search_bounds": final_bounds,
        "n_calibration_trajectories": len(seeds),
        "trajectory_seed_start": int(seeds[0]),
        "trajectory_seed_end_inclusive": int(seeds[-1]),
        "smoke_mode": bool(smoke),
    }
    _write_json(output_directory / "stage2_best.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lift frozen public I1 provider cards into M1 native surrogates"
    )
    parser.add_argument(
        "--card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase3_m1_contract_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m1_provider_lift_v1",
    )
    parser.add_argument(
        "--stage",
        choices=("stage1", "stage2", "all"),
        default="all",
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
        help="tiny search/seed budget for implementation smoke testing only",
    )
    args = parser.parse_args()

    contract = _read_json(args.contract.resolve())
    if contract.get("status") != "IMPLEMENTATION_CANDIDATE_PHASE3_M1_LIFT_V1_NOT_FROZEN":
        raise ValueError("unexpected M1 implementation contract status")
    metadata_by_provider, surfaces, i1_manifest = load_verified_public_i1_cards(
        args.card_root.resolve()
    )
    selected = (args.provider,) if args.provider is not None else PROVIDERS
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    stage1_results: dict[str, Any] = {}
    stage2_results: dict[str, Any] = {}
    for provider in selected:
        provider_output = output_root / provider
        if args.stage in ("stage1", "all"):
            stage1_results[provider] = run_stage1_for_provider(
                provider=provider,
                metadata=metadata_by_provider[provider],
                public_surface=surfaces[provider],
                contract=contract,
                output_directory=provider_output,
                smoke=bool(args.smoke),
            )
        else:
            stage1_path = provider_output / "stage1_best.json"
            if not stage1_path.exists():
                raise FileNotFoundError(
                    f"Stage 2 requires an existing Stage-1 result: {stage1_path}"
                )
            stage1_results[provider] = _read_json(stage1_path)

        if args.stage in ("stage2", "all"):
            stage2_results[provider] = run_stage2_for_provider(
                provider=provider,
                metadata=metadata_by_provider[provider],
                public_surface=surfaces[provider],
                contract=contract,
                output_directory=provider_output,
                stage1_result=stage1_results[provider],
                smoke=bool(args.smoke),
            )

    manifest = {
        "status": "PHASE3_M1_PROVIDER_LIFT_RUN_NOT_FROZEN",
        "stage": args.stage,
        "providers": list(selected),
        "smoke_mode": bool(args.smoke),
        "contract_path": str(args.contract.resolve()),
        "contract_sha256": _sha256(args.contract.resolve()),
        "public_i1_manifest_sha256": _sha256(
            args.card_root.resolve() / "i1_rho_conditioned_manifest_v1.json"
        ),
        "public_i1_same_for_m0_and_m1": bool(
            i1_manifest.get("same_materialized_I1_for_M0_and_M1")
        ),
        "canonical_IPT": float(
            contract["fixed_closure_conventions"]["canonical_IPT"]
        ),
        "pilot_execution_fraction": float(contract["pilot_scope"]["execution_fraction"]),
        "stage1_results": stage1_results,
        "stage2_results": stage2_results,
        "graph_level_whitebox_used": False,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    _write_json(output_root / "m1_provider_lift_manifest.json", manifest)

    print("PHASE3_M1_PROVIDER_LIFT_RUN_COMPLETE_NOT_FROZEN")
    print("M1_PUBLIC_I1_FIREWALL_PASS")
    if stage1_results:
        print("M1_STAGE1_DETERMINISTIC_NOMINAL_LIFT_COMPLETE")
    if stage2_results:
        print("M1_STAGE2_STOCHASTIC_VARIABILITY_LIFT_COMPLETE")
    print(f"output={output_root}")


if __name__ == "__main__":
    main()
