"""Run M2-A4: GP level-set search followed by diverse portfolio extraction.

This stage addresses the failure mode exposed by M2-A2/A3: the original TPE
search can miss remote, high-quality public-I1-compatible regions. It warm-starts
an ARD Matérn-5/2 Gaussian process with all existing 25-trajectory TPE and LHS
observations measured on the original M1 search seed bank, then sequentially
queries a frozen Sobol candidate pool with a straddle level-set acquisition.

Only actually evaluated points can enter the provisional portfolio. No graph
simulation, graph prediction, graph white-box result, private provider trace, or
PPG GP mechanism is read or reused here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
for module_directory in (PHASE2, PHASE3):
    if str(module_directory) not in sys.path:
        sys.path.insert(0, str(module_directory))

from m1_joint_lift_v2 import build_search_bounds  # noqa: E402
from run_m1_provider_lift_v2 import (  # noqa: E402
    _simulate_and_score,
    load_verified_public_i1_cards,
)

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_STATUS = "PHASE4_M2_A4_GP_LEVELSET_PORTFOLIO_CONTRACT_V1"
EXPECTED_A2_STATUS = "PHASE4_M2_A2_NONADAPTIVE_COVERAGE_AUDIT_COMPLETE_V1"
EXPECTED_LANDSCAPE_STATUS = "PHASE4_M2_A_LOCAL_LANDSCAPE_INSPECTION_V1"
TOL = 1e-12


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_head(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        return None


def _seed_bank(start: int, n: int) -> tuple[int, ...]:
    return tuple(range(int(start), int(start) + int(n)))


def _load_gp_dependencies():
    try:
        from scipy.spatial import cKDTree
        from scipy.stats import qmc
        from sklearn.exceptions import ConvergenceWarning
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
    except ImportError as exc:
        raise RuntimeError(
            "M2-A4 requires scipy and scikit-learn for the GP level-set search. "
            "Install them in the praise-cao environment, e.g. "
            "`python -m pip install scipy scikit-learn`."
        ) from exc
    return (
        cKDTree,
        qmc,
        ConvergenceWarning,
        GaussianProcessRegressor,
        ConstantKernel,
        Matern,
        WhiteKernel,
    )


def _unit_to_parameters(unit: np.ndarray, bounds) -> tuple[float, float, float]:
    x = np.asarray(unit, dtype=float)
    if x.shape != (3,):
        raise ValueError("unit coordinate must have shape (3,)")
    log_mu_lo = math.log(float(bounds.mean_service_time_lower))
    log_mu_hi = math.log(float(bounds.mean_service_time_upper))
    log_k_lo = math.log(float(bounds.cost_rate_lower))
    log_k_hi = math.log(float(bounds.cost_rate_upper))
    cv_lo = float(bounds.service_cv_lower)
    cv_hi = float(bounds.service_cv_upper)
    mu = math.exp(log_mu_lo + float(x[0]) * (log_mu_hi - log_mu_lo))
    kappa = math.exp(log_k_lo + float(x[1]) * (log_k_hi - log_k_lo))
    cv = cv_lo + float(x[2]) * (cv_hi - cv_lo)
    return float(mu), float(kappa), float(cv)


def _make_sobol_pool(
    *, provider_index: int, power: int, seed: int, qmc_module
) -> np.ndarray:
    sampler = qmc_module.Sobol(
        d=3,
        scramble=True,
        seed=int(seed) + int(provider_index) * 100003,
    )
    pool = np.asarray(sampler.random_base2(m=int(power)), dtype=float)
    if pool.shape != (2 ** int(power), 3):
        raise RuntimeError("unexpected Sobol pool shape")
    if np.any(pool < 0.0) or np.any(pool > 1.0):
        raise RuntimeError("Sobol pool escaped unit cube")
    return pool


def _build_pool_table(
    *, contract: dict[str, Any], bounds_by_provider: dict[str, Any], qmc_module
) -> pd.DataFrame:
    pool_cfg = dict(contract["acquisition"]["candidate_pool"])
    power = int(pool_cfg["sobol_power"])
    declared_n = int(pool_cfg["points_per_provider"])
    if 2**power != declared_n:
        raise ValueError("Sobol power does not match declared points_per_provider")
    seed = int(pool_cfg["seed"])
    frames: list[pd.DataFrame] = []
    for provider_index, provider in enumerate(PROVIDERS):
        unit = _make_sobol_pool(
            provider_index=provider_index,
            power=power,
            seed=seed,
            qmc_module=qmc_module,
        )
        params = [_unit_to_parameters(row, bounds_by_provider[provider]) for row in unit]
        frame = pd.DataFrame(
            {
                "provider": provider,
                "pool_index": np.arange(len(unit), dtype=int),
                "z_log_mu": unit[:, 0],
                "z_log_kappa": unit[:, 1],
                "z_cv": unit[:, 2],
                "mean_service_time": [p[0] for p in params],
                "cost_rate": [p[1] for p in params],
                "service_cv": [p[2] for p in params],
            }
        )
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _warm_start_table(existing: pd.DataFrame, lhs: pd.DataFrame) -> pd.DataFrame:
    required_existing = {
        "provider",
        "trial_number",
        "source_relpath",
        "z_log_mu",
        "z_log_kappa",
        "z_cv",
        "mean_service_time",
        "cost_rate",
        "service_cv",
        "search_mse",
    }
    missing = sorted(required_existing.difference(existing.columns))
    if missing:
        raise ValueError("existing landscape missing columns: " + ", ".join(missing))

    tpe = existing[list(required_existing)].copy()
    tpe["source_stage"] = "TPE"
    tpe["candidate_id"] = [
        f"{str(r.provider)}_TPE_{'expanded' if 'expanded' in str(r.source_relpath) else 'base'}_trial{int(r.trial_number):03d}"
        for r in tpe.itertuples(index=False)
    ]
    tpe["local_mse"] = tpe["search_mse"].astype(float)
    tpe = tpe[
        [
            "provider",
            "candidate_id",
            "source_stage",
            "z_log_mu",
            "z_log_kappa",
            "z_cv",
            "mean_service_time",
            "cost_rate",
            "service_cv",
            "local_mse",
        ]
    ]

    required_lhs = {
        "provider",
        "candidate_id",
        "z_log_mu",
        "z_log_kappa",
        "z_cv",
        "mean_service_time",
        "cost_rate",
        "service_cv",
        "lhs_mse",
    }
    missing = sorted(required_lhs.difference(lhs.columns))
    if missing:
        raise ValueError("M2-A2 LHS results missing columns: " + ", ".join(missing))
    lhs2 = lhs[list(required_lhs)].copy()
    lhs2["source_stage"] = "LHS"
    lhs2["local_mse"] = lhs2["lhs_mse"].astype(float)
    lhs2 = lhs2[
        [
            "provider",
            "candidate_id",
            "source_stage",
            "z_log_mu",
            "z_log_kappa",
            "z_cv",
            "mean_service_time",
            "cost_rate",
            "service_cv",
            "local_mse",
        ]
    ]

    warm = pd.concat([tpe, lhs2], ignore_index=True)
    for col in ("z_log_mu", "z_log_kappa", "z_cv"):
        warm[col] = warm[col].astype(float)

    warm["_theta_key"] = warm.apply(
        lambda row: "|".join(
            format(float(row[c]), ".14g")
            for c in ("z_log_mu", "z_log_kappa", "z_cv")
        ),
        axis=1,
    )
    warm = warm.sort_values(
        ["provider", "_theta_key", "local_mse", "source_stage", "candidate_id"],
        kind="mergesort",
    ).drop_duplicates(["provider", "_theta_key"], keep="first")
    return warm.drop(columns="_theta_key").reset_index(drop=True)


def _build_gp(contract: dict[str, Any], iteration_seed: int, deps):
    (
        _,
        _,
        ConvergenceWarning,
        GaussianProcessRegressor,
        ConstantKernel,
        Matern,
        WhiteKernel,
    ) = deps
    cfg = dict(contract["gp_model"])
    c_bounds = tuple(float(v) for v in cfg["constant_bounds"])
    ls_bounds = tuple(float(v) for v in cfg["length_scale_bounds"])
    w_bounds = tuple(float(v) for v in cfg["white_noise_bounds"])
    kernel = (
        ConstantKernel(1.0, constant_value_bounds=c_bounds)
        * Matern(
            length_scale=np.asarray(cfg["initial_length_scale"], dtype=float),
            length_scale_bounds=ls_bounds,
            nu=2.5,
        )
        + WhiteKernel(noise_level=1e-3, noise_level_bounds=w_bounds)
    )
    gp = GaussianProcessRegressor(
        kernel=kernel,
        alpha=float(cfg["alpha_jitter"]),
        normalize_y=bool(cfg["normalize_y"]),
        n_restarts_optimizer=int(cfg["n_restarts_optimizer"]),
        random_state=int(iteration_seed),
    )
    return gp, ConvergenceWarning


def _load_thresholds(geometry: pd.DataFrame) -> dict[str, float]:
    required = {"provider", "compatibility_mse_ceiling"}
    missing = sorted(required.difference(geometry.columns))
    if missing:
        raise ValueError("M2-A2 geometry missing columns: " + ", ".join(missing))
    thresholds: dict[str, float] = {}
    for provider in PROVIDERS:
        rows = geometry[geometry["provider"].astype(str) == provider]
        if len(rows) != 1:
            raise RuntimeError(f"{provider}: expected one M2-A2 geometry row")
        thresholds[provider] = float(rows.iloc[0]["compatibility_mse_ceiling"])
    return thresholds


def _observed_for_provider(
    provider: str, warm: pd.DataFrame, acquisitions: pd.DataFrame
) -> pd.DataFrame:
    frames = [warm[warm["provider"].astype(str) == provider].copy()]
    if not acquisitions.empty:
        gp = acquisitions[acquisitions["provider"].astype(str) == provider].copy()
        if not gp.empty:
            gp2 = gp[
                [
                    "provider",
                    "candidate_id",
                    "source_stage",
                    "z_log_mu",
                    "z_log_kappa",
                    "z_cv",
                    "mean_service_time",
                    "cost_rate",
                    "service_cv",
                    "local_mse",
                ]
            ].copy()
            frames.append(gp2)
    observed = pd.concat(frames, ignore_index=True)
    observed = observed.drop_duplicates("candidate_id", keep="last")
    return observed.reset_index(drop=True)


def _evaluate_gp_search(
    *,
    contract: dict[str, Any],
    warm: pd.DataFrame,
    pool_table: pd.DataFrame,
    thresholds: dict[str, float],
    metadata_by_provider: dict[str, dict[str, object]],
    surfaces: dict[str, pd.DataFrame],
    trajectory_seeds: tuple[int, ...],
    canonical_ipt: float,
    execution_fraction: float,
    output_root: Path,
    deps,
) -> pd.DataFrame:
    cKDTree = deps[0]
    acq_cfg = dict(contract["acquisition"])
    pool_cfg = dict(acq_cfg["candidate_pool"])
    beta = float(acq_cfg["beta_sigma"])
    duplicate_tol = float(pool_cfg["exclude_nearest_observed_distance_leq"])
    n_new = int(contract["search_budget"]["new_evaluations_per_provider"])
    base_gp_seed = int(contract["gp_model"]["random_seed"])

    results_path = output_root / "m2_a4_gp_acquisitions.csv"
    if results_path.exists():
        acquisitions = pd.read_csv(results_path)
        print(f"M2-A4 resume: {len(acquisitions)} acquisitions already evaluated", flush=True)
    else:
        acquisitions = pd.DataFrame()

    for provider_index, provider in enumerate(PROVIDERS):
        existing_provider = (
            acquisitions[acquisitions["provider"].astype(str) == provider].copy()
            if not acquisitions.empty
            else pd.DataFrame()
        )
        if not existing_provider.empty:
            iterations = sorted(existing_provider["gp_iteration"].astype(int).tolist())
            expected = list(range(len(iterations)))
            if iterations != expected:
                raise RuntimeError(
                    f"{provider}: existing GP iterations are not a contiguous prefix"
                )

        provider_pool = pool_table[
            pool_table["provider"].astype(str) == provider
        ].sort_values("pool_index").reset_index(drop=True)
        pool_x = provider_pool[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(float)

        for gp_iteration in range(len(existing_provider), n_new):
            observed = _observed_for_provider(provider, warm, acquisitions)
            x_train = observed[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(float)
            y_train = observed["local_mse"].to_numpy(float)
            if len(x_train) < 4:
                raise RuntimeError(f"{provider}: insufficient GP warm-start observations")

            gp_seed = base_gp_seed + provider_index * 100003 + gp_iteration
            gp, convergence_warning = _build_gp(contract, gp_seed, deps)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", convergence_warning)
                gp.fit(x_train, y_train)

            tree = cKDTree(x_train)
            nearest, _ = tree.query(pool_x, k=1)
            eligible = nearest > duplicate_tol

            if not acquisitions.empty:
                used = acquisitions[
                    acquisitions["provider"].astype(str) == provider
                ]["pool_index"].astype(int).to_numpy()
                if len(used):
                    eligible[used] = False

            eligible_indices = np.flatnonzero(eligible)
            if len(eligible_indices) == 0:
                raise RuntimeError(f"{provider}: Sobol acquisition pool exhausted")
            mean, std = gp.predict(pool_x[eligible_indices], return_std=True)
            epsilon = float(thresholds[provider])
            acquisition = beta * std - np.abs(mean - epsilon)
            local_choice = int(np.argmax(acquisition))
            pool_index = int(eligible_indices[local_choice])
            row = provider_pool.iloc[pool_index]

            candidate_id = f"{provider}_GP_{gp_iteration:03d}"
            print(
                f"M2-A4 {provider} {gp_iteration + 1}/{n_new} {candidate_id} "
                f"pool={pool_index} pred={float(mean[local_choice]):.8g} "
                f"std={float(std[local_choice]):.8g} "
                f"straddle={float(acquisition[local_choice]):.8g}",
                flush=True,
            )

            metrics, simulated, comparison = _simulate_and_score(
                metadata=metadata_by_provider[provider],
                public_surface=surfaces[provider],
                mean_service_time=float(row["mean_service_time"]),
                cost_rate=float(row["cost_rate"]),
                service_cv=float(row["service_cv"]),
                trajectory_seeds=trajectory_seeds,
                canonical_ipt=float(canonical_ipt),
                execution_fraction=float(execution_fraction),
                quiet=True,
            )
            mse = float(metrics["mse"])
            result = {
                "provider": provider,
                "candidate_id": candidate_id,
                "source_stage": "GP_LSE",
                "gp_iteration": int(gp_iteration),
                "pool_index": pool_index,
                "z_log_mu": float(row["z_log_mu"]),
                "z_log_kappa": float(row["z_log_kappa"]),
                "z_cv": float(row["z_cv"]),
                "mean_service_time": float(row["mean_service_time"]),
                "cost_rate": float(row["cost_rate"]),
                "service_cv": float(row["service_cv"]),
                "posterior_mean_before_eval": float(mean[local_choice]),
                "posterior_std_before_eval": float(std[local_choice]),
                "straddle_acquisition": float(acquisition[local_choice]),
                "compatibility_mse_ceiling": epsilon,
                "local_mse": mse,
                "local_rmse": float(metrics["rmse"]),
                "local_mae": float(metrics["mae"]),
                "local_bias": float(metrics["bias"]),
                "local_max_abs_error": float(metrics["max_abs_error"]),
                "local_compatible": bool(mse <= epsilon + TOL),
                "gp_kernel_after_fit": str(gp.kernel_),
            }

            candidate_dir = output_root / "gp_surfaces" / candidate_id
            candidate_dir.mkdir(parents=True, exist_ok=True)
            simulated.to_csv(candidate_dir / "gp_sigma_surface.csv", index=False)
            comparison.to_csv(candidate_dir / "gp_comparison.csv", index=False)

            acquisitions = pd.concat(
                [acquisitions, pd.DataFrame([result])], ignore_index=True
            )
            acquisitions = acquisitions.drop_duplicates(
                ["provider", "gp_iteration"], keep="last"
            ).sort_values(["provider", "gp_iteration"], kind="mergesort")
            acquisitions.to_csv(results_path, index=False)

    return acquisitions.reset_index(drop=True)


def _max_pairwise_distance(coords: np.ndarray) -> float:
    if len(coords) <= 1:
        return 0.0
    best = 0.0
    for i in range(len(coords) - 1):
        d = np.linalg.norm(coords[i + 1 :] - coords[i], axis=1)
        if len(d):
            best = max(best, float(np.max(d)))
    return best


def _extract_provisional_portfolio(
    *,
    contract: dict[str, Any],
    warm: pd.DataFrame,
    acquisitions: pd.DataFrame,
    thresholds: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    k = int(contract["provisional_portfolio"]["k_per_provider"])
    rows: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []

    for provider in PROVIDERS:
        observed = _observed_for_provider(provider, warm, acquisitions)
        epsilon = float(thresholds[provider])
        compatible = observed[observed["local_mse"].astype(float) <= epsilon + TOL].copy()
        compatible = compatible.sort_values(
            ["local_mse", "candidate_id"], kind="mergesort"
        ).reset_index(drop=True)
        if compatible.empty:
            raise RuntimeError(f"{provider}: no observed points in frozen level set")

        chosen_indices = [0]
        min_distances = [np.nan]
        coords = compatible[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(float)
        while len(chosen_indices) < min(k, len(compatible)):
            remaining = [idx for idx in range(len(compatible)) if idx not in chosen_indices]
            candidates: list[tuple[float, float, str, int]] = []
            for idx in remaining:
                min_d = min(
                    float(np.linalg.norm(coords[idx] - coords[j]))
                    for j in chosen_indices
                )
                candidates.append(
                    (
                        -min_d,
                        float(compatible.iloc[idx]["local_mse"]),
                        str(compatible.iloc[idx]["candidate_id"]),
                        idx,
                    )
                )
            candidates.sort()
            chosen = candidates[0][-1]
            chosen_indices.append(chosen)
            min_distances.append(-candidates[0][0])

        selected = compatible.iloc[chosen_indices].copy().reset_index(drop=True)
        selected.insert(0, "selection_order", np.arange(1, len(selected) + 1, dtype=int))
        selected["portfolio_role"] = [
            "BEST_LOCAL_LOSS" if i == 0 else f"DIVERSE_{i}"
            for i in range(len(selected))
        ]
        selected["min_distance_to_previous_portfolio"] = min_distances
        selected["compatibility_mse_ceiling"] = epsilon
        selected["loss_ratio_to_ceiling"] = (
            selected["local_mse"].astype(float) / epsilon
        )
        rows.append(selected)

        compatible_coords = compatible[
            ["z_log_mu", "z_log_kappa", "z_cv"]
        ].to_numpy(float)
        gp_provider = acquisitions[
            acquisitions["provider"].astype(str) == provider
        ].copy()
        summaries.append(
            {
                "provider": provider,
                "n_warm_observations": int(
                    len(warm[warm["provider"].astype(str) == provider])
                ),
                "n_gp_evaluations": int(len(gp_provider)),
                "n_gp_compatible": int(
                    gp_provider["local_compatible"].astype(bool).sum()
                    if not gp_provider.empty
                    else 0
                ),
                "n_observed_compatible_union": int(len(compatible)),
                "frozen_compatibility_mse_ceiling": epsilon,
                "best_observed_local_mse": float(compatible["local_mse"].min()),
                "compatible_union_max_pairwise_distance": _max_pairwise_distance(
                    compatible_coords
                ),
                "provisional_portfolio_size": int(len(selected)),
            }
        )

    return (
        pd.concat(rows, ignore_index=True),
        pd.DataFrame(summaries),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run M2-A4 GP level-set search and diverse portfolio extraction"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_a4_gp_levelset_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_a4_gp_levelset_v1",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Validate inputs, freeze Sobol pool, and print warm-start geometry without simulations.",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    contract_path = args.contract.resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
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

    deps = _load_gp_dependencies()
    qmc_module = deps[1]

    inputs = dict(contract["inputs"])
    existing_path = (HERE / str(inputs["existing_tpe_landscape"])).resolve()
    landscape_manifest_path = (HERE / str(inputs["existing_landscape_manifest"])).resolve()
    a2_manifest_path = (HERE / str(inputs["a2_manifest"])).resolve()
    lhs_results_path = (HERE / str(inputs["a2_lhs_results"])).resolve()
    geometry_path = (HERE / str(inputs["a2_existing_geometry"])).resolve()

    landscape_manifest = _read_json(landscape_manifest_path)
    if landscape_manifest.get("status") != EXPECTED_LANDSCAPE_STATUS:
        raise RuntimeError("unexpected M2-A landscape status")
    a2_manifest = _read_json(a2_manifest_path)
    if a2_manifest.get("status") != EXPECTED_A2_STATUS:
        raise RuntimeError("unexpected M2-A2 manifest status")
    for key in ("sampler_adaptive", "graph_simulation", "graph_prediction_read", "graph_whitebox_read"):
        if bool(a2_manifest.get(key)):
            raise RuntimeError(f"M2-A2 provenance violates M2-A4 assumptions: {key}")

    existing = pd.read_csv(existing_path)
    lhs = pd.read_csv(lhs_results_path)
    geometry = pd.read_csv(geometry_path)
    warm = _warm_start_table(existing, lhs)
    thresholds = _load_thresholds(geometry)

    card_root = (HERE / str(inputs["public_i1_root"])).resolve()
    metadata_by_provider, surfaces, public_manifest = load_verified_public_i1_cards(
        card_root
    )
    base_contract_path = (
        HERE / str(contract["search_space"]["bounds_source_A_B"])
    ).resolve()
    c_contract_path = (
        HERE / str(contract["search_space"]["bounds_source_C"])
    ).resolve()
    base_contract = _read_json(base_contract_path)
    c_contract = _read_json(c_contract_path)
    bounds_by_provider = {
        provider: build_search_bounds(
            metadata_by_provider[provider],
            c_contract if provider == "ProviderC" else base_contract,
        )
        for provider in PROVIDERS
    }

    pool_table = _build_pool_table(
        contract=contract,
        bounds_by_provider=bounds_by_provider,
        qmc_module=qmc_module,
    )
    pool_path = output_root / "m2_a4_sobol_pool.csv"
    if pool_path.exists():
        previous_hash = _sha256(pool_path)
        candidate_bytes = pool_table.to_csv(index=False).encode("utf-8")
        candidate_hash = hashlib.sha256(candidate_bytes).hexdigest()
        if previous_hash != candidate_hash:
            raise RuntimeError("existing M2-A4 Sobol pool differs from frozen deterministic design")
    else:
        pool_table.to_csv(pool_path, index=False)

    warm_path = output_root / "m2_a4_warm_start_observations.csv"
    warm.to_csv(warm_path, index=False)

    warm_summary = []
    for provider in PROVIDERS:
        p = warm[warm["provider"].astype(str) == provider]
        eps = float(thresholds[provider])
        warm_summary.append(
            {
                "provider": provider,
                "n_warm_observations": int(len(p)),
                "n_warm_compatible": int((p["local_mse"].astype(float) <= eps + TOL).sum()),
                "best_warm_local_mse": float(p["local_mse"].min()),
                "frozen_compatibility_mse_ceiling": eps,
            }
        )
    warm_summary_df = pd.DataFrame(warm_summary)
    warm_summary_df.to_csv(output_root / "m2_a4_warm_start_summary.csv", index=False)

    print("M2_A4_GP_LEVELSET_DESIGN_FROZEN_PASS")
    print(warm_summary_df.to_string(index=False))
    print(f"sobol_pool_sha256={_sha256(pool_path)}")

    if args.prepare_only:
        print("M2_A4_PREPARE_ONLY_COMPLETE")
        print(f"output={output_root}")
        return

    closure_path = (HERE / str(inputs["pilot_closure_source"])).resolve()
    closure = _read_json(closure_path)
    canonical_ipt = float(closure["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(closure["pilot_scope"]["execution_fraction"])

    search_cfg = dict(contract["search_budget"])
    trajectory_seeds = _seed_bank(
        int(search_cfg["trajectory_seed_start"]),
        int(search_cfg["n_trajectories_per_evaluation"]),
    )

    acquisitions = _evaluate_gp_search(
        contract=contract,
        warm=warm,
        pool_table=pool_table,
        thresholds=thresholds,
        metadata_by_provider=metadata_by_provider,
        surfaces=surfaces,
        trajectory_seeds=trajectory_seeds,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        output_root=output_root,
        deps=deps,
    )

    provisional, summary = _extract_provisional_portfolio(
        contract=contract,
        warm=warm,
        acquisitions=acquisitions,
        thresholds=thresholds,
    )
    provisional_path = output_root / "m2_a4_provisional_portfolio.csv"
    summary_path = output_root / "m2_a4_levelset_summary.csv"
    provisional.to_csv(provisional_path, index=False)
    summary.to_csv(summary_path, index=False)

    n_expected = int(search_cfg["new_evaluations_per_provider"]) * len(PROVIDERS)
    if len(acquisitions) != n_expected:
        raise RuntimeError(
            f"M2-A4 expected {n_expected} completed acquisitions, found {len(acquisitions)}"
        )
    provisional_k = int(contract["provisional_portfolio"]["k_per_provider"])
    counts = provisional.groupby("provider").size().to_dict()
    if any(int(counts.get(p, 0)) < provisional_k for p in PROVIDERS):
        raise RuntimeError(
            "M2-A4 did not find enough observed compatible points for the frozen provisional portfolio size"
        )

    elapsed = time.perf_counter() - started
    manifest = {
        "status": "PHASE4_M2_A4_GP_LEVELSET_SEARCH_COMPLETE_V1",
        "contract_sha256": _sha256(contract_path),
        "landscape_manifest_sha256": _sha256(landscape_manifest_path),
        "a2_manifest_sha256": _sha256(a2_manifest_path),
        "existing_tpe_landscape_sha256": _sha256(existing_path),
        "a2_lhs_results_sha256": _sha256(lhs_results_path),
        "a2_existing_geometry_sha256": _sha256(geometry_path),
        "public_i1_manifest_status": public_manifest.get("status"),
        "warm_start_observations": int(len(warm)),
        "new_gp_evaluations": int(len(acquisitions)),
        "new_gp_evaluations_per_provider": int(search_cfg["new_evaluations_per_provider"]),
        "local_trajectories_per_new_evaluation": int(
            search_cfg["n_trajectories_per_evaluation"]
        ),
        "total_new_local_trajectories": int(
            len(acquisitions) * int(search_cfg["n_trajectories_per_evaluation"])
        ),
        "sobol_pool_sha256": _sha256(pool_path),
        "frozen_level_set_ceilings": {
            provider: float(thresholds[provider]) for provider in PROVIDERS
        },
        "provisional_portfolio_counts": {
            provider: int(counts.get(provider, 0)) for provider in PROVIDERS
        },
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
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "sobol_pool": pool_path.name,
            "warm_start_observations": warm_path.name,
            "gp_acquisitions": "m2_a4_gp_acquisitions.csv",
            "provisional_portfolio": provisional_path.name,
            "levelset_summary": summary_path.name,
            "gp_surfaces": "gp_surfaces/<candidate_id>/",
        },
        "next_gate": (
            "Confirm the five precomputed provisional portfolio members per provider "
            "on the frozen 23000..23099 local bank. Do not run M2-B2 or any new graph "
            "composition before the final three-per-provider portfolio is frozen."
        ),
    }
    _write_json(output_root / "m2_a4_search_manifest_v1.json", manifest)

    print("\nM2_A4_LEVELSET_SUMMARY")
    print(summary.to_string(index=False))
    print("\nM2_A4_PROVISIONAL_PORTFOLIO")
    print(
        provisional[
            [
                "provider",
                "selection_order",
                "candidate_id",
                "source_stage",
                "portfolio_role",
                "local_mse",
                "compatibility_mse_ceiling",
                "min_distance_to_previous_portfolio",
                "mean_service_time",
                "cost_rate",
                "service_cv",
            ]
        ].to_string(index=False)
    )
    print("M2_A4_GP_LEVELSET_SEARCH_COMPLETE")
    print(f"output={output_root}")


if __name__ == "__main__":
    main()
