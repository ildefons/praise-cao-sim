"""Run M2-B3: one-at-a-time graph propagation of the frozen M2-A4 portfolio."""
from __future__ import annotations

import argparse
import json
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
for directory in (PHASE2, PHASE3):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    PROVIDERS,
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from m1_graph_simulator_v2 import GraphProviderSurrogate, execute_one_m1_graph_trajectory  # noqa: E402
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
    build_public_induced_global_boundary,
)
from m2_b_one_at_a_time_graph import _request_summary, _surface_metrics  # noqa: E402
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402

EXPECTED_STATUS = "PHASE4_M2_B3_A4_PORTFOLIO_GRAPH_PROPAGATION_V1"
EXPECTED_A4_STATUS = "PHASE4_M2_A4_FINAL_PORTFOLIO_PASS_V1"
EXPECTED_M1_CONFIRM_STATUS = "PHASE4_M2_A_CONFIRMATION_PASS"
EXPECTED_M1_CONTRACT_STATUS = "IMPLEMENTATION_CANDIDATE_PHASE3_M1_LIFT_V2_NOT_FROZEN"
EXPECTED_M0_CONTRACT_STATUS = "FROZEN_PHASE3_M0_BASELINE_V2_SAME_RHO"
TOL = 1e-12


def _seeds(contract: dict[str, Any], smoke: bool) -> tuple[int, ...]:
    cfg = contract["graph_simulation"]
    seeds = tuple(range(int(cfg["trajectory_seed_start"]), int(cfg["trajectory_seed_end_inclusive"]) + 1))
    if len(seeds) != int(cfg["n_trajectories_per_variant"]):
        raise RuntimeError("declared graph seed bank length mismatch")
    if smoke:
        seeds = seeds[: int(cfg["smoke_n_trajectories_per_variant"])]
    return seeds


