#!/usr/bin/env python3
"""Blind M3 dominant-mass weighted graph prediction.

This stage:
- validates the public-I1-selected lambda=V3 weighting products;
- selects the minimal descending joint-weight prefix with cumulative mass >=0.999;
- freezes integer minimax trajectory allocations for B=1400 and B=2000;
- simulates only those retained joint latent hypotheses;
- forms weighted graph-survival predictions for the same frozen 15-query battery.

It never reads or generates graph white-box evidence.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
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
for directory in (PHASE2, PHASE3, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
)
from m0_analytic_composition import AdmissibilityBoundary  # noqa: E402
from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa: E402
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
)
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402
from m2_b5_joint_ensemble_graph import _ledger  # noqa: E402

EXPECTED_STATUS = "FROZEN_PHASE4_M3_V4_DOMINANT_MASS_GRAPH_PREDICTION_V1"
EXPECTED_LAMBDA_STATUS = "FROZEN_PHASE4_M3_V3_PUBLIC_I1_CV_WEIGHTING_COMPLETE"
EXPECTED_STEP0_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_CALIBRATION_PASS_V2"
COMPLETE_STATUS = "FROZEN_PHASE4_M3_V4_DOMINANT_MASS_GRAPH_PREDICTIONS"
TOL = 1e-12


def _query_boundary(rec: pd.Series) -> AdmissibilityBoundary:
    return AdmissibilityBoundary(
        l_max=float(rec["A_G_l_max"]),
        c_max=float(rec["A_G_c_max"]),
        q_min=float(rec["A_G_q_min"]),
    )


def _load_and_validate_inputs(args, contract):
    cfg = dict(contract["inputs"])

    lambda_manifest_path = (HERE / str(cfg["lambda_cv_manifest"])).resolve()
    lambda_manifest = _read_json(lambda_manifest_path)
    if lambda_manifest.get("status") != str(cfg["lambda_cv_manifest_status"]):
        raise RuntimeError("unexpected M3-v3 lambda-CV manifest status")
    if lambda_manifest.get("status") != EXPECTED_LAMBDA_STATUS:
        raise RuntimeError("unexpected M3-v3 lambda status")
    if bool(lambda_manifest.get("graph_simulation")) or bool(lambda_manifest.get("graph_whitebox_read")):
        raise RuntimeError("M3-v3 weighting provenance is not graph-clean")

    weights_path = (HERE / str(cfg["provider_weights"])).resolve()
    weights = pd.read_csv(weights_path)
    if str(lambda_manifest.get("weights_sha256")) != _sha256(weights_path):
        raise RuntimeError("M3-v3 provider weights hash mismatch")

    joint_path = (HERE / str(cfg["joint_mass_audit"])).resolve()
    joint = pd.read_csv(joint_path)
    required_joint = {"rank", "joint_weight", "cumulative_mass", "A", "B", "C"}
    missing = sorted(required_joint.difference(joint.columns))
    if missing:
        raise RuntimeError("M3 joint-mass audit missing: " + ", ".join(missing))
    joint = joint.sort_values("rank").reset_index(drop=True)
    if len(joint) != 48**3:
        raise RuntimeError("M3 joint-mass audit does not contain 48^3 combinations")
    if joint["rank"].astype(int).tolist() != list(range(1, len(joint) + 1)):
        raise RuntimeError("M3 joint-mass ranks are not consecutive")
    if not np.isclose(joint["joint_weight"].astype(float).sum(), 1.0, atol=1e-10):
        raise RuntimeError("M3 joint-mass weights do not sum to one")

    weight_lookup = {
        (str(r.provider), str(r.candidate_id)): r
        for r in weights.itertuples(index=False)
    }
    if len(weight_lookup) != len(weights):
        raise RuntimeError("duplicate provider/candidate IDs in M3 weights")

    for rec in joint.head(50).itertuples(index=False):
        wa = float(weight_lookup[("ProviderA", str(rec.A))].weight_v3)
        wb = float(weight_lookup[("ProviderB", str(rec.B))].weight_v3)
        wc = float(weight_lookup[("ProviderC", str(rec.C))].weight_v3)
        if not np.isclose(float(rec.joint_weight), wa * wb * wc, atol=1e-12, rtol=1e-10):
            raise RuntimeError("joint-mass audit disagrees with provider product weights")

    step0_manifest_path = (HERE / str(cfg["step0_manifest"])).resolve()
    step0_manifest = _read_json(step0_manifest_path)
    if step0_manifest.get("status") != str(cfg["step0_manifest_status"]):
        raise RuntimeError("unexpected Step-0 manifest status")
    if step0_manifest.get("status") != EXPECTED_STEP0_STATUS:
        raise RuntimeError("unexpected frozen query-battery status")

    selected_path = (HERE / str(cfg["selected_regions"])).resolve()
    if str(step0_manifest.get("selected_regions_frozen_sha256")) != _sha256(selected_path):
        raise RuntimeError("frozen query-battery hash mismatch")
    selected = pd.read_csv(selected_path)
    if len(selected) != 15:
        raise RuntimeError("expected exactly 15 frozen sigma-regime queries")

    return (
        lambda_manifest_path,
        lambda_manifest,
        weights_path,
        weights,
        joint_path,
        joint,
        selected_path,
        selected.sort_values(["rho_global", "regime"]).reset_index(drop=True),
        step0_manifest_path,
    )


def _select_dominant_set(joint: pd.DataFrame, contract: dict[str, Any]) -> tuple[pd.DataFrame, float]:
    cfg = dict(contract["dominant_mass"])
    target = float(cfg["target_retained_mass"])
    cum = joint["cumulative_mass"].astype(float).to_numpy()
    idx = int(np.searchsorted(cum, target, side="left"))
    selected = joint.iloc[: idx + 1].copy().reset_index(drop=True)
    expected_n = int(cfg["expected_n_hypotheses_from_frozen_v3"])
    if len(selected) != expected_n:
        raise RuntimeError(
            f"dominant-mass prefix changed: expected {expected_n}, found {len(selected)}"
        )
    retained = float(selected["joint_weight"].astype(float).sum())
    if retained + TOL < target:
        raise RuntimeError("dominant-mass prefix misses target")
    if len(selected) > 1:
        previous = retained - float(selected.iloc[-1]["joint_weight"])
        if previous >= target - TOL:
            raise RuntimeError("dominant-mass prefix is not minimal")
    selected["alpha_renormalized"] = selected["joint_weight"].astype(float) / retained
    selected["omitted_mass"] = 1.0 - retained
    return selected, retained


def _integer_minimax_allocations(alpha: np.ndarray, budgets: list[int]) -> pd.DataFrame:
    alpha = np.asarray(alpha, dtype=float)
    if not np.isclose(alpha.sum(), 1.0, atol=1e-12):
        raise RuntimeError("renormalized dominant weights do not sum to one")
    k = len(alpha)
    budgets = sorted(int(b) for b in budgets)
    if budgets[0] < k:
        raise RuntimeError("graph budget smaller than retained hypothesis count")

    n = np.ones(k, dtype=int)
    snapshots: dict[int, np.ndarray] = {}
    max_budget = budgets[-1]
    if k in budgets:
        snapshots[k] = n.copy()

    for total in range(k + 1, max_budget + 1):
        marginal = alpha * alpha / (n * (n + 1))
        # np.argmax resolves exact ties by lower rank/index.
        j = int(np.argmax(marginal))
        n[j] += 1
        if total in budgets:
            snapshots[total] = n.copy()

    rows = []
    for budget in budgets:
        counts = snapshots[budget]
        var_bound = 0.25 * float(np.sum(alpha * alpha / counts))
        for j, nj in enumerate(counts):
            rows.append(
                {
                    "budget": int(budget),
                    "rank": int(j + 1),
                    "n_trajectories": int(nj),
                    "alpha_renormalized": float(alpha[j]),
                    "worst_case_mc_variance_bound_budget": var_bound,
                    "worst_case_mc_se_bound_budget": float(math.sqrt(var_bound)),
                }
            )
    return pd.DataFrame(rows)


def _build_design(
    dominant: pd.DataFrame,
    weights: pd.DataFrame,
    allocations: pd.DataFrame,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, dict[str, GraphProviderSurrogate]]]:
    lookup = {
        (str(r.provider), str(r.candidate_id)): r
        for r in weights.itertuples(index=False)
    }
    sim = dict(contract["simulation_budget"])
    max_budget = max(int(x) for x in sim["budgets"])
    max_alloc = allocations[allocations["budget"].astype(int) == max_budget].set_index("rank")
    seed_base = int(sim["seed_base"])
    stride = int(sim["seed_block_stride"])

    variants = {}
    rows = []
    for rec in dominant.itertuples(index=False):
        rank = int(rec.rank)
        aid, bid, cid = str(rec.A), str(rec.B), str(rec.C)
        ar = lookup[("ProviderA", aid)]
        br = lookup[("ProviderB", bid)]
        cr = lookup[("ProviderC", cid)]
        variant_id = f"M3Q_R{rank:02d}"
        variants[variant_id] = {
            "ProviderA": GraphProviderSurrogate(
                mean_service_time=float(ar.mean_service_time),
                cost_rate=float(ar.cost_rate),
                service_cv=float(ar.service_cv),
            ),
            "ProviderB": GraphProviderSurrogate(
                mean_service_time=float(br.mean_service_time),
                cost_rate=float(br.cost_rate),
                service_cv=float(br.service_cv),
            ),
            "ProviderC": GraphProviderSurrogate(
                mean_service_time=float(cr.mean_service_time),
                cost_rate=float(cr.cost_rate),
                service_cv=float(cr.service_cv),
            ),
        }
        nmax = int(max_alloc.loc[rank, "n_trajectories"])
        start = seed_base + (rank - 1) * stride
        if nmax >= stride:
            raise RuntimeError("seed block stride too small for allocated trajectories")
        row = {
            "rank": rank,
            "variant_id": variant_id,
            "joint_weight": float(rec.joint_weight),
            "alpha_renormalized": float(rec.alpha_renormalized),
            "cumulative_mass": float(rec.cumulative_mass),
            "ProviderA_candidate_id": aid,
            "ProviderB_candidate_id": bid,
            "ProviderC_candidate_id": cid,
            "max_n_trajectories": nmax,
            "seed_start": start,
            "seed_end_inclusive": start + nmax - 1,
        }
        for budget in sorted(int(x) for x in sim["budgets"]):
            nj = int(
                allocations[
                    (allocations["budget"].astype(int) == budget)
                    & (allocations["rank"].astype(int) == rank)
                ]["n_trajectories"].iloc[0]
            )
            row[f"n_B{budget}"] = nj
        rows.append(row)
    return pd.DataFrame(rows), variants


def _simulate_worker(payload: tuple) -> tuple[str, bool, int]:
    variant_id, surrogates, seeds, graph_spec, workload, ipt, x, path = payload
    ledger, reused = _ledger(
        variant_id=str(variant_id),
        surrogates=surrogates,
        seeds=tuple(int(s) for s in seeds),
        graph_spec=graph_spec,
        workload=workload,
        canonical_ipt=float(ipt),
        execution_fraction=float(x),
        path=Path(path),
    )
    return str(variant_id), bool(reused), int(len(ledger))


def _simulate_all(
    *,
    design: pd.DataFrame,
    variants: dict[str, Any],
    graph_spec: dict[str, Any],
    workload: dict[str, Any],
    canonical_ipt: float,
    execution_fraction: float,
    ledger_dir: Path,
    workers: int,
) -> tuple[int, int]:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for rec in design.itertuples(index=False):
        seeds = tuple(range(int(rec.seed_start), int(rec.seed_end_inclusive) + 1))
        tasks.append(
            (
                str(rec.variant_id),
                variants[str(rec.variant_id)],
                seeds,
                graph_spec,
                workload,
                canonical_ipt,
                execution_fraction,
                str(ledger_dir / f"{rec.variant_id}.csv"),
            )
        )

    if workers <= 1:
        results = [_simulate_worker(t) for t in tasks]
    else:
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_simulate_worker, t): t[0] for t in tasks}
            for fut in concurrent.futures.as_completed(futures):
                variant_id = futures[fut]
                result = fut.result()
                print(f"M3 dominant variant complete: {variant_id}", flush=True)
                results.append(result)

    reused = sum(int(r[1]) for r in results)
    rows = sum(int(r[2]) for r in results)
    return reused, rows


def _member_curves(
    *,
    design: pd.DataFrame,
    allocations: pd.DataFrame,
    selected: pd.DataFrame,
    ledger_dir: Path,
    horizons: list[float],
    workload: dict[str, Any],
    budgets: list[int],
) -> pd.DataFrame:
    rows = []
    design_idx = design.set_index("rank")
    alloc_idx = allocations.set_index(["budget", "rank"])

    for budget in budgets:
        for rank in design["rank"].astype(int):
            rec = design_idx.loc[rank]
            ledger = pd.read_csv(ledger_dir / f"{rec['variant_id']}.csv")
            n = int(alloc_idx.loc[(budget, rank), "n_trajectories"])
            subset = ledger[ledger["trajectory"].astype(int) < n].copy()
            if subset["trajectory"].nunique() != n:
                raise RuntimeError(
                    f"budget={budget} rank={rank}: prefix ledger has wrong trajectory count"
                )
            for _, query in selected.iterrows():
                boundary = _query_boundary(query)
                curve = build_empirical_graph_sigma_curve(
                    subset,
                    boundary=boundary,
                    rho_global=float(query["rho_global"]),
                    horizons=horizons,
                    stop_time=float(workload["horizon_max"]),
                    accounting_origin=float(workload["accounting_origin"]),
                    output_column="sigma_member",
                )
                curve.insert(0, "budget", int(budget))
                curve.insert(1, "rank", int(rank))
                curve.insert(2, "variant_id", str(rec["variant_id"]))
                curve.insert(3, "rho_global", float(query["rho_global"]))
                curve.insert(4, "regime", str(query["regime"]))
                curve["n_trajectories"] = n
                curve["alpha_renormalized"] = float(rec["alpha_renormalized"])
                curve["joint_weight"] = float(rec["joint_weight"])
                curve["scale"] = float(query["scale"])
                curve["A_G_l_max"] = float(boundary.l_max)
                curve["A_G_c_max"] = float(boundary.c_max)
                curve["A_G_q_min"] = float(boundary.q_min)
                rows.append(curve)

    return pd.concat(rows, ignore_index=True).sort_values(
        ["budget", "rank", "rho_global", "regime", "horizon"]
    ).reset_index(drop=True)


def _aggregate_predictions(
    member: pd.DataFrame,
    *,
    retained_mass: float,
    allocations: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    alloc_summary = (
        allocations.groupby("budget", as_index=False)
        .agg(
            worst_case_mc_variance_bound=(
                "worst_case_mc_variance_bound_budget", "first"
            ),
            worst_case_mc_se_bound=("worst_case_mc_se_bound_budget", "first"),
            total_trajectories=("n_trajectories", "sum"),
        )
    )
    alloc_lookup = alloc_summary.set_index("budget")

    for (budget, rho, regime, horizon), g in member.groupby(
        ["budget", "rho_global", "regime", "horizon"], sort=True
    ):
        if g["rank"].nunique() != 14:
            raise RuntimeError("M3 prediction point is missing retained hypotheses")
        w = g["alpha_renormalized"].astype(float).to_numpy()
        x = g["sigma_member"].astype(float).to_numpy()
        if not np.isclose(w.sum(), 1.0, atol=1e-10):
            raise RuntimeError("M3 retained weights do not sum to one")
        mean = float(np.sum(w * x))
        weighted_var = float(np.sum(w * np.square(x - mean)))
        q = g.iloc[0]
        info = alloc_lookup.loc[int(budget)]
        omitted = 1.0 - float(retained_mass)
        rows.append(
            {
                "budget": int(budget),
                "rho_global": float(rho),
                "regime": str(regime),
                "horizon": float(horizon),
                "scale": float(q["scale"]),
                "A_G_l_max": float(q["A_G_l_max"]),
                "A_G_c_max": float(q["A_G_c_max"]),
                "A_G_q_min": float(q["A_G_q_min"]),
                "sigma_m3_dominant": mean,
                "weighted_member_std": float(math.sqrt(max(0.0, weighted_var))),
                "retained_mass": float(retained_mass),
                "omitted_mass": omitted,
                "deterministic_truncation_abs_error_bound": omitted,
                "full_mixture_lower_bound_if_member_curves_exact": float(retained_mass) * mean,
                "full_mixture_upper_bound_if_member_curves_exact": float(retained_mass) * mean + omitted,
                "worst_case_mc_variance_bound": float(info["worst_case_mc_variance_bound"]),
                "worst_case_mc_se_bound": float(info["worst_case_mc_se_bound"]),
                "total_graph_trajectories": int(info["total_trajectories"]),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["budget", "rho_global", "regime", "horizon"]
    ).reset_index(drop=True)


def _ledger_hashes(design: pd.DataFrame, ledger_dir: Path) -> pd.DataFrame:
    rows = []
    for rec in design.itertuples(index=False):
        path = ledger_dir / f"{rec.variant_id}.csv"
        rows.append(
            {
                "rank": int(rec.rank),
                "variant_id": str(rec.variant_id),
                "sha256": _sha256(path),
                "bytes": int(path.stat().st_size),
                "n_trajectories": int(rec.max_n_trajectories),
                "seed_start": int(rec.seed_start),
                "seed_end_inclusive": int(rec.seed_end_inclusive),
            }
        )
    return pd.DataFrame(rows)


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected M3 dominant-mass graph contract status")

    (
        lambda_manifest_path,
        lambda_manifest,
        weights_path,
        weights,
        joint_path,
        joint,
        selected_path,
        selected,
        step0_manifest_path,
    ) = _load_and_validate_inputs(args, contract)

    dominant, retained_mass = _select_dominant_set(joint, contract)
    budgets = sorted(int(x) for x in contract["simulation_budget"]["budgets"])
    allocations = _integer_minimax_allocations(
        dominant["alpha_renormalized"].astype(float).to_numpy(),
        budgets,
    )
    design, variants = _build_design(
        dominant=dominant,
        weights=weights,
        allocations=allocations,
        contract=contract,
    )

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    rho_support = sorted(float(v) for v in common_same_rho_support(metadata))
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)
    selected_rhos = sorted(float(v) for v in selected["rho_global"].unique())
    if not np.allclose(rho_support, selected_rhos, atol=TOL, rtol=0.0):
        raise RuntimeError("M3 query rho support differs from frozen public I1")

    m1_contract = _read_json(args.m1_contract.resolve())
    m0_contract = _read_json(args.m0_contract.resolve())
    graph_spec = dict(m0_contract["phase1_benchmark_adapter"])
    canonical_ipt = float(m1_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(m1_contract["pilot_scope"]["execution_fraction"])

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    design_path = output / "m3_v4_dominant_design.csv"
    allocation_path = output / "m3_v4_allocation_table.csv"
    design.to_csv(design_path, index=False)
    allocations.to_csv(allocation_path, index=False)

    print("M3_V4_DOMINANT_MASS_PREPARE_PASS_NO_WHITEBOX")
    print(
        f"retained_hypotheses={len(dominant)} retained_mass={retained_mass:.9f} "
        f"truncation_bound={1-retained_mass:.9f}"
    )
    print("\nM3_V4_DOMINANT_DESIGN")
    print(
        design[
            [
                "rank",
                "variant_id",
                "joint_weight",
                "alpha_renormalized",
                "ProviderA_candidate_id",
                "ProviderB_candidate_id",
                "ProviderC_candidate_id",
                "n_B1400",
                "n_B2000",
                "seed_start",
                "seed_end_inclusive",
            ]
        ].to_string(index=False)
    )
    print("\nM3_V4_BUDGET_BOUNDS")
    print(
        allocations.groupby("budget", as_index=False)
        .agg(
            total=("n_trajectories", "sum"),
            mc_var_bound=("worst_case_mc_variance_bound_budget", "first"),
            mc_se_bound=("worst_case_mc_se_bound_budget", "first"),
        )
        .to_string(index=False)
    )
    if args.prepare_only:
        print("M3_V4_PREPARE_ONLY_COMPLETE")
        print(f"output={output}")
        return

    ledger_dir = output / "ledgers"
    reused, total_rows = _simulate_all(
        design=design,
        variants=variants,
        graph_spec=graph_spec,
        workload=workload,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        ledger_dir=ledger_dir,
        workers=max(1, int(args.workers)),
    )

    member = _member_curves(
        design=design,
        allocations=allocations,
        selected=selected,
        ledger_dir=ledger_dir,
        horizons=horizons,
        workload=workload,
        budgets=budgets,
    )
    member_path = output / "m3_v4_member_curves.csv"
    member.to_csv(member_path, index=False)

    predictions = _aggregate_predictions(
        member,
        retained_mass=retained_mass,
        allocations=allocations,
    )
    prediction_path = output / "m3_v4_blind_predictions.csv"
    predictions.to_csv(prediction_path, index=False)

    ledger_hash = _ledger_hashes(design, ledger_dir)
    ledger_hash_path = output / "m3_v4_ledger_hashes.csv"
    ledger_hash.to_csv(ledger_hash_path, index=False)

    manifest_path = output / "m3_v4_prediction_manifest.json"
    _write_json(
        manifest_path,
        {
            "status": COMPLETE_STATUS,
            "contract_sha256": _sha256(contract_path),
            "lambda_cv_manifest_sha256": _sha256(lambda_manifest_path),
            "provider_weights_sha256": _sha256(weights_path),
            "joint_mass_audit_sha256": _sha256(joint_path),
            "selected_regions_sha256": _sha256(selected_path),
            "step0_manifest_sha256": _sha256(step0_manifest_path),
            "m1_contract_sha256": _sha256(args.m1_contract.resolve()),
            "m0_contract_sha256": _sha256(args.m0_contract.resolve()),
            "public_i1_manifest_sha256": _sha256(args.i1_manifest.resolve()),
            "dominant_design_sha256": _sha256(design_path),
            "allocation_table_sha256": _sha256(allocation_path),
            "member_curves_sha256": _sha256(member_path),
            "blind_predictions_sha256": _sha256(prediction_path),
            "ledger_hashes_sha256": _sha256(ledger_hash_path),
            "selected_lambda": float(lambda_manifest["selected_lambda"]),
            "n_retained_hypotheses": int(len(dominant)),
            "retained_mass": float(retained_mass),
            "omitted_mass": float(1.0 - retained_mass),
            "budgets": budgets,
            "max_graph_trajectories": int(max(budgets)),
            "checkpoint_reused_variants": int(reused),
            "total_request_rows_loaded_or_generated": int(total_rows),
            "independent_seed_streams_across_hypotheses": True,
            "graph_whitebox_read": False,
            "final_whitebox_generated": False,
            "python_wall_seconds": float(time.perf_counter() - started),
            "git_commit": _git_head(FIRST_SCIENCE.parent),
            "next_gate": contract["next_gate"],
        },
    )

    print("\nM3_V4_PREDICTION_REGIME_MEANS_H60_H240")
    diag = predictions[
        (predictions["horizon"].astype(float) >= 60 - TOL)
        & (predictions["horizon"].astype(float) <= 240 + TOL)
    ]
    print(
        diag.groupby(["budget", "rho_global", "regime"], as_index=False)
        .agg(sigma_m3_mean=("sigma_m3_dominant", "mean"))
        .to_string(index=False)
    )
    print("M3_V4_DOMINANT_MASS_BLIND_PREDICTIONS_FROZEN_PASS")
    print(f"manifest={manifest_path}")
    print(f"python_wall_seconds={time.perf_counter()-started:.3f}")


def main() -> None:
    p = argparse.ArgumentParser(description="M3 dominant-mass blind graph prediction")
    p.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m3_v4_dominant_mass_graph_v1.json",
    )
    p.add_argument(
        "--m1-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m1_contract_v2.json",
    )
    p.add_argument(
        "--m0-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m0_contract_v1.json",
    )
    p.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    p.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m3_v4_dominant_mass_graph_v1",
    )
    p.add_argument("--workers", type=int, default=1)
    stages = p.add_mutually_exclusive_group(required=True)
    stages.add_argument("--prepare-only", action="store_true")
    stages.add_argument("--predict", action="store_true")
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
