#!/usr/bin/env python3
"""Cost-matched Stage-B mechanism ablation for the closed M3 pilot.

Post-hoc explanatory experiment. It does not alter M3, the public I1 cards,
the retained support, lambda, queries, or the frozen white-box reference.

At total graph budget B=1400 it compares:
  Top1-1400
  Uniform14-EQ-1400
  Weighted14-EQ-1400
against the already frozen Weighted14-MINIMAX-1400 production result.

Uniform14 and Weighted14-EQ use exactly the same 14 x 100 CRN ledgers.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import subprocess
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

from diagnose_rho_conditioned_i1_m0 import load_rho_conditioned_i1_cards  # noqa: E402
from m0_analytic_composition import AdmissibilityBoundary  # noqa: E402
from m1_graph_simulator_v2 import GraphProviderSurrogate  # noqa: E402
from run_m1_graph_prediction_v2 import _common_workload_contract, build_empirical_graph_sigma_curve  # noqa: E402
from m2_b5_joint_ensemble_graph import _ledger  # noqa: E402
from sla_compliance_analysis import SlaComplianceDefinition, calculate_empirical_sla_sigma_from_ledgers  # noqa: E402

EXPECTED_STATUS = "FROZEN_PHASE4_M3_POSTHOC_STAGE_B_COST_MATCHED_ABLATION_V1"
COMPLETE_STATUS = "PHASE4_M3_POSTHOC_STAGE_B_COST_MATCHED_ABLATION_COMPLETE_V1"
TOL = 1e-10
Z975 = 1.959963984540054


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


def _git_head(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        return None


def _wilson_interval(p: float, n: int) -> tuple[float, float]:
    x = int(round(float(p) * int(n)))
    phat = float(x / n)
    z2 = Z975 * Z975
    den = 1.0 + z2 / n
    centre = (phat + z2 / (2.0 * n)) / den
    half = Z975 * math.sqrt(
        phat * (1.0 - phat) / n + z2 / (4.0 * n * n)
    ) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def _validate_firewall(contract: dict[str, Any]) -> None:
    fw = dict(contract["firewall"])
    if not bool(fw.get("new_graph_simulation")):
        raise RuntimeError("Stage B must explicitly authorize graph simulation")
    for key, value in fw.items():
        if key == "new_graph_simulation":
            continue
        if key == "PPG_firewall_preserved":
            if not bool(value):
                raise RuntimeError("PPG firewall must remain preserved")
        elif bool(value):
            raise RuntimeError(f"Stage-B contract unexpectedly allows {key}")


def _query_boundary(rec: pd.Series) -> AdmissibilityBoundary:
    return AdmissibilityBoundary(
        l_max=float(rec["A_G_l_max"]),
        c_max=float(rec["A_G_c_max"]),
        q_min=float(rec["A_G_q_min"]),
    )


def _build_variants(weights: pd.DataFrame, design: pd.DataFrame) -> dict[int, dict[str, GraphProviderSurrogate]]:
    lookup = {
        (str(r.provider), str(r.candidate_id)): r
        for r in weights.itertuples(index=False)
    }
    out: dict[int, dict[str, GraphProviderSurrogate]] = {}
    for rec in design.sort_values("rank").itertuples(index=False):
        rank = int(rec.rank)
        a = lookup[("ProviderA", str(rec.ProviderA_candidate_id))]
        b = lookup[("ProviderB", str(rec.ProviderB_candidate_id))]
        c = lookup[("ProviderC", str(rec.ProviderC_candidate_id))]
        out[rank] = {
            "ProviderA": GraphProviderSurrogate(
                mean_service_time=float(a.mean_service_time),
                cost_rate=float(a.cost_rate),
                service_cv=float(a.service_cv),
            ),
            "ProviderB": GraphProviderSurrogate(
                mean_service_time=float(b.mean_service_time),
                cost_rate=float(b.cost_rate),
                service_cv=float(b.service_cv),
            ),
            "ProviderC": GraphProviderSurrogate(
                mean_service_time=float(c.mean_service_time),
                cost_rate=float(c.cost_rate),
                service_cv=float(c.service_cv),
            ),
        }
    if sorted(out) != list(range(1, 15)):
        raise RuntimeError("expected frozen retained ranks 1..14")
    return out


def _simulation_design(design: pd.DataFrame, contract: dict[str, Any]) -> pd.DataFrame:
    seed_cfg = dict(contract["seed_design"])
    base = int(seed_cfg["seed_base"])
    rows = []
    for rec in design.sort_values("rank").itertuples(index=False):
        rank = int(rec.rank)
        nmax = 1400 if rank == 1 else 100
        rows.append(
            {
                "rank": rank,
                "variant_id": f"M3ABL_R{rank:02d}",
                "alpha_renormalized": float(rec.alpha_renormalized),
                "joint_weight": float(rec.joint_weight),
                "ProviderA_candidate_id": str(rec.ProviderA_candidate_id),
                "ProviderB_candidate_id": str(rec.ProviderB_candidate_id),
                "ProviderC_candidate_id": str(rec.ProviderC_candidate_id),
                "n_equal_support": 100,
                "n_top1_full": 1400 if rank == 1 else 0,
                "n_simulated": nmax,
                "seed_start": base,
                "seed_end_inclusive": base + nmax - 1,
            }
        )
    out = pd.DataFrame(rows)
    if not np.isclose(out["alpha_renormalized"].sum(), 1.0, atol=1e-12):
        raise RuntimeError("frozen retained alpha does not sum to one")
    return out


def _simulate_worker(payload: tuple) -> tuple[int, bool, int]:
    (
        rank, variant_id, surrogates, seeds, graph_spec, workload,
        canonical_ipt, execution_fraction, path,
    ) = payload
    ledger, reused = _ledger(
        variant_id=str(variant_id),
        surrogates=surrogates,
        seeds=tuple(int(x) for x in seeds),
        graph_spec=graph_spec,
        workload=workload,
        canonical_ipt=float(canonical_ipt),
        execution_fraction=float(execution_fraction),
        path=Path(path),
    )
    return int(rank), bool(reused), int(len(ledger))


def _simulate_all(
    sim_design: pd.DataFrame,
    variants: dict[int, dict[str, GraphProviderSurrogate]],
    *,
    graph_spec: dict[str, Any],
    workload: dict[str, Any],
    canonical_ipt: float,
    execution_fraction: float,
    ledger_dir: Path,
    workers: int,
) -> tuple[int, int]:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for rec in sim_design.itertuples(index=False):
        seeds = tuple(range(int(rec.seed_start), int(rec.seed_end_inclusive) + 1))
        tasks.append(
            (
                int(rec.rank),
                str(rec.variant_id),
                variants[int(rec.rank)],
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
                result = fut.result()
                print(f"Stage-B graph variant complete: rank={result[0]}", flush=True)
                results.append(result)
    return sum(int(x[1]) for x in results), sum(int(x[2]) for x in results)


def _member_curves(
    sim_design: pd.DataFrame,
    comparison: pd.DataFrame,
    ledger_dir: Path,
    workload: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    queries = (
        comparison[
            ["rho_global", "regime", "A_G_l_max", "A_G_c_max", "A_G_q_min"]
        ]
        .drop_duplicates()
        .sort_values(["rho_global", "regime"])
        .reset_index(drop=True)
    )
    horizons = sorted(comparison["horizon"].astype(float).unique())
    rows = []
    top1_rows = []
    for rec in sim_design.sort_values("rank").itertuples(index=False):
        ledger = pd.read_csv(ledger_dir / f"{rec.variant_id}.csv")
        eq = ledger[ledger["trajectory"].astype(int) < 100].copy()
        if eq["trajectory"].nunique() != 100:
            raise RuntimeError(f"rank {rec.rank}: missing equal-support trajectories")
        for _, query in queries.iterrows():
            boundary = _query_boundary(query)
            curve = build_empirical_graph_sigma_curve(
                eq,
                boundary=boundary,
                rho_global=float(query["rho_global"]),
                horizons=horizons,
                stop_time=float(workload["horizon_max"]),
                accounting_origin=float(workload["accounting_origin"]),
                output_column="sigma_member_eq100",
            )
            curve.insert(0, "rank", int(rec.rank))
            curve.insert(1, "variant_id", str(rec.variant_id))
            curve.insert(2, "rho_global", float(query["rho_global"]))
            curve.insert(3, "regime", str(query["regime"]))
            curve["alpha_renormalized"] = float(rec.alpha_renormalized)
            curve["n_trajectories"] = 100
            rows.append(curve)

            if int(rec.rank) == 1:
                curve_top = build_empirical_graph_sigma_curve(
                    ledger,
                    boundary=boundary,
                    rho_global=float(query["rho_global"]),
                    horizons=horizons,
                    stop_time=float(workload["horizon_max"]),
                    accounting_origin=float(workload["accounting_origin"]),
                    output_column="sigma_top1_1400",
                )
                curve_top.insert(0, "rho_global", float(query["rho_global"]))
                curve_top.insert(1, "regime", str(query["regime"]))
                curve_top["n_trajectories"] = 1400
                top1_rows.append(curve_top)
    return (
        pd.concat(rows, ignore_index=True).sort_values(
            ["rank", "rho_global", "regime", "horizon"]
        ).reset_index(drop=True),
        pd.concat(top1_rows, ignore_index=True).sort_values(
            ["rho_global", "regime", "horizon"]
        ).reset_index(drop=True),
    )


def _aggregate_predictions(
    member: pd.DataFrame,
    top1: pd.DataFrame,
    comparison: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for key, g in member.groupby(["rho_global", "regime", "horizon"], sort=True):
        g = g.sort_values("rank")
        if g["rank"].nunique() != 14:
            raise RuntimeError(f"{key}: incomplete equal-support member set")
        x = g["sigma_member_eq100"].astype(float).to_numpy()
        w = g["alpha_renormalized"].astype(float).to_numpy()
        rows.append(
            {
                "rho_global": float(key[0]),
                "regime": str(key[1]),
                "horizon": float(key[2]),
                "sigma_uniform14_eq1400": float(np.mean(x)),
                "sigma_weighted14_eq1400": float(np.sum(w * x)),
            }
        )
    out = pd.DataFrame(rows)
    out = out.merge(
        top1[["rho_global", "regime", "horizon", "sigma_top1_1400"]],
        on=["rho_global", "regime", "horizon"],
        how="left",
        validate="one_to_one",
    )
    refcols = [
        "rho_global", "regime", "horizon",
        "sigma_m3_B1400", "sigma_whitebox",
    ]
    out = out.merge(
        comparison[refcols],
        on=["rho_global", "regime", "horizon"],
        how="left",
        validate="one_to_one",
    )
    out = out.rename(columns={"sigma_m3_B1400": "sigma_weighted14_minimax1400"})
    if out.isna().any().any():
        raise RuntimeError("Stage-B prediction merge produced missing values")
    return out.sort_values(["rho_global", "regime", "horizon"]).reset_index(drop=True)


def _error_metrics(pred: pd.DataFrame) -> pd.DataFrame:
    methods = {
        "TOP1_1400": "sigma_top1_1400",
        "UNIFORM14_EQ_1400": "sigma_uniform14_eq1400",
        "WEIGHTED14_EQ_1400": "sigma_weighted14_eq1400",
        "WEIGHTED14_MINIMAX_1400": "sigma_weighted14_minimax1400",
    }
    rows = []
    scopes = [("ALL", pred)]
    scopes += [(r, pred[pred["regime"].astype(str) == r]) for r in sorted(pred["regime"].unique())]
    for scope, frame in scopes:
        wb = frame["sigma_whitebox"].astype(float).to_numpy()
        for method, col in methods.items():
            y = frame[col].astype(float).to_numpy()
            e = y - wb
            rows.append(
                {
                    "scope": scope,
                    "method": method,
                    "n_points": int(len(frame)),
                    "mae": float(np.mean(np.abs(e))),
                    "rmse": float(np.sqrt(np.mean(np.square(e)))),
                    "bias": float(np.mean(e)),
                    "max_abs_error": float(np.max(np.abs(e))),
                }
            )
    return pd.DataFrame(rows)


def _decision_metrics(pred: pd.DataFrame, contract: dict[str, Any]) -> pd.DataFrame:
    cfg = dict(contract["analysis_window"])
    betas = [float(x) for x in cfg["decision_thresholds_beta"]]
    n_wb = int(cfg["whitebox_reference_n"])
    methods = {
        "TOP1_1400": "sigma_top1_1400",
        "UNIFORM14_EQ_1400": "sigma_uniform14_eq1400",
        "WEIGHTED14_EQ_1400": "sigma_weighted14_eq1400",
        "WEIGHTED14_MINIMAX_1400": "sigma_weighted14_minimax1400",
    }
    wb = pred["sigma_whitebox"].astype(float).to_numpy()
    rows = []
    for beta in betas:
        intervals = [_wilson_interval(float(p), n_wb) for p in wb]
        certain = np.asarray([(lo >= beta) or (hi < beta) for lo, hi in intervals])
        ref = wb >= beta
        for method, col in methods.items():
            y = pred[col].astype(float).to_numpy()
            pa = y >= beta
            for subset, mask in (
                ("all_reference_points", np.ones(len(pred), dtype=bool)),
                ("wb_wilson95_certain_only", certain),
            ):
                p = pa[mask]
                r = ref[mask]
                rows.append(
                    {
                        "beta": beta,
                        "method": method,
                        "subset": subset,
                        "n_evaluated": int(mask.sum()),
                        "decision_agreement_rate": float(np.mean(p == r)),
                        "decision_disagreement_rate": float(np.mean(p != r)),
                        "false_accept_count": int(np.sum(p & ~r)),
                        "false_reject_count": int(np.sum(~p & r)),
                    }
                )
    return pd.DataFrame(rows)


def _trajectory_matrix(
    ledger: pd.DataFrame,
    queries: pd.DataFrame,
    horizons: list[float],
    workload: dict[str, Any],
) -> np.ndarray:
    trajectory_ids = sorted(ledger["trajectory"].astype(int).unique())
    if trajectory_ids != list(range(len(trajectory_ids))):
        raise RuntimeError("trajectory IDs are not contiguous 0..N-1")
    blocks = []
    for _, query in queries.iterrows():
        boundary = _query_boundary(query)
        definition = SlaComplianceDefinition(
            rho=float(query["rho_global"]),
            accounting_origin=float(workload["accounting_origin"]),
            zero_decision_compliance=1.0,
        )
        _, trajectory_curves, _ = calculate_empirical_sla_sigma_from_ledgers(
            ledger,
            latency_threshold=float(boundary.l_max),
            cost_threshold=float(boundary.c_max),
            quality_threshold=float(boundary.q_min),
            horizons=horizons,
            stop_time=float(workload["horizon_max"]),
            sla_definition=definition,
        )
        pivot = (
            trajectory_curves
            .pivot(index="trajectory", columns="horizon", values="sla_compliant")
            .reindex(index=trajectory_ids, columns=horizons)
        )
        if pivot.isna().any().any():
            raise RuntimeError("incomplete trajectory outcome matrix")
        blocks.append(pivot.astype(float).to_numpy())
    return np.concatenate(blocks, axis=1)


def _bootstrap(
    sim_design: pd.DataFrame,
    design: pd.DataFrame,
    comparison: pd.DataFrame,
    ledger_dir: Path,
    workload: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = dict(contract["analysis_window"])
    reps = int(cfg["bootstrap_reps"])
    seed = int(cfg["bootstrap_seed"])
    queries = (
        comparison[
            ["rho_global", "regime", "A_G_l_max", "A_G_c_max", "A_G_q_min"]
        ]
        .drop_duplicates()
        .sort_values(["rho_global", "regime"])
        .reset_index(drop=True)
    )
    horizons = sorted(comparison["horizon"].astype(float).unique())
    expected_points = len(queries) * len(horizons)
    ref = comparison.sort_values(["rho_global", "regime", "horizon"])[
        "sigma_whitebox"
    ].astype(float).to_numpy()
    if len(ref) != expected_points:
        raise RuntimeError("comparison point order/size mismatch")

    matrices = []
    top1_full = None
    for rec in sim_design.sort_values("rank").itertuples(index=False):
        ledger = pd.read_csv(ledger_dir / f"{rec.variant_id}.csv")
        if int(rec.rank) == 1:
            top1_full = _trajectory_matrix(ledger, queries, horizons, workload)
            eqledger = ledger[ledger["trajectory"].astype(int) < 100].copy()
        else:
            eqledger = ledger
        matrices.append(_trajectory_matrix(eqledger, queries, horizons, workload))
    if top1_full is None or top1_full.shape != (1400, expected_points):
        raise RuntimeError("top1 full bootstrap matrix has wrong shape")
    stack = np.stack(matrices, axis=0)
    if stack.shape != (14, 100, expected_points):
        raise RuntimeError(f"equal-support bootstrap stack has wrong shape {stack.shape}")

    alpha = design.sort_values("rank")["alpha_renormalized"].astype(float).to_numpy()
    uniform_seed = np.mean(stack, axis=0)
    weighted_seed = np.tensordot(alpha, stack, axes=(0, 0))

    rng = np.random.default_rng(seed)
    records = []
    batch = 250
    done = 0
    while done < reps:
        b = min(batch, reps - done)
        counts_eq = rng.multinomial(100, np.full(100, 0.01), size=b).astype(float)
        counts_top = rng.multinomial(
            1400, np.full(1400, 1.0 / 1400.0), size=b
        ).astype(float)
        pred_u = counts_eq @ uniform_seed / 100.0
        pred_w = counts_eq @ weighted_seed / 100.0
        pred_t = counts_top @ top1_full / 1400.0
        mae_u = np.mean(np.abs(pred_u - ref[None, :]), axis=1)
        mae_w = np.mean(np.abs(pred_w - ref[None, :]), axis=1)
        mae_t = np.mean(np.abs(pred_t - ref[None, :]), axis=1)
        for k in range(b):
            records.append(
                {
                    "replicate": done + k,
                    "mae_top1_1400": float(mae_t[k]),
                    "mae_uniform14_eq1400": float(mae_u[k]),
                    "mae_weighted14_eq1400": float(mae_w[k]),
                    "delta_weighted_minus_uniform": float(mae_w[k] - mae_u[k]),
                    "delta_weighted_minus_top1": float(mae_w[k] - mae_t[k]),
                }
            )
        done += b
    boot = pd.DataFrame(records)

    summaries = []
    for col in [
        "mae_top1_1400",
        "mae_uniform14_eq1400",
        "mae_weighted14_eq1400",
        "delta_weighted_minus_uniform",
        "delta_weighted_minus_top1",
    ]:
        x = boot[col].astype(float).to_numpy()
        summaries.append(
            {
                "quantity": col,
                "mean": float(np.mean(x)),
                "median": float(np.median(x)),
                "p2_5": float(np.quantile(x, 0.025)),
                "p97_5": float(np.quantile(x, 0.975)),
                "p_less_than_zero": float(np.mean(x < 0.0)),
                "bootstrap_role": (
                    "paired shared-seed bootstrap"
                    if col == "delta_weighted_minus_uniform"
                    else "graph-MC diagnostic; WB fixed"
                ),
            }
        )
    return boot, pd.DataFrame(summaries)


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected Stage-B contract status")
    _validate_firewall(contract)

    inp = {k: (HERE / str(v)).resolve() for k, v in dict(contract["inputs"]).items()}
    for key, path in inp.items():
        if not path.exists():
            raise FileNotFoundError(f"missing required local input {key}: {path}")

    weights = pd.read_csv(inp["m3_provider_weights"])
    design = pd.read_csv(inp["m3_dominant_design"]).sort_values("rank").reset_index(drop=True)
    comparison_all = pd.read_csv(inp["final_comparison"])
    selected = pd.read_csv(inp["selected_regions"])

    if len(design) != 14 or design["rank"].astype(int).tolist() != list(range(1, 15)):
        raise RuntimeError("Stage B requires exactly the frozen top-14 support")
    if not np.isclose(design["alpha_renormalized"].astype(float).sum(), 1.0, atol=1e-12):
        raise RuntimeError("retained weights do not sum to one")
    if len(selected) != 15:
        raise RuntimeError("frozen query battery must contain 15 cells")

    cfg = dict(contract["analysis_window"])
    comparison = comparison_all[
        (comparison_all["horizon"].astype(float) >= float(cfg["horizon_min"]) - TOL)
        & (comparison_all["horizon"].astype(float) <= float(cfg["horizon_max"]) + TOL)
    ].copy().sort_values(["rho_global", "regime", "horizon"]).reset_index(drop=True)

    sim_design = _simulation_design(design, contract)
    variants = _build_variants(weights, design)

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    workload = _common_workload_contract(metadata)
    m1_contract = _read_json(inp["m1_contract"])
    m0_contract = _read_json(inp["m0_contract"])
    graph_spec = dict(m0_contract["phase1_benchmark_adapter"])
    canonical_ipt = float(m1_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(m1_contract["pilot_scope"]["execution_fraction"])

    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    design_path = out / "stage_b_design.csv"
    sim_design.to_csv(design_path, index=False)

    print("M3_STAGE_B_PREPARE_PASS")
    print(sim_design.to_string(index=False))
    print(
        "New graph trajectories required: "
        f"{int(sim_design['n_simulated'].sum())} "
        "(Top1 1400 plus 13 additional members x100; Top1 first100 reused in ensemble)"
    )
    if args.prepare_only:
        print("M3_STAGE_B_PREPARE_ONLY_COMPLETE")
        return

    ledger_dir = out / "ledgers"
    reused, rows_loaded = _simulate_all(
        sim_design,
        variants,
        graph_spec=graph_spec,
        workload=workload,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        ledger_dir=ledger_dir,
        workers=max(1, int(args.workers)),
    )

    member, top1 = _member_curves(sim_design, comparison, ledger_dir, workload)
    member_path = out / "stage_b_member_curves.csv"
    member.to_csv(member_path, index=False)

    pred = _aggregate_predictions(member, top1, comparison)
    pred_path = out / "stage_b_predictions.csv"
    pred.to_csv(pred_path, index=False)

    metrics = _error_metrics(pred)
    metrics_path = out / "stage_b_error_metrics.csv"
    metrics.to_csv(metrics_path, index=False)

    decisions = _decision_metrics(pred, contract)
    decisions_path = out / "stage_b_decision_metrics.csv"
    decisions.to_csv(decisions_path, index=False)

    boot, boot_summary = _bootstrap(
        sim_design, design, comparison, ledger_dir, workload, contract
    )
    boot_path = out / "stage_b_bootstrap_mae.csv"
    boot_summary_path = out / "stage_b_bootstrap_summary.csv"
    boot.to_csv(boot_path, index=False)
    boot_summary.to_csv(boot_summary_path, index=False)

    ledger_hashes = []
    for rec in sim_design.itertuples(index=False):
        p = ledger_dir / f"{rec.variant_id}.csv"
        ledger_hashes.append(
            {
                "rank": int(rec.rank),
                "variant_id": str(rec.variant_id),
                "n_trajectories": int(rec.n_simulated),
                "sha256": _sha256(p),
            }
        )
    ledger_hash_path = out / "stage_b_ledger_hashes.csv"
    pd.DataFrame(ledger_hashes).to_csv(ledger_hash_path, index=False)

    manifest_path = out / "stage_b_manifest.json"
    _write_json(
        manifest_path,
        {
            "status": COMPLETE_STATUS,
            "classification": str(contract["classification"]),
            "contract_sha256": _sha256(contract_path),
            "design_sha256": _sha256(design_path),
            "member_curves_sha256": _sha256(member_path),
            "predictions_sha256": _sha256(pred_path),
            "error_metrics_sha256": _sha256(metrics_path),
            "decision_metrics_sha256": _sha256(decisions_path),
            "bootstrap_mae_sha256": _sha256(boot_path),
            "bootstrap_summary_sha256": _sha256(boot_summary_path),
            "ledger_hashes_sha256": _sha256(ledger_hash_path),
            "new_graph_trajectories": int(sim_design["n_simulated"].sum()),
            "checkpoint_reused_variants": int(reused),
            "request_rows_loaded_or_generated": int(rows_loaded),
            "new_provider_simulation": False,
            "new_whitebox_simulation": False,
            "lambda_changed": False,
            "support_changed": False,
            "weights_changed": False,
            "queries_changed": False,
            "git_commit": _git_head(FIRST_SCIENCE.parent),
            "python_wall_seconds": float(time.perf_counter() - started),
            "stop_rule": str(contract["stop_rule"]),
        },
    )

    print("\nM3_STAGE_B_ERROR_METRICS")
    print(metrics.to_string(index=False))
    print("\nM3_STAGE_B_BOOTSTRAP_SUMMARY")
    print(boot_summary.to_string(index=False))
    print("\nM3_STAGE_B_DECISIONS_CERTAIN_ONLY")
    print(
        decisions[
            decisions["subset"].astype(str) == "wb_wilson95_certain_only"
        ].to_string(index=False)
    )
    print("M3_POSTHOC_STAGE_B_COMPLETE")
    print(f"output={out}")
    print(f"python_wall_seconds={time.perf_counter()-started:.3f}")


def main() -> None:
    p = argparse.ArgumentParser(description="Run frozen cost-matched M3 Stage-B ablation")
    p.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m3_posthoc_stage_b_ablation_v1.json",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m3_posthoc_stage_b_ablation_v1",
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
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--prepare-only", action="store_true")
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