def _load_and_freeze_candidates(
    contract: dict[str, Any],
    a4_manifest_path: Path,
    a4_portfolio_path: Path,
    a4_replay_path: Path,
    m1_manifest_path: Path,
    m1_candidates_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, GraphProviderSurrogate]], pd.DataFrame]:
    a4_manifest = _read_json(a4_manifest_path)
    if a4_manifest.get("status") != EXPECTED_A4_STATUS:
        raise RuntimeError("M2-A4 final portfolio gate did not pass")
    counts = dict(a4_manifest.get("final_portfolio_counts", {}))
    if any(int(counts.get(p, 0)) != 3 for p in PROVIDERS):
        raise RuntimeError("M2-A4 must contain exactly three final candidates per provider")
    for key in ("graph_simulation", "graph_prediction_read", "graph_whitebox_read"):
        if bool(a4_manifest.get(key)):
            raise RuntimeError(f"M2-A4 provenance unexpectedly contains graph access: {key}")

    portfolio = pd.read_csv(a4_portfolio_path)
    required = {
        "provider", "candidate_id", "final_portfolio_order", "source_stage",
        "mean_service_time", "cost_rate", "service_cv", "confirmation_mse",
        "z_log_mu", "z_log_kappa", "z_cv",
    }
    missing = sorted(required.difference(portfolio.columns))
    if missing:
        raise ValueError("M2-A4 final portfolio missing fields: " + ", ".join(missing))
    if len(portfolio) != 9 or portfolio["candidate_id"].astype(str).duplicated().any():
        raise RuntimeError("M2-A4 final portfolio must contain nine unique candidates")

    expected = {
        str(p): [str(x) for x in ids]
        for p, ids in contract["variant_design"]["expected_final_candidate_ids"].items()
    }
    actual: dict[str, list[str]] = {}
    for provider in PROVIDERS:
        rows = portfolio[portfolio["provider"].astype(str) == provider].sort_values("final_portfolio_order")
        if len(rows) != 3 or rows["final_portfolio_order"].astype(int).tolist() != [1, 2, 3]:
            raise RuntimeError(f"{provider}: final A4 portfolio is not exactly ordered 1,2,3")
        actual[provider] = rows["candidate_id"].astype(str).tolist()
    if actual != expected:
        raise RuntimeError(f"frozen A4 candidate set mismatch: expected={expected} actual={actual}")

    replay = pd.read_csv(a4_replay_path)
    if not {"provider", "candidate_id", "replay_mse"}.issubset(replay.columns):
        raise ValueError("M2-A4 replay results missing required fields")
    if set(replay["candidate_id"].astype(str)) != set(portfolio["candidate_id"].astype(str)):
        raise RuntimeError("M2-A4 replay does not cover exactly the final portfolio")
    portfolio = portfolio.merge(
        replay[["provider", "candidate_id", "replay_mse"]],
        on=["provider", "candidate_id"],
        how="left",
        validate="one_to_one",
    )

    m1_manifest = _read_json(m1_manifest_path)
    if m1_manifest.get("status") != EXPECTED_M1_CONFIRM_STATUS:
        raise RuntimeError("unexpected M1-anchor confirmation status")
    if bool(m1_manifest.get("graph_whitebox_read")):
        raise RuntimeError("M1-anchor confirmation unexpectedly read graph reference")

    m1 = pd.read_csv(m1_candidates_path)
    anchors = m1[
        (m1["selection_role"].astype(str) == "M1")
        & (m1["confirmation_compatible"].astype(bool))
    ].copy()
    if len(anchors) != 3 or set(anchors["provider"].astype(str)) != set(PROVIDERS):
        raise RuntimeError("expected one confirmed frozen M1 anchor per provider")

    anchor_rows = {str(r.provider): r for r in anchors.itertuples(index=False)}
    base = {
        p: GraphProviderSurrogate(
            mean_service_time=float(anchor_rows[p].mean_service_time),
            cost_rate=float(anchor_rows[p].cost_rate),
            service_cv=float(anchor_rows[p].service_cv),
        )
        for p in PROVIDERS
    }
    variants: dict[str, dict[str, GraphProviderSurrogate]] = {"BASE_M1": base}
    design_rows: list[dict[str, Any]] = [{
        "variant_id": "BASE_M1",
        "changed_provider": "",
        "changed_candidate_id": "",
        "final_portfolio_order": 0,
        "source_stage": "M1_ANCHOR",
        "confirmation_mse": np.nan,
        "replay_mse": np.nan,
        "z_distance_from_m1": 0.0,
    }]

    for rec in portfolio.sort_values(["provider", "final_portfolio_order"]).itertuples(index=False):
        provider = str(rec.provider)
        candidate_id = str(rec.candidate_id)
        candidate_map = dict(base)
        candidate_map[provider] = GraphProviderSurrogate(
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
        )
        variants[candidate_id] = candidate_map

        anchor = anchors[anchors["provider"].astype(str) == provider].iloc[0]
        z_distance = np.nan
        if all(c in anchors.columns for c in ("z_log_mu", "z_log_kappa", "z_cv")):
            za = anchor[["z_log_mu", "z_log_kappa", "z_cv"]].to_numpy(float)
            zb = np.array([float(rec.z_log_mu), float(rec.z_log_kappa), float(rec.z_cv)])
            z_distance = float(np.linalg.norm(zb - za))
        design_rows.append({
            "variant_id": candidate_id,
            "changed_provider": provider,
            "changed_candidate_id": candidate_id,
            "final_portfolio_order": int(rec.final_portfolio_order),
            "source_stage": str(rec.source_stage),
            "confirmation_mse": float(rec.confirmation_mse),
            "replay_mse": float(rec.replay_mse),
            "z_distance_from_m1": z_distance,
        })

    if len(variants) != int(contract["variant_design"]["n_expected_variants"]):
        raise RuntimeError("unexpected M2-B3 variant count")
    return anchors.reset_index(drop=True), portfolio.reset_index(drop=True), variants, pd.DataFrame(design_rows)


