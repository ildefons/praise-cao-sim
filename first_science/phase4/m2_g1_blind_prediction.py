"""Run the blind prospective G1 prediction side for frozen M2.

This stage is deliberately white-box free. It:
  * validates the frozen G1 contract and unchanged M1/M2 candidate sets;
  * materializes the frozen public asymmetric G1 condition;
  * runs BASE_M1 plus all 27 frozen M2 joint members on seeds 30000..30099;
  * computes the public M0 curve and G1 M1/M2 sigma curves;
  * freezes all prediction-side artifacts and hashes before any G1 white-box
    generation is permitted.

No Phase-1 graph reference and no G1 white-box generator are imported or read.
"""
from __future__ import annotations

import argparse
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
except ImportError:  # pragma: no cover
    resource = None

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
for directory in (PHASE2, PHASE3):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    build_same_rho_conditioned_m0_curve,
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
)
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402
from m2_b5_joint_ensemble_graph import (  # noqa: E402
    EXPECTED_A4_STATUS,
    EXPECTED_M0_CONTRACT_STATUS,
    EXPECTED_M1_CONFIRM_STATUS,
    EXPECTED_M1_CONTRACT_STATUS,
    EXPECTED_SEMANTIC_STATUS,
    _aggregate_joint_ensemble,
    _validate_and_build_variants,
)
from m2_b_one_at_a_time_graph import _request_summary  # noqa: E402
from m2_g1_graph_simulator import (  # noqa: E402
    execute_one_g1_prediction_trajectory,
)
from m2_g1_public_adapter import (  # noqa: E402
    G1_BRANCH_FIXED_LATENCY_SECONDS,
    G1_CONDITION_ID,
    G1_FIXED_COMMON_LATENCY_SECONDS,
    G1_PROVIDER_PR_SECONDS,
    build_g1_induced_global_boundary,
    build_g1_public_graph_spec,
    validate_g1_public_graph_spec,
)

EXPECTED_G1_CONTRACT_STATUS = "FROZEN_PHASE4_M2_G1_PROSPECTIVE_VALIDATION_CONTRACT_V1"
EXPECTED_B5_CONTRACT_STATUS = "FROZEN_PHASE4_M2_B5_JOINT_ENSEMBLE_GRAPH_CONTRACT_V1"
COMPLETE_STATUS = "FROZEN_PHASE4_M2_G1_BLIND_PREDICTIONS_V1"
TOL = 1e-12


def _prediction_seeds(contract: dict[str, Any], smoke: bool) -> tuple[int, ...]:
    cfg = dict(contract["prediction_protocol"])
    seeds = tuple(
        range(
            int(cfg["G1_prediction_seed_start"]),
            int(cfg["G1_prediction_seed_end_inclusive"]) + 1,
        )
    )
    expected = int(cfg["n_prediction_trajectories_per_variant"])
    if len(seeds) != expected:
        raise RuntimeError("G1 prediction seed bank length differs from frozen contract")
    if smoke:
        seeds = seeds[: int(cfg["smoke_testing"]["n_trajectories"])]
    if not seeds:
        raise RuntimeError("G1 prediction seed bank is empty")
    return seeds


