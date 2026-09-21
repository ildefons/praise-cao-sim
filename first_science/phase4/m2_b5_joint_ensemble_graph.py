"""Run M2-B5: blind joint graph propagation of the frozen M2-A4 portfolios.

B5 completes the frozen M2 semantics without reading graph white-box evidence:
  * verify the frozen semantic and execution contracts;
  * load the three already-confirmed A4 members for each provider;
  * enumerate the complete 3x3x3 Cartesian product;
  * run every joint member plus BASE_M1 on one fresh common-random-number bank;
  * materialize every graph-sigma curve;
  * aggregate the 27 M2 members into an equal-weight mean and finite-portfolio
    min-max ambiguity range.

The M2 range is model ambiguity, not a statistical confidence interval.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import platform
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import resource
except ImportError:  # pragma: no cover - non-POSIX fallback
    resource = None

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
from m1_graph_simulator_v2 import (  # noqa: E402
    GraphProviderSurrogate,
    execute_one_m1_graph_trajectory,
)
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
    build_public_induced_global_boundary,
)
from m2_b_one_at_a_time_graph import _request_summary  # noqa: E402
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402

EXPECTED_CONTRACT_STATUS = "FROZEN_PHASE4_M2_B5_JOINT_ENSEMBLE_GRAPH_CONTRACT_V1"
EXPECTED_SEMANTIC_STATUS = "FROZEN_PHASE4_M2_JOINT_ENSEMBLE_SEMANTICS_V1"
EXPECTED_A4_STATUS = "PHASE4_M2_A4_FINAL_PORTFOLIO_PASS_V1"
EXPECTED_M1_CONFIRM_STATUS = "PHASE4_M2_A_CONFIRMATION_PASS"
EXPECTED_M1_CONTRACT_STATUS = "IMPLEMENTATION_CANDIDATE_PHASE3_M1_LIFT_V2_NOT_FROZEN"
EXPECTED_M0_CONTRACT_STATUS = "FROZEN_PHASE3_M0_BASELINE_V2_SAME_RHO"
COMPLETE_STATUS = "PHASE4_M2_B5_JOINT_ENSEMBLE_GRAPH_COMPLETE_V1"
TOL = 1e-12


def _seeds(contract: dict[str, Any], smoke: bool) -> tuple[int, ...]:
    cfg = dict(contract["graph_simulation"])
    seeds = tuple(
        range(
            int(cfg["trajectory_seed_start"]),
            int(cfg["trajectory_seed_end_inclusive"]) + 1,
        )
    )
    if len(seeds) != int(cfg["n_trajectories_per_variant"]):
        raise RuntimeError("declared B5 graph seed bank length mismatch")
    if smoke:
        seeds = seeds[: int(cfg["smoke_n_trajectories_per_variant"])]
    if not seeds:
        raise RuntimeError("B5 graph seed bank is empty")
    return seeds


def _surrogate(row: pd.Series) -> GraphProviderSurrogate:
    return GraphProviderSurrogate(
        mean_service_time=float(row["mean_service_time"]),
        cost_rate=float(row["cost_rate"]),
        service_cv=float(row["service_cv"]),
    )


def _validate_and_build_variants(
    *,
    contract: dict[str, Any],
    semantic_contract: dict[str, Any],
    a4_manifest_path: Path,
    a4_portfolio_path: Path,
    a4_replay_path: Path,
    m1_manifest_path: Path,
    m1_candidates_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, GraphProviderSurrogate]], pd.DataFrame]:
    if semantic_contract.get("status") != EXPECTED_SEMANTIC_STATUS:
        raise RuntimeError("unexpected frozen M2 semantic-contract status")
    if int(semantic_contract["joint_graph_portfolio"]["n_joint_combinations"]) != 27:
        raise RuntimeError("frozen M2 semantics no longer specify 27 joint members")
    if bool(semantic_contract["relationship_to_m1"]["M1_anchor_in_M2_ensemble"]):
        raise RuntimeError("frozen M2 semantics unexpectedly include M1 in the ensemble")

    a4_manifest = _read_json(a4_manifest_path)
    if a4_manifest.get("status") != EXPECTED_A4_STATUS:
        raise RuntimeError("M2-A4 final portfolio gate did not pass")
    counts = dict(a4_manifest.get("final_portfolio_counts", {}))
    if any(int(counts.get(provider, 0)) != 3 for provider in PROVIDERS):
        raise RuntimeError("M2-A4 must contain exactly three final candidates per provider")
    for key in ("graph_simulation", "graph_prediction_read", "graph_whitebox_read"):
        if bool(a4_manifest.get(key)):
            raise RuntimeError(f"M2-A4 provenance unexpectedly contains graph access: {key}")

    portfolio = pd.read_csv(a4_portfolio_path)
    required = {
        "provider",
        "candidate_id",
        "final_portfolio_order",
        "source_stage",
        "mean_service_time",
        "cost_rate",
        "service_cv",
        "confirmation_mse",
        "z_log_mu",
        "z_log_kappa",
        "z_cv",
    }
    missing = sorted(required.difference(portfolio.columns))
    if missing:
        raise ValueError("M2-A4 final portfolio missing fields: " + ", ".join(missing))
    if len(portfolio) != 9 or portfolio["candidate_id"].astype(str).duplicated().any():
        raise RuntimeError("M2-A4 final portfolio must contain nine unique candidates")

    expected = {
        str(provider): [str(x) for x in ids]
        for provider, ids in contract["frozen_provider_members"].items()
    }
    semantic_size = int(semantic_contract["provider_portfolios"]["portfolio_size_per_provider"])
    if semantic_size != 3:
        raise RuntimeError("frozen semantic contract portfolio size is not three")

    ordered_rows: dict[str, list[pd.Series]] = {}
    actual: dict[str, list[str]] = {}
    for provider in PROVIDERS:
        rows = portfolio[portfolio["provider"].astype(str) == provider].sort_values(
            "final_portfolio_order"
        )
        if len(rows) != 3:
            raise RuntimeError(f"{provider}: expected exactly three A4 candidates")
        if rows["final_portfolio_order"].astype(int).tolist() != [1, 2, 3]:
            raise RuntimeError(f"{provider}: A4 portfolio orders must be exactly 1,2,3")
        actual[provider] = rows["candidate_id"].astype(str).tolist()
        ordered_rows[provider] = [row for _, row in rows.iterrows()]
    if actual != expected:
        raise RuntimeError(
            f"frozen B5 member IDs disagree with A4 portfolio: expected={expected} actual={actual}"
        )

    replay = pd.read_csv(a4_replay_path)
    if not {"provider", "candidate_id", "replay_mse"}.issubset(replay.columns):
        raise ValueError("M2-A4 replay results missing required fields")
    if set(replay["candidate_id"].astype(str)) != set(portfolio["candidate_id"].astype(str)):
        raise RuntimeError("M2-A4 replay does not cover exactly the frozen portfolio")
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
        raise RuntimeError("M1-anchor confirmation unexpectedly read graph white-box")

    m1 = pd.read_csv(m1_candidates_path)
    m1_required = {
        "provider",
        "candidate_id",
        "selection_role",
        "mean_service_time",
        "cost_rate",
        "service_cv",
        "confirmation_compatible",
    }
    missing_m1 = sorted(m1_required.difference(m1.columns))
    if missing_m1:
        raise ValueError("M1 candidate file missing fields: " + ", ".join(missing_m1))
    anchors = m1[
        (m1["selection_role"].astype(str) == "M1")
        & (m1["confirmation_compatible"].astype(bool))
    ].copy()
    if len(anchors) != 3 or set(anchors["provider"].astype(str)) != set(PROVIDERS):
        raise RuntimeError("expected exactly one confirmed M1 anchor per provider")
    anchor_rows = {
        provider: anchors[anchors["provider"].astype(str) == provider].iloc[0]
        for provider in PROVIDERS
    }

    variants: dict[str, dict[str, GraphProviderSurrogate]] = {}
    design_rows: list[dict[str, Any]] = []

    base = {provider: _surrogate(anchor_rows[provider]) for provider in PROVIDERS}
    variants["BASE_M1"] = base
    design_rows.append(
        {
            "variant_id": "BASE_M1",
            "ensemble_member": False,
            "joint_weight": 0.0,
            "ProviderA_candidate_id": str(anchor_rows["ProviderA"]["candidate_id"]),
            "ProviderA_portfolio_order": 0,
            "ProviderB_candidate_id": str(anchor_rows["ProviderB"]["candidate_id"]),
            "ProviderB_portfolio_order": 0,
            "ProviderC_candidate_id": str(anchor_rows["ProviderC"]["candidate_id"]),
            "ProviderC_portfolio_order": 0,
        }
    )

    joint_weight = float(contract["weights"]["joint_member_weight"])
    for a_row, b_row, c_row in itertools.product(
        ordered_rows["ProviderA"],
        ordered_rows["ProviderB"],
        ordered_rows["ProviderC"],
    ):
        a_order = int(a_row["final_portfolio_order"])
        b_order = int(b_row["final_portfolio_order"])
        c_order = int(c_row["final_portfolio_order"])
        variant_id = f"M2J_A{a_order}_B{b_order}_C{c_order}"
        if variant_id in variants:
            raise RuntimeError(f"duplicate B5 joint variant id: {variant_id}")
        variants[variant_id] = {
            "ProviderA": _surrogate(a_row),
            "ProviderB": _surrogate(b_row),
            "ProviderC": _surrogate(c_row),
        }
        design_rows.append(
            {
                "variant_id": variant_id,
                "ensemble_member": True,
                "joint_weight": joint_weight,
                "ProviderA_candidate_id": str(a_row["candidate_id"]),
                "ProviderA_portfolio_order": a_order,
                "ProviderB_candidate_id": str(b_row["candidate_id"]),
                "ProviderB_portfolio_order": b_order,
                "ProviderC_candidate_id": str(c_row["candidate_id"]),
                "ProviderC_portfolio_order": c_order,
            }
        )

    design = pd.DataFrame(design_rows)
    m2_design = design[design["ensemble_member"].astype(bool)]
    expected_m2 = int(contract["variant_design"]["n_m2_joint_variants"])
    expected_total = int(contract["variant_design"]["n_total_simulated_variants_including_m1"])
    if len(m2_design) != expected_m2 or expected_m2 != 27:
        raise RuntimeError("B5 did not materialize exactly 27 M2 joint members")
    if len(variants) != expected_total or expected_total != 28:
        raise RuntimeError("B5 did not materialize exactly 27 M2 members plus BASE_M1")
    if not np.isclose(
        m2_design["joint_weight"].astype(float).sum(), 1.0, atol=TOL, rtol=0.0
    ):
        raise RuntimeError("B5 joint ensemble weights do not sum to one")
    if not np.allclose(
        m2_design["joint_weight"].astype(float).to_numpy(),
        np.full(expected_m2, 1.0 / expected_m2),
        atol=TOL,
        rtol=0.0,
    ):
        raise RuntimeError("B5 M2 members do not have equal weight")

    return (
        anchors.reset_index(drop=True),
        portfolio.reset_index(drop=True),
        variants,
        design.reset_index(drop=True),
    )


def _ledger(
    *,
    variant_id: str,
    surrogates: dict[str, GraphProviderSurrogate],
    seeds: tuple[int, ...],
    graph_spec: dict[str, Any],
    workload: dict[str, Any],
    canonical_ipt: float,
    execution_fraction: float,
    path: Path,
) -> tuple[pd.DataFrame, bool]:
    if path.exists():
        frame = pd.read_csv(path)
        required = {"variant_id", "trajectory", "trajectory_seed", "request_id"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise RuntimeError(
                f"{variant_id}: existing ledger missing checkpoint fields: {missing}"
            )
        actual = tuple(sorted(frame["trajectory_seed"].astype(int).unique().tolist()))
        if actual != tuple(sorted(seeds)):
            raise RuntimeError(f"{variant_id}: existing ledger has a different seed bank")
        if set(frame["variant_id"].astype(str)) != {variant_id}:
            raise RuntimeError(f"{variant_id}: existing ledger variant mismatch")
        if int(frame["trajectory"].nunique()) != len(seeds):
            raise RuntimeError(f"{variant_id}: existing ledger trajectory count mismatch")
        if frame[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"{variant_id}: duplicate request rows in checkpoint")
        print(f"M2-B5 resume {variant_id}: loaded completed ledger", flush=True)
        return frame, True

    frames: list[pd.DataFrame] = []
    for trajectory_index, seed in enumerate(seeds):
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
        one.insert(0, "trajectory", int(trajectory_index))
        one.insert(1, "trajectory_seed", int(seed))
        frames.append(one)
        if (
            trajectory_index == 0
            or (trajectory_index + 1) % 25 == 0
            or trajectory_index + 1 == len(seeds)
        ):
            print(
                f"  {variant_id}: {trajectory_index + 1}/{len(seeds)}",
                flush=True,
            )

    frame = pd.concat(frames, ignore_index=True)
    frame.insert(0, "variant_id", variant_id)
    frame.to_csv(path, index=False)
    return frame, False


def _aggregate_joint_ensemble(
    *,
    all_curves: pd.DataFrame,
    design: pd.DataFrame,
    expected_members: int,
) -> pd.DataFrame:
    m2_ids = set(
        design.loc[design["ensemble_member"].astype(bool), "variant_id"].astype(str)
    )
    if len(m2_ids) != expected_members:
        raise RuntimeError("joint design does not contain the expected M2 member count")

    selected = all_curves[all_curves["variant_id"].astype(str).isin(m2_ids)].copy()
    base = all_curves[all_curves["variant_id"].astype(str) == "BASE_M1"].copy()
    if selected.empty or base.empty:
        raise RuntimeError("B5 curves are missing M2 members or BASE_M1")

    rows: list[dict[str, Any]] = []
    for (rho, horizon), group in selected.groupby(["rho_global", "horizon"], sort=True):
        if int(group["variant_id"].nunique()) != expected_members:
            raise RuntimeError(
                f"rho={rho}, H={horizon}: incomplete M2 joint ensemble"
            )
        triples = group[["A_G_l_max", "A_G_c_max", "A_G_q_min"]].drop_duplicates()
        if len(triples) != 1:
            raise RuntimeError(
                f"rho={rho}, H={horizon}: A_G differs across M2 members"
            )

        values = group["sigma"].astype(float).to_numpy()
        ids = group["variant_id"].astype(str).to_numpy()
        i_min = int(np.argmin(values))
        i_max = int(np.argmax(values))
        rec = triples.iloc[0]

        b = base[
            np.isclose(base["rho_global"].astype(float), float(rho), atol=TOL, rtol=0.0)
            & np.isclose(base["horizon"].astype(float), float(horizon), atol=TOL, rtol=0.0)
        ]
        if len(b) != 1:
            raise RuntimeError(
                f"rho={rho}, H={horizon}: expected one BASE_M1 curve point"
            )
        b_rec = b.iloc[0]
        if not (
            abs(float(b_rec["A_G_l_max"]) - float(rec["A_G_l_max"])) <= TOL
            and abs(float(b_rec["A_G_c_max"]) - float(rec["A_G_c_max"])) <= TOL
            and abs(float(b_rec["A_G_q_min"]) - float(rec["A_G_q_min"])) <= TOL
        ):
            raise RuntimeError(
                f"rho={rho}, H={horizon}: BASE_M1 A_G differs from M2"
            )

        mean = float(np.mean(values))
        rows.append(
            {
                "rho_global": float(rho),
                "horizon": float(horizon),
                "A_G_l_max": float(rec["A_G_l_max"]),
                "A_G_c_max": float(rec["A_G_c_max"]),
                "A_G_q_min": float(rec["A_G_q_min"]),
                "n_m2_members": int(expected_members),
                "sigma_m2_mean": mean,
                "sigma_m2_min": float(values[i_min]),
                "sigma_m2_max": float(values[i_max]),
                "sigma_m2_std_population": float(np.std(values, ddof=0)),
                "sigma_m2_median": float(np.median(values)),
                "sigma_m2_q25": float(np.quantile(values, 0.25)),
                "sigma_m2_q75": float(np.quantile(values, 0.75)),
                "argmin_variant_id": str(ids[i_min]),
                "argmax_variant_id": str(ids[i_max]),
                "sigma_m1_same_seed_bank": float(b_rec["sigma"]),
                "m2_mean_minus_m1": mean - float(b_rec["sigma"]),
            }
        )

    ensemble = pd.DataFrame(rows).sort_values(
        ["rho_global", "horizon"]
    ).reset_index(drop=True)
    expected_points = int(
        selected[["rho_global", "horizon"]].drop_duplicates().shape[0]
    )
    if len(ensemble) != expected_points:
        raise RuntimeError("B5 ensemble aggregation changed the rho/horizon support")
    return ensemble


def _cost_snapshot() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
    }
    if resource is not None:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        payload.update(
            {
                "user_cpu_seconds": float(usage.ru_utime),
                "system_cpu_seconds": float(usage.ru_stime),
                "max_rss": int(usage.ru_maxrss),
                "max_rss_units": "KiB on Linux; bytes on macOS",
            }
        )
    return payload


def run(args: argparse.Namespace) -> None:
    wall_started = time.perf_counter()
    process_started = time.process_time()

    contract_path = args.contract.resolve()
    semantic_path = args.semantic_contract.resolve()
    contract = _read_json(contract_path)
    semantic_contract = _read_json(semantic_path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected M2-B5 execution-contract status")

    anchors, portfolio, variants, design = _validate_and_build_variants(
        contract=contract,
        semantic_contract=semantic_contract,
        a4_manifest_path=args.a4_confirmation_manifest.resolve(),
        a4_portfolio_path=args.a4_final_portfolio.resolve(),
        a4_replay_path=args.a4_replay_results.resolve(),
        m1_manifest_path=args.m1_confirmation_manifest.resolve(),
        m1_candidates_path=args.m1_anchor_candidates.resolve(),
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
    rho_support = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)
    if abs(float(max(horizons)) - float(workload["horizon_max"])) > TOL:
        raise RuntimeError("public I1 Hmax and workload horizon_max disagree")

    graph_spec = dict(m0_contract["phase1_benchmark_adapter"])
    canonical_ipt = float(m1_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(m1_contract["pilot_scope"]["execution_fraction"])
    seeds = _seeds(contract, bool(args.smoke))

    output = args.output
    if output is None:
        output = HERE / "results" / (
            "m2_b5_joint_ensemble_graph_smoke_v1"
            if args.smoke
            else "m2_b5_joint_ensemble_graph_v1"
        )
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    design_path = output / "m2_b5_joint_variant_design.csv"
    candidate_path = output / "m2_b5_frozen_candidate_set.csv"
    design.to_csv(design_path, index=False)
    pd.concat(
        [
            anchors.assign(candidate_source="M1_anchor"),
            portfolio.assign(candidate_source="A4_final_portfolio"),
        ],
        ignore_index=True,
        sort=False,
    ).to_csv(candidate_path, index=False)

    print("M2_B5_JOINT_DESIGN_FROZEN_PASS")
    print(design.to_string(index=False))
    print(f"graph_seed_bank={seeds[0]}..{seeds[-1]} n={len(seeds)}")
    if args.prepare_only:
        print("M2_B5_PREPARE_ONLY_COMPLETE")
        print(f"output={output}")
        return

    ledger_dir = output / "ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    curves: dict[str, pd.DataFrame] = {}
    request_rows: list[dict[str, Any]] = []
    total_request_rows = 0
    reused_variants = 0

    for variant_index, (variant_id, surrogate_map) in enumerate(variants.items(), start=1):
        print(
            f"M2-B5 variant {variant_index}/{len(variants)} "
            f"{variant_id} trajectories={len(seeds)}",
            flush=True,
        )
        ledger, reused = _ledger(
            variant_id=variant_id,
            surrogates=surrogate_map,
            seeds=seeds,
            graph_spec=graph_spec,
            workload=workload,
            canonical_ipt=canonical_ipt,
            execution_fraction=execution_fraction,
            path=ledger_dir / f"{variant_id}.csv",
        )
        reused_variants += int(reused)
        total_request_rows += len(ledger)
        request_rows.append(_request_summary(variant_id, ledger))

        rho_frames: list[pd.DataFrame] = []
        for rho in rho_support:
            provider_boundaries = provider_boundaries_at_region_rho(metadata, float(rho))
            induced = build_public_induced_global_boundary(
                provider_boundaries, m0_contract
            )
            curve = build_empirical_graph_sigma_curve(
                ledger,
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

    total_expected_variants = int(
        contract["variant_design"]["n_total_simulated_variants_including_m1"]
    )
    if int(all_curves["variant_id"].nunique()) != total_expected_variants:
        raise RuntimeError("B5 curve bank lost one or more simulated variants")

    # Every simulated variant must share the same rho/horizon grid and A_G.
    grid = all_curves[["rho_global", "horizon"]].drop_duplicates()
    expected_grid_size = len(grid)
    variant_counts = all_curves.groupby("variant_id").size()
    if not (variant_counts.astype(int) == expected_grid_size).all():
        raise RuntimeError("B5 variants do not share one complete rho/horizon grid")
    for rho, rg in all_curves.groupby("rho_global"):
        triples = rg[["A_G_l_max", "A_G_c_max", "A_G_q_min"]].drop_duplicates()
        if len(triples) != 1:
            raise RuntimeError(f"rho={rho}: A_G differs across B5 variants")

    curves_path = output / "m2_b5_joint_graph_sigma_curves.csv"
    all_curves.to_csv(curves_path, index=False)

    ensemble = _aggregate_joint_ensemble(
        all_curves=all_curves,
        design=design,
        expected_members=int(contract["variant_design"]["n_m2_joint_variants"]),
    )
    ensemble_path = output / "m2_b5_ensemble_curve.csv"
    ensemble.to_csv(ensemble_path, index=False)

    request_summary = pd.DataFrame(request_rows).merge(
        design, on="variant_id", how="left", validate="one_to_one"
    )
    request_path = output / "m2_b5_request_distribution_summary.csv"
    request_summary.to_csv(request_path, index=False)

    wall_seconds = float(time.perf_counter() - wall_started)
    process_seconds = float(time.process_time() - process_started)
    n_variants = len(variants)
    newly_simulated_variants = n_variants - reused_variants
    cost_manifest = {
        "status": "PHASE4_M2_B5_COST_ACCOUNTING_V1",
        "smoke_mode": bool(args.smoke),
        "provider_local_simulation_trajectories": 0,
        "optimizer_or_GP_evaluations": 0,
        "n_m2_joint_variants": int(contract["variant_design"]["n_m2_joint_variants"]),
        "n_reference_m1_variants": 1,
        "n_total_graph_variants": int(n_variants),
        "n_trajectories_per_variant": int(len(seeds)),
        "planned_graph_trajectories_for_this_mode": int(n_variants * len(seeds)),
        "newly_executed_graph_trajectories_this_invocation": int(
            newly_simulated_variants * len(seeds)
        ),
        "checkpoint_reused_variants": int(reused_variants),
        "checkpoint_new_variants": int(newly_simulated_variants),
        "total_request_rows_loaded_or_generated": int(total_request_rows),
        "python_wall_seconds": wall_seconds,
        "python_process_cpu_seconds": process_seconds,
        "runtime_snapshot": _cost_snapshot(),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    cost_path = output / "m2_b5_cost_manifest_v1.json"
    _write_json(cost_path, cost_manifest)

    manifest = {
        "status": COMPLETE_STATUS,
        "smoke_mode": bool(args.smoke),
        "semantic_contract_frozen": True,
        "candidate_set_frozen_before_graph": True,
        "graph_whitebox_read": False,
        "phase1_graph_reference_read": False,
        "provider_private_trace_read": False,
        "provider_private_parameter_read": False,
        "new_provider_search": False,
        "candidate_set_changed": False,
        "candidate_parameters_changed": False,
        "graph_prediction_used_for_member_selection": False,
        "M1_in_M2_ensemble": False,
        "equal_weight_joint_ensemble": True,
        "n_m2_joint_variants": int(contract["variant_design"]["n_m2_joint_variants"]),
        "n_total_simulated_variants_including_m1": int(n_variants),
        "n_trajectories_per_variant": int(len(seeds)),
        "graph_trajectory_seed_start": int(seeds[0]),
        "graph_trajectory_seed_end_inclusive": int(seeds[-1]),
        "common_random_numbers_across_all_variants": True,
        "global_admissibility_region_identical_across_variants": True,
        "same_rho_diagonal": True,
        "Jaccard_D_A": "N/A",
        "ensemble_mean_materialized": True,
        "finite_portfolio_ambiguity_range_materialized": True,
        "portfolio_range_is_confidence_interval": False,
        "total_request_rows": int(total_request_rows),
        "semantic_contract_sha256": _sha256(semantic_path),
        "execution_contract_sha256": _sha256(contract_path),
        "a4_confirmation_manifest_sha256": _sha256(
            args.a4_confirmation_manifest.resolve()
        ),
        "a4_final_portfolio_sha256": _sha256(args.a4_final_portfolio.resolve()),
        "a4_replay_results_sha256": _sha256(args.a4_replay_results.resolve()),
        "m1_confirmation_manifest_sha256": _sha256(
            args.m1_confirmation_manifest.resolve()
        ),
        "m1_anchor_candidates_sha256": _sha256(
            args.m1_anchor_candidates.resolve()
        ),
        "m1_contract_sha256": _sha256(args.m1_contract.resolve()),
        "m0_contract_sha256": _sha256(args.m0_contract.resolve()),
        "public_i1_manifest_sha256": _sha256(args.i1_manifest.resolve()),
        "variant_design_sha256": _sha256(design_path),
        "frozen_candidate_set_sha256": _sha256(candidate_path),
        "joint_graph_sigma_curves_sha256": _sha256(curves_path),
        "ensemble_curve_sha256": _sha256(ensemble_path),
        "request_distribution_summary_sha256": _sha256(request_path),
        "cost_manifest_sha256": _sha256(cost_path),
        "python_wall_seconds": wall_seconds,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "variant_design": design_path.name,
            "frozen_candidate_set": candidate_path.name,
            "joint_graph_sigma_curves": curves_path.name,
            "ensemble_curve": ensemble_path.name,
            "request_distribution_summary": request_path.name,
            "cost_manifest": cost_path.name,
            "ledgers": "ledgers/<variant_id>.csv",
        },
        "next_gate": contract["next_gate"],
    }
    manifest_path = output / "m2_b5_manifest_v1.json"
    _write_json(manifest_path, manifest)

    print("M2_B5_JOINT_GRAPH_PREDICTIONS_FROZEN_WITHOUT_WHITEBOX_PASS")
    print("\nM2_B5_ENSEMBLE_CURVE")
    print(ensemble.to_string(index=False))
    print("\nM2_B5_REQUEST_DISTRIBUTION_SUMMARY")
    print(request_summary.to_string(index=False))
    print("M2_B5_JOINT_ENSEMBLE_GRAPH_COMPLETE")
    print(f"output={output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run blind M2-B5 full 3x3x3 joint ensemble graph propagation"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_b5_joint_ensemble_graph_v1.json",
    )
    parser.add_argument(
        "--semantic-contract",
        type=Path,
        default=HERE / "config_phase4_m2_joint_ensemble_semantics_v1.json",
    )
    parser.add_argument(
        "--a4-confirmation-manifest",
        type=Path,
        default=HERE
        / "results"
        / "m2_a4_portfolio_confirmation_v1"
        / "m2_a4_portfolio_confirmation_manifest_v1.json",
    )
    parser.add_argument(
        "--a4-final-portfolio",
        type=Path,
        default=HERE
        / "results"
        / "m2_a4_portfolio_confirmation_v1"
        / "m2_a4_final_confirmed_portfolio.csv",
    )
    parser.add_argument(
        "--a4-replay-results",
        type=Path,
        default=HERE
        / "results"
        / "m2_a4_portfolio_confirmation_v1"
        / "m2_a4_replay_results.csv",
    )
    parser.add_argument(
        "--m1-confirmation-manifest",
        type=Path,
        default=HERE
        / "results"
        / "m2_a_confirmation_v1"
        / "m2_a_confirmation_manifest_v1.json",
    )
    parser.add_argument(
        "--m1-anchor-candidates",
        type=Path,
        default=HERE
        / "results"
        / "m2_a_confirmation_v1"
        / "m2_a_confirmed_compatible_candidates.csv",
    )
    parser.add_argument(
        "--m1-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m1_contract_v2.json",
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
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