def _ledger(
    variant_id: str,
    surrogates: dict[str, GraphProviderSurrogate],
    seeds: tuple[int, ...],
    graph_spec: dict[str, Any],
    workload: dict[str, Any],
    canonical_ipt: float,
    execution_fraction: float,
    path: Path,
) -> pd.DataFrame:
    if path.exists():
        frame = pd.read_csv(path)
        actual = tuple(sorted(frame["trajectory_seed"].astype(int).unique().tolist()))
        if actual != tuple(sorted(seeds)):
            raise RuntimeError(f"{variant_id}: existing ledger has a different seed bank")
        if set(frame["variant_id"].astype(str)) != {variant_id}:
            raise RuntimeError(f"{variant_id}: existing ledger variant mismatch")
        if int(frame["trajectory"].nunique()) != len(seeds):
            raise RuntimeError(f"{variant_id}: existing ledger trajectory count mismatch")
        if frame[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"{variant_id}: duplicate request rows in checkpoint")
        print(f"M2-B3 resume {variant_id}: loaded completed ledger", flush=True)
        return frame

    frames: list[pd.DataFrame] = []
    for i, seed in enumerate(seeds):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            one = execute_one_m1_graph_trajectory(
                provider_surrogates=surrogates,
                graph_spec=graph_spec,
                workload_period=float(workload["period"]),
                stop_time=float(workload["horizon_max"]),
                trajectory_seed=int(seed),
                canonical_ipt=canonical_ipt,
                execution_fraction=execution_fraction,
            )
        one.insert(0, "trajectory", i)
        one.insert(1, "trajectory_seed", int(seed))
        frames.append(one)
        if i == 0 or (i + 1) % 25 == 0 or i + 1 == len(seeds):
            print(f"  {variant_id}: {i + 1}/{len(seeds)}", flush=True)
    frame = pd.concat(frames, ignore_index=True)
    frame.insert(0, "variant_id", variant_id)
    frame.to_csv(path, index=False)
    return frame