def _validate_contract_and_public_adapter(
    g1_contract: dict[str, Any],
    b5_contract: dict[str, Any],
    graph_spec: dict[str, Any],
) -> None:
    if g1_contract.get("status") != EXPECTED_G1_CONTRACT_STATUS:
        raise RuntimeError("unexpected frozen G1 prospective contract status")
    if b5_contract.get("status") != EXPECTED_B5_CONTRACT_STATUS:
        raise RuntimeError("unexpected frozen B5 execution contract status")
    validate_g1_public_graph_spec(graph_spec)

    frozen = dict(g1_contract["frozen_method"])
    expected_portfolios = {
        str(provider): [str(x) for x in ids]
        for provider, ids in frozen["M2_provider_portfolios"].items()
    }
    b5_portfolios = {
        str(provider): [str(x) for x in ids]
        for provider, ids in b5_contract["frozen_provider_members"].items()
    }
    if expected_portfolios != b5_portfolios:
        raise RuntimeError("G1 M2 portfolios differ from the already-frozen B5 portfolios")

    ensemble = dict(frozen["M2_joint_ensemble"])
    if int(ensemble["n_members"]) != 27:
        raise RuntimeError("G1 contract no longer specifies 27 M2 joint members")
    if str(ensemble["member_weight"]) != "1/27":
        raise RuntimeError("G1 contract no longer specifies equal 1/27 member weights")
    if bool(ensemble["M1_is_member"]):
        raise RuntimeError("G1 contract unexpectedly includes M1 in the M2 ensemble")

    cond = dict(g1_contract["G1_public_condition"])
    if str(cond["condition_id"]) != G1_CONDITION_ID:
        raise RuntimeError("G1 condition ID differs from public adapter")
    result_pr = {
        str(k): float(v)
        for k, v in cond["provider_branch_PR_assignment_provenance"]["result"].items()
    }
    if result_pr != {k: float(v) for k, v in G1_PROVIDER_PR_SECONDS.items()}:
        raise RuntimeError("G1 provider propagation delays differ from frozen adapter")

    algebra = dict(g1_contract["G1_boundary_algebra"])
    if abs(
        float(algebra["common_latency_seconds_excluding_provider_branch_and_local_provider"])
        - G1_FIXED_COMMON_LATENCY_SECONDS
    ) > TOL:
        raise RuntimeError("G1 common latency constant differs from public adapter")
    branch = {
        str(k): float(v)
        for k, v in algebra["provider_branch_fixed_latency_seconds"].items()
    }
    if branch != {k: float(v) for k, v in G1_BRANCH_FIXED_LATENCY_SECONDS.items()}:
        raise RuntimeError("G1 branch latency constants differ from public adapter")