def _pairwise(curves: dict[str, pd.DataFrame], design: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for provider in PROVIDERS:
        ids = design[design["changed_provider"].astype(str) == provider].sort_values(
            "final_portfolio_order"
        )["variant_id"].astype(str).tolist()
        if len(ids) != 3:
            raise RuntimeError(f"{provider}: expected three A4 graph variants")
        for i in range(2):
            for j in range(i + 1, 3):
                summary, _ = _surface_metrics(curves[ids[i]], curves[ids[j]])
                rows.append({
                    "provider": provider,
                    "variant_a": ids[i],
                    "variant_b": ids[j],
                    "pairwise_mae": float(summary["mae_vs_base"]),
                    "pairwise_rmse": float(summary["rmse_vs_base"]),
                    "pairwise_max_abs_delta": float(summary["max_abs_delta_vs_base"]),
                })
    return pd.DataFrame(rows)


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract_path = args.contract.resolve()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected M2-B3 contract status")

    anchors, portfolio, variants, design = _load_and_freeze_candidates(
        contract,
        args.a4_confirmation_manifest.resolve(),
        args.a4_final_portfolio.resolve(),
        args.a4_replay_results.resolve(),
        args.m1_confirmation_manifest.resolve(),
        args.m1_anchor_candidates.resolve(),
    )

    m1_contract = _read_json(args.m1_contract.resolve())
    m0_contract = _read_json(args.m0_contract.resolve())
    if m1_contract.get("status") != EXPECTED_M1_CONTRACT_STATUS:
        raise RuntimeError("unexpected M1-v2 contract status")
    if m0_contract.get("status") != EXPECTED_M0_CONTRACT_STATUS:
        raise RuntimeError("unexpected M0 contract status")

    metadata, _, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    rho_support = common_same_rho_support(metadata)
    horizons = common_horizon_support(metadata)
    workload = _common_workload_contract(metadata)
    graph_spec = dict(m0_contract["phase1_benchmark_adapter"])
    canonical_ipt = float(m1_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(m1_contract["pilot_scope"]["execution_fraction"])
    seeds = _seeds(contract, bool(args.smoke))

    output = args.output
    if output is None:
        output = HERE / "results" / (
            "m2_b3_a4_portfolio_graph_smoke_v1" if args.smoke
            else "m2_b3_a4_portfolio_graph_v1"
        )
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    design.to_csv(output / "m2_b3_variant_design.csv", index=False)
    pd.concat([
        anchors.assign(candidate_source="M1_anchor"),
        portfolio.assign(candidate_source="A4_final_portfolio"),
    ], ignore_index=True, sort=False).to_csv(output / "m2_b3_frozen_candidate_set.csv", index=False)

    print("M2_B3_A4_PORTFOLIO_DESIGN_FROZEN_PASS")
    print(design.to_string(index=False))
    print(f"graph_seed_bank={seeds[0]}..{seeds[-1]} n={len(seeds)}")
    if args.prepare_only:
        print("M2_B3_PREPARE_ONLY_COMPLETE")
        print(f"output={output}")
        return

    ledger_dir = output / "ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    curves: dict[str, pd.DataFrame] = {}
    requests: list[dict[str, Any]] = []
    total_rows = 0

    for k, (variant_id, surrogate_map) in enumerate(variants.items(), start=1):
        print(f"M2-B3 variant {k}/{len(variants)} {variant_id} trajectories={len(seeds)}", flush=True)
        frame = _ledger(
            variant_id, surrogate_map, seeds, graph_spec, workload,
            canonical_ipt, execution_fraction, ledger_dir / f"{variant_id}.csv"
        )
        total_rows += len(frame)
        requests.append(_request_summary(variant_id, frame))
        rho_frames: list[pd.DataFrame] = []
        for rho in rho_support:
            provider_boundaries = provider_boundaries_at_region_rho(metadata, float(rho))
            induced = build_public_induced_global_boundary(provider_boundaries, m0_contract)
            curve = build_empirical_graph_sigma_curve(
                frame,
                boundary=induced,
                rho_global=float(rho),
                horizons=horizons,
                stop_time=float(workload["horizon_max"]),
                accounting_origin=float(workload["accounting_origin"]),
                output_column="sigma",
            )
            curve.insert(0, "rho_global", float(rho))
            curve.insert(0, "variant_id", variant_id)
            curve["A_G_l_max"] = float(induced.l_max)
            curve["A_G_c_max"] = float(induced.c_max)
            curve["A_G_q_min"] = float(induced.q_min)
            rho_frames.append(curve)
        curves[variant_id] = pd.concat(rho_frames, ignore_index=True)

    all_curves = pd.concat(curves.values(), ignore_index=True).sort_values(
        ["variant_id", "rho_global", "horizon"]
    ).reset_index(drop=True)
    all_curves.to_csv(output / "m2_b3_graph_sigma_curves.csv", index=False)

    base = curves["BASE_M1"]
    surface_rows: list[dict[str, Any]] = []
    per_rho_rows: list[dict[str, Any]] = []
    delta_frames: list[pd.DataFrame] = []
    for variant_id, curve in curves.items():
        summary, merged = _surface_metrics(curve, base)
        surface_rows.append({"variant_id": variant_id, **summary})
        delta_frames.append(merged)
        for rho in rho_support:
            a = curve[np.isclose(curve["rho_global"].astype(float), float(rho), atol=TOL, rtol=0.0)]
            b = base[np.isclose(base["rho_global"].astype(float), float(rho), atol=TOL, rtol=0.0)]
            rho_summary, _ = _surface_metrics(a, b)
            per_rho_rows.append({"variant_id": variant_id, "rho_global": float(rho), **rho_summary})

    surface = pd.DataFrame(surface_rows).merge(design, on="variant_id", validate="one_to_one")
    surface = surface.sort_values(["mae_vs_base", "variant_id"], ascending=[False, True])
    surface.to_csv(output / "m2_b3_surface_spread_summary.csv", index=False)

    pd.DataFrame(per_rho_rows).merge(
        design, on="variant_id", validate="many_to_one"
    ).to_csv(output / "m2_b3_per_rho_spread_summary.csv", index=False)
    pd.concat(delta_frames, ignore_index=True).to_csv(
        output / "m2_b3_graph_sigma_deltas_vs_base.csv", index=False
    )

    pairwise = _pairwise(curves, design)
    pairwise.to_csv(output / "m2_b3_within_provider_pairwise_spread.csv", index=False)
    provider_summary = pairwise.groupby("provider", as_index=False).agg(
        mean_pairwise_mae=("pairwise_mae", "mean"),
        max_pairwise_mae=("pairwise_mae", "max"),
        max_pairwise_rmse=("pairwise_rmse", "max"),
        max_pairwise_abs_delta=("pairwise_max_abs_delta", "max"),
    )
    provider_summary.to_csv(output / "m2_b3_provider_spread_summary.csv", index=False)

    request_summary = pd.DataFrame(requests).merge(design, on="variant_id", validate="one_to_one")
    request_summary.to_csv(output / "m2_b3_request_distribution_summary.csv", index=False)

    manifest = {
        "status": "PHASE4_M2_B3_A4_PORTFOLIO_GRAPH_PROPAGATION_COMPLETE_V1",
        "smoke_mode": bool(args.smoke),
        "candidate_set_frozen_before_graph": True,
        "graph_whitebox_read": False,
        "graph_prediction_used_for_candidate_selection": False,
        "global_admissibility_region_identical_across_variants": True,
        "n_variants": len(variants),
        "variant_ids": list(variants),
        "n_trajectories_per_variant": len(seeds),
        "graph_trajectory_seed_start": int(seeds[0]),
        "graph_trajectory_seed_end_inclusive": int(seeds[-1]),
        "common_random_numbers_across_variants": True,
        "total_graph_trajectories": len(variants) * len(seeds),
        "total_request_rows": int(total_rows),
        "contract_sha256": _sha256(contract_path),
        "a4_confirmation_manifest_sha256": _sha256(args.a4_confirmation_manifest.resolve()),
        "a4_final_portfolio_sha256": _sha256(args.a4_final_portfolio.resolve()),
        "a4_replay_results_sha256": _sha256(args.a4_replay_results.resolve()),
        "m1_confirmation_manifest_sha256": _sha256(args.m1_confirmation_manifest.resolve()),
        "m1_anchor_candidates_sha256": _sha256(args.m1_anchor_candidates.resolve()),
        "m1_contract_sha256": _sha256(args.m1_contract.resolve()),
        "m0_contract_sha256": _sha256(args.m0_contract.resolve()),
        "public_i1_manifest_sha256": _sha256(args.i1_manifest.resolve()),
        "python_wall_seconds": time.perf_counter() - started,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "variant_design": "m2_b3_variant_design.csv",
            "frozen_candidate_set": "m2_b3_frozen_candidate_set.csv",
            "graph_sigma_curves": "m2_b3_graph_sigma_curves.csv",
            "surface_spread_summary": "m2_b3_surface_spread_summary.csv",
            "per_rho_spread_summary": "m2_b3_per_rho_spread_summary.csv",
            "graph_sigma_deltas": "m2_b3_graph_sigma_deltas_vs_base.csv",
            "within_provider_pairwise_spread": "m2_b3_within_provider_pairwise_spread.csv",
            "provider_spread_summary": "m2_b3_provider_spread_summary.csv",
            "request_distribution_summary": "m2_b3_request_distribution_summary.csv",
            "ledgers": "ledgers/<variant_id>.csv"
        },
        "next_gate": contract["next_gate"],
    }
    _write_json(output / "m2_b3_graph_propagation_manifest_v1.json", manifest)

    print("M2_B3_GRAPH_PREDICTIONS_MATERIALIZED_WITHOUT_WHITEBOX_PASS")
    print("\nWHOLE_SURFACE_SPREAD_VS_BASE_M1")
    print(surface.to_string(index=False))
    print("\nWITHIN_PROVIDER_A4_PAIRWISE_SPREAD")
    print(pairwise.to_string(index=False))
    print("\nPROVIDER_SPREAD_SUMMARY")
    print(provider_summary.to_string(index=False))
    print("\nREQUEST_DISTRIBUTION_SUMMARY")
    print(request_summary.to_string(index=False))
    print("M2_B3_A4_PORTFOLIO_GRAPH_PROPAGATION_COMPLETE")
    print(f"output={output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M2-B3 A4 portfolio graph propagation")
    parser.add_argument("--contract", type=Path, default=HERE / "config_phase4_m2_b3_a4_portfolio_graph_v1.json")
    parser.add_argument("--a4-confirmation-manifest", type=Path, default=HERE / "results" / "m2_a4_portfolio_confirmation_v1" / "m2_a4_portfolio_confirmation_manifest_v1.json")
    parser.add_argument("--a4-final-portfolio", type=Path, default=HERE / "results" / "m2_a4_portfolio_confirmation_v1" / "m2_a4_final_confirmed_portfolio.csv")
    parser.add_argument("--a4-replay-results", type=Path, default=HERE / "results" / "m2_a4_portfolio_confirmation_v1" / "m2_a4_replay_results.csv")
    parser.add_argument("--m1-confirmation-manifest", type=Path, default=HERE / "results" / "m2_a_confirmation_v1" / "m2_a_confirmation_manifest_v1.json")
    parser.add_argument("--m1-anchor-candidates", type=Path, default=HERE / "results" / "m2_a_confirmation_v1" / "m2_a_confirmed_compatible_candidates.csv")
    parser.add_argument("--m1-contract", type=Path, default=PHASE3 / "config_phase3_m1_contract_v2.json")
    parser.add_argument("--m0-contract", type=Path, default=PHASE3 / "config_phase3_m0_contract_v1.json")
    parser.add_argument("--i1-card-root", type=Path, default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public")
    parser.add_argument("--i1-manifest", type=Path, default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public" / "i1_rho_conditioned_manifest_v1.json")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