def _ledger(
    *,
    variant_id: str,
    surrogates: dict[str, Any],
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
                f"{variant_id}: existing G1 ledger missing checkpoint fields: {missing}"
            )
        actual = tuple(sorted(frame["trajectory_seed"].astype(int).unique().tolist()))
        if actual != tuple(sorted(seeds)):
            raise RuntimeError(f"{variant_id}: G1 checkpoint has a different seed bank")
        if set(frame["variant_id"].astype(str)) != {variant_id}:
            raise RuntimeError(f"{variant_id}: G1 checkpoint variant mismatch")
        if int(frame["trajectory"].nunique()) != len(seeds):
            raise RuntimeError(f"{variant_id}: G1 checkpoint trajectory count mismatch")
        if frame[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"{variant_id}: duplicate request rows in G1 checkpoint")
        print(f"M2-G1 resume {variant_id}: loaded completed ledger", flush=True)
        return frame, True

    frames: list[pd.DataFrame] = []
    for trajectory_index, seed in enumerate(seeds):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            one = execute_one_g1_prediction_trajectory(
                provider_surrogates=surrogates,
                graph_spec=graph_spec,
                workload_period=float(workload["period"]),
                stop_time=float(workload["horizon_max"]),
                trajectory_seed=int(seed),
                canonical_ipt=float(canonical_ipt),
                execution_fraction=float(execution_fraction),
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


def _g1_m0_curve(
    *,
    metadata: dict[str, Any],
    provider_surfaces: dict[str, pd.DataFrame],
    rho_support: list[float],
    horizons: list[float],
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for rho in rho_support:
        m0 = build_same_rho_conditioned_m0_curve(
            provider_surfaces,
            rho=float(rho),
            horizons=horizons,
        )
        provider_boundaries = provider_boundaries_at_region_rho(metadata, float(rho))
        boundary = build_g1_induced_global_boundary(provider_boundaries)
        m0["A_G_l_max"] = float(boundary.l_max)
        m0["A_G_c_max"] = float(boundary.c_max)
        m0["A_G_q_min"] = float(boundary.q_min)
        rows.append(m0)
    return pd.concat(rows, ignore_index=True).sort_values(
        ["rho_global", "horizon"]
    ).reset_index(drop=True)


def run(args: argparse.Namespace) -> None:
    wall_started = time.perf_counter()
    process_started = time.process_time()

    g1_contract_path = args.contract.resolve()
    b5_contract_path = args.b5_contract.resolve()
    semantic_path = args.semantic_contract.resolve()
    m1_contract_path = args.m1_contract.resolve()
    m0_contract_path = args.m0_contract.resolve()
    i1_manifest_path = args.i1_manifest.resolve()

    g1_contract = _read_json(g1_contract_path)
    b5_contract = _read_json(b5_contract_path)
    semantic_contract = _read_json(semantic_path)
    graph_spec = build_g1_public_graph_spec()
    _validate_contract_and_public_adapter(g1_contract, b5_contract, graph_spec)

    if semantic_contract.get("status") != EXPECTED_SEMANTIC_STATUS:
        raise RuntimeError("unexpected frozen M2 semantic contract status")

    anchors, portfolio, variants, design = _validate_and_build_variants(
        contract=b5_contract,
        semantic_contract=semantic_contract,
        a4_manifest_path=args.a4_confirmation_manifest.resolve(),
        a4_portfolio_path=args.a4_final_portfolio.resolve(),
        a4_replay_path=args.a4_replay_results.resolve(),
        m1_manifest_path=args.m1_confirmation_manifest.resolve(),
        m1_candidates_path=args.m1_anchor_candidates.resolve(),
    )

    m1_contract = _read_json(m1_contract_path)
    m0_contract = _read_json(m0_contract_path)
    if m1_contract.get("status") != EXPECTED_M1_CONTRACT_STATUS:
        raise RuntimeError("unexpected frozen M1 provider-lift contract status")
    if m0_contract.get("status") != EXPECTED_M0_CONTRACT_STATUS:
        raise RuntimeError("unexpected frozen M0 contract status")

    metadata, provider_surfaces, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), i1_manifest_path
    )
    rho_support = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)

    expected_workload = dict(g1_contract["G1_public_condition"]["workload"])
    if abs(float(workload["period"]) - float(expected_workload["period_seconds"])) > TOL:
        raise RuntimeError("public I1 workload period differs from frozen G1 contract")
    if abs(float(workload["horizon_max"]) - float(expected_workload["horizon_max_seconds"])) > TOL:
        raise RuntimeError("public I1 Hmax differs from frozen G1 contract")
    if len(rho_support) != len(expected_workload["rho_values"]) or not np.allclose(
        np.asarray(sorted(rho_support), dtype=float),
        np.asarray(sorted(float(v) for v in expected_workload["rho_values"]), dtype=float),
        atol=TOL,
        rtol=0.0,
    ):
        raise RuntimeError("public I1 rho support differs from frozen G1 contract")

    canonical_ipt = float(m1_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(m1_contract["pilot_scope"]["execution_fraction"])
    seeds = _prediction_seeds(g1_contract, bool(args.smoke))

    output = args.output
    if output is None:
        output = HERE / "results" / (
            "m2_g1_blind_prediction_smoke_v1"
            if args.smoke
            else "m2_g1_blind_prediction_v1"
        )
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    graph_spec_path = output / "m2_g1_public_condition_manifest_v1.json"
    _write_json(graph_spec_path, graph_spec)

    design_path = output / "m2_g1_joint_variant_design.csv"
    design.to_csv(design_path, index=False)
    candidate_path = output / "m2_g1_frozen_candidate_set.csv"
    pd.concat(
        [
            anchors.assign(candidate_source="M1_anchor"),
            portfolio.assign(candidate_source="A4_final_portfolio"),
        ],
        ignore_index=True,
        sort=False,
    ).to_csv(candidate_path, index=False)

    m0_curve = _g1_m0_curve(
        metadata=metadata,
        provider_surfaces=provider_surfaces,
        rho_support=rho_support,
        horizons=horizons,
    )
    m0_path = output / "m2_g1_m0_curve.csv"
    m0_curve.to_csv(m0_path, index=False)

    print("M2_G1_PUBLIC_CONDITION_AND_DESIGN_FROZEN_PASS")
    print(f"condition_id={G1_CONDITION_ID}")
    print(
        "provider_PR_seconds="
        + json.dumps({k: float(v) for k, v in G1_PROVIDER_PR_SECONDS.items()}, sort_keys=True)
    )
    print(design.to_string(index=False))
    print(f"prediction_seed_bank={seeds[0]}..{seeds[-1]} n={len(seeds)}")

    if args.prepare_only:
        print("M2_G1_PREPARE_ONLY_COMPLETE_NO_WHITEBOX")
        print(f"output={output}")
        return

    ledger_dir = output / "ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    curves: dict[str, pd.DataFrame] = {}
    request_rows: list[dict[str, Any]] = []
    reused_variants = 0
    total_request_rows = 0

    for variant_index, (variant_id, surrogate_map) in enumerate(variants.items(), start=1):
        print(
            f"M2-G1 variant {variant_index}/{len(variants)} "
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
            boundary = build_g1_induced_global_boundary(provider_boundaries)
            curve = build_empirical_graph_sigma_curve(
                ledger,
                boundary=boundary,
                rho_global=float(rho),
                horizons=horizons,
                stop_time=float(workload["horizon_max"]),
                accounting_origin=float(workload["accounting_origin"]),
                output_column="sigma",
            )
            curve.insert(0, "rho_global", float(rho))
            curve.insert(0, "variant_id", variant_id)
            curve["A_G_l_max"] = float(boundary.l_max)
            curve["A_G_c_max"] = float(boundary.c_max)
            curve["A_G_q_min"] = float(boundary.q_min)
            rho_frames.append(curve)
        curves[variant_id] = pd.concat(rho_frames, ignore_index=True)

    all_curves = pd.concat(curves.values(), ignore_index=True).sort_values(
        ["variant_id", "rho_global", "horizon"]
    ).reset_index(drop=True)
    if int(all_curves["variant_id"].nunique()) != 28:
        raise RuntimeError("G1 prediction bank does not contain 28 variants")

    grid = all_curves[["rho_global", "horizon"]].drop_duplicates()
    expected_grid_size = len(grid)
    counts = all_curves.groupby("variant_id").size()
    if not (counts.astype(int) == expected_grid_size).all():
        raise RuntimeError("G1 variants do not share one complete rho/horizon grid")
    for rho, group in all_curves.groupby("rho_global"):
        triples = group[["A_G_l_max", "A_G_c_max", "A_G_q_min"]].drop_duplicates()
        if len(triples) != 1:
            raise RuntimeError(f"rho={rho}: G1 A_G differs across variants")

    curves_path = output / "m2_g1_joint_graph_sigma_curves.csv"
    all_curves.to_csv(curves_path, index=False)

    ensemble = _aggregate_joint_ensemble(
        all_curves=all_curves,
        design=design,
        expected_members=27,
    )
    ensemble_path = output / "m2_g1_ensemble_curve.csv"
    ensemble.to_csv(ensemble_path, index=False)

    request_summary = pd.DataFrame(request_rows).merge(
        design, on="variant_id", how="left", validate="one_to_one"
    )
    request_path = output / "m2_g1_request_distribution_summary.csv"
    request_summary.to_csv(request_path, index=False)

    wall_seconds = float(time.perf_counter() - wall_started)
    process_seconds = float(time.process_time() - process_started)
    cost = {
        "status": "PHASE4_M2_G1_PREDICTION_COST_ACCOUNTING_V1",
        "smoke_mode": bool(args.smoke),
        "provider_local_simulation_trajectories": 0,
        "optimizer_or_GP_evaluations": 0,
        "n_m2_joint_variants": 27,
        "n_reference_m1_variants": 1,
        "n_total_graph_variants": 28,
        "n_trajectories_per_variant": len(seeds),
        "planned_graph_trajectories_for_this_mode": int(28 * len(seeds)),
        "checkpoint_reused_variants": int(reused_variants),
        "checkpoint_new_variants": int(28 - reused_variants),
        "total_request_rows_loaded_or_generated": int(total_request_rows),
        "python_wall_seconds": wall_seconds,
        "python_process_cpu_seconds": process_seconds,
        "runtime_snapshot": _cost_snapshot(),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    cost_path = output / "m2_g1_cost_manifest_v1.json"
    _write_json(cost_path, cost)

    status = (
        "PHASE4_M2_G1_SMOKE_PREDICTIONS_COMPLETE_NOT_SCIENTIFIC"
        if args.smoke
        else COMPLETE_STATUS
    )
    manifest = {
        "status": status,
        "smoke_mode": bool(args.smoke),
        "prospective_condition": True,
        "condition_id": G1_CONDITION_ID,
        "G1_whitebox_generated": False,
        "G1_whitebox_read": False,
        "phase1_graph_reference_read": False,
        "provider_private_trace_read": False,
        "provider_private_parameter_read": False,
        "provider_search": False,
        "candidate_set_changed": False,
        "candidate_parameters_changed": False,
        "ensemble_weights_changed": False,
        "M1_in_M2_ensemble": False,
        "equal_weight_joint_ensemble": True,
        "n_m2_joint_variants": 27,
        "n_total_simulated_variants_including_m1": 28,
        "n_trajectories_per_variant": len(seeds),
        "prediction_seed_start": int(seeds[0]),
        "prediction_seed_end_inclusive": int(seeds[-1]),
        "common_random_numbers_across_all_variants": True,
        "global_admissibility_region_identical_across_variants": True,
        "same_rho_diagonal": True,
        "Jaccard_D_A": "N/A",
        "g1_contract_sha256": _sha256(g1_contract_path),
        "semantic_contract_sha256": _sha256(semantic_path),
        "b5_contract_sha256": _sha256(b5_contract_path),
        "m1_contract_sha256": _sha256(m1_contract_path),
        "m0_contract_sha256": _sha256(m0_contract_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "g1_public_adapter_sha256": _sha256(HERE / "m2_g1_public_adapter.py"),
        "g1_simulator_sha256": _sha256(HERE / "m2_g1_graph_simulator.py"),
        "g1_runner_sha256": _sha256(Path(__file__).resolve()),
        "a4_confirmation_manifest_sha256": _sha256(
            args.a4_confirmation_manifest.resolve()
        ),
        "a4_final_portfolio_sha256": _sha256(args.a4_final_portfolio.resolve()),
        "a4_replay_results_sha256": _sha256(args.a4_replay_results.resolve()),
        "m1_confirmation_manifest_sha256": _sha256(
            args.m1_confirmation_manifest.resolve()
        ),
        "m1_anchor_candidates_sha256": _sha256(args.m1_anchor_candidates.resolve()),
        "public_condition_manifest_sha256": _sha256(graph_spec_path),
        "variant_design_sha256": _sha256(design_path),
        "frozen_candidate_set_sha256": _sha256(candidate_path),
        "m0_curve_sha256": _sha256(m0_path),
        "joint_graph_sigma_curves_sha256": _sha256(curves_path),
        "ensemble_curve_sha256": _sha256(ensemble_path),
        "request_distribution_summary_sha256": _sha256(request_path),
        "cost_manifest_sha256": _sha256(cost_path),
        "python_wall_seconds": wall_seconds,
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "public_condition_manifest": graph_spec_path.name,
            "variant_design": design_path.name,
            "frozen_candidate_set": candidate_path.name,
            "m0_curve": m0_path.name,
            "joint_graph_sigma_curves": curves_path.name,
            "ensemble_curve": ensemble_path.name,
            "request_distribution_summary": request_path.name,
            "cost_manifest": cost_path.name,
            "ledgers": "ledgers/<variant_id>.csv",
        },
        "next_gate": (
            "If smoke: inspect implementation only, then run full prediction side. "
            "If full: this manifest is the pre-whitebox G1 prediction freeze; only "
            "after it exists may a separate G1 white-box generator be implemented/run."
        ),
    }
    manifest_path = output / "m2_g1_prediction_freeze_manifest_v1.json"
    _write_json(manifest_path, manifest)

    if args.smoke:
        print("M2_G1_SMOKE_PREDICTION_COMPLETE_NO_WHITEBOX")
    else:
        print("M2_G1_BLIND_PREDICTIONS_FROZEN_BEFORE_WHITEBOX_PASS")

    print("\nM2_G1_ENSEMBLE_CURVE")
    print(ensemble.to_string(index=False))
    print("\nM2_G1_REQUEST_DISTRIBUTION_SUMMARY")
    print(request_summary.to_string(index=False))
    print(f"output={output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run and freeze the blind prospective G1 M0/M1/M2 predictions"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_g1_prospective_validation_v1.json",
    )
    parser.add_argument(
        "--b5-contract",
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
