#!/usr/bin/env python3
"""Pilot-only reproduction gate for the M3 policy-transfer experiment.

No battery world (P1/P3/P4) is used. The gate combines archived-input
deterministic parity, archived pilot graph prediction reproduction,
matched-seed native simulator smoke, and optionally a complete B1400
pilot native replay. All writes are isolated, never to Phase-4 archives.

A successful seal requires ALL four stages, including the full native replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST = HERE.parent.parent
P2, P3, P4, P5 = (FIRST / f"phase{n}" for n in (2, 3, 4, 5))
for directory in (P2, P3, P4, P5, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

OUT = FIRST / "b1" / "local_audit" / "pilot_m3_reproduction_gate_v1"
PILOT = P4 / "results" / "m3_v4_dominant_mass_graph_v1"
LOCAL = P4 / "results" / "m3_local_weighting_v1"
CVROOT = P4 / "results" / "m3_lambda_cv_v3"
DESIGN = P4 / "results" / "m2_a2_nonadaptive_coverage_v1" / "m2_a2_lhs_design.csv"
PHASE2_CARD = P2 / "results" / "i1_cards_v2_rho_conditioned" / "public"
PREVIOUS = P4 / "results" / "sigma_regime_step0_calibration_v2" / "sigma_regime_v2_selected_regions_frozen.csv"
CONFIG = HERE / "config_pilot_m3_policy_transfer_v1.json"
TRANSFER_CODE = HERE / "run_pilot_m3_policy_transfer_v1.py"
TRANSFER_CORE = HERE / "_pilot_m3_policy_transfer_core_v1.py"
PILOT_CORE = P4 / "config_phase4_m3_v4_dominant_mass_graph_v1.json"
PILOT_CV = P4 / "config_phase4_m3_lambda_cv_v3.json"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def freeze(stage, info):
    path = OUT / (stage + ".json")
    record = {
        "status": "B1_PILOT_REPRODUCTION_" + stage.upper() + "_PASS",
        "pilot_graph_contract_sha256": digest(PILOT_CORE),
        "pilot_cv_contract_sha256": digest(PILOT_CV),
        "transfer_contract_sha256": digest(CONFIG),
        "reproduction_runner_sha256": digest(Path(__file__)),
        **info,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if read(path) != record:
            raise RuntimeError("Existing gate checkpoint changed: " + str(path))
    else:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    print(stage.upper() + "_PASS")
    return path


def check_inputs():
    necessary = [
        DESIGN, PILOT / "m3_v4_dominant_design.csv",
        PILOT / "m3_v4_blind_predictions.csv",
        PILOT / "m3_v4_allocation_table.csv",
        CVROOT / "m3_lambda_cv_summary.csv",
        CVROOT / "m3_v3_provider_weights.csv",
        LOCAL / "m3_local_rescore_results.csv",
        P4 / "config_phase4_m2_a2_nonadaptive_coverage_v1.json",
        P3 / "config_phase3_m1_contract_v2.json",
        P3 / "config_phase3_m1_contract_v2_providerC_expanded_v1.json",
        PILOT_CORE, PILOT_CV, PREVIOUS,
        TRANSFER_CODE, TRANSFER_CORE, CONFIG,
    ]
    for path in necessary:
        if not path.is_file():
            raise FileNotFoundError(path)
    for rank in range(1, 15):
        file = PILOT / "ledgers" / f"M3Q_R{rank:02d}.csv"
        if not file.is_file():
            raise FileNotFoundError(file)
    if len(pd.read_csv(PREVIOUS)) != 15:
        raise RuntimeError("Pilot must have exactly 15 frozen SLA queries")
    if read(CONFIG)["graph_budget"] != 1400:
        raise RuntimeError("Frozen transfer budget has changed")
    print("PILOT_REPRODUCTION_PREFLIGHT_PASS")
    print("Original provider world only; archived public cards, original G0 graph.")
    print("No P1/P3/P4, no Phase-II WB results, no existing science files modified.")


def deterministic():
    """Pilot parameter designs, five-fold lambda CV, weighted support and B1400."""
    check_inputs()
    from m2_a2_nonadaptive_coverage import _build_design
    from run_m1_provider_lift_v2 import load_verified_public_i1_cards
    from m3_lambda_cv_v3 import (
        _load_candidate_surfaces, _fold_assignments,
        _cv_scores, _summarize_cv, _select_lambda,
    )
    import audit_pilot_estimator_parity_v1 as original_parity

    meta, _, _ = load_verified_public_i1_cards(PHASE2_CARD)
    proposal_cfg = read(P4 / "config_phase4_m2_a2_nonadaptive_coverage_v1.json")
    regenerated, _ = _build_design(
        contract=proposal_cfg,
        metadata_by_provider=meta,
        base_contract=read(P3 / "config_phase3_m1_contract_v2.json"),
        expanded_c_contract=read(
            P3 / "config_phase3_m1_contract_v2_providerC_expanded_v1.json"
        ),
    )
    archived = pd.read_csv(DESIGN)
    key = ["provider", "lhs_index"]
    reconstructed = regenerated.sort_values(key).reset_index(drop=True)
    archived = archived.sort_values(key).reset_index(drop=True)
    if len(reconstructed) != 144 or len(archived) != 144:
        raise RuntimeError("Expected 48 candidates for each of three providers")
    if reconstructed["candidate_id"].tolist() != archived["candidate_id"].tolist():
        raise RuntimeError("Original candidate identities/order differ")
    candidate_fields = [
        "z_log_mu", "z_log_kappa", "z_cv",
        "mean_service_time", "cost_rate", "service_cv",
    ]
    drift = np.abs(
        reconstructed[candidate_fields].to_numpy(float)
        - archived[candidate_fields].to_numpy(float)
    )
    max_delta = float(drift.max())
    if not np.allclose(
        reconstructed[candidate_fields], archived[candidate_fields],
        rtol=1e-12, atol=1e-12
    ):
        raise RuntimeError(f"Original public candidate design mismatch: {max_delta:g}")

    pilot_local = pd.read_csv(LOCAL / "m3_local_rescore_results.csv")
    surfaces = _load_candidate_surfaces(
        local_results=pilot_local, local_surface_root=LOCAL / "local_surfaces"
    )
    assignment = _fold_assignments(next(iter(surfaces["ProviderA"].values())))
    scores = _cv_scores(
        surfaces=surfaces, assignments=assignment,
        lambda_grid=list(map(float, read(PILOT_CV)["lambda_grid"])),
    )
    summary = _summarize_cv(scores)
    winner = _select_lambda(summary)
    lam = float(winner["lambda"])
    if lam != 30:
        raise RuntimeError(f"Original CV should select 30, got {lam}")
    old_cv = pd.read_csv(CVROOT / "m3_lambda_cv_summary.csv").sort_values("lambda")
    now_cv = summary.sort_values("lambda")
    if not np.array_equal(old_cv["lambda"].to_numpy(), now_cv["lambda"].to_numpy()):
        raise RuntimeError("Pilot lambda grid/order differs")
    cv_delta = float(np.max(np.abs(
        old_cv["mean_validation_bernoulli_kl"].to_numpy(float)
        - now_cv["mean_validation_bernoulli_kl"].to_numpy(float)
    )))
    if cv_delta > 1e-12:
        raise RuntimeError(f"Original blocked-CV scores differ: {cv_delta}")
    # This existing independent check recomputes all 144 provider weights,
    # 48^3 joint weights, the first 14 models, and B1400 allocations.
    original_parity.main()
    freeze("deterministic", {
        "n_pilot_candidates": 144,
        "max_abs_candidate_parameter_difference": max_delta,
        "selected_lambda": lam,
        "max_abs_cv_score_difference": cv_delta,
        "joint_support_size": 14,
        "pilot_retained_mass_expected": 0.9991741970173574,
        "simulation_budget": 1400,
        "archived_lhs_design_sha256": digest(DESIGN),
        "archived_provider_weights_sha256": digest(
            CVROOT / "m3_v3_provider_weights.csv"
        ),
    })


def archived_scoring():
    """Rescore the ORIGINAL 15 queries using only archived original G0 ledgers."""
    if not (OUT / "deterministic.json").is_file():
        raise RuntimeError("Run --stage deterministic first")
    from m3_v4_dominant_mass_graph import _member_curves, _aggregate_predictions
    from run_m1_provider_lift_v2 import load_verified_public_i1_cards
    from diagnose_rho_conditioned_i1_m0 import (
        common_horizon_support, load_rho_conditioned_i1_cards,
    )
    from run_m1_graph_prediction_v2 import _common_workload_contract

    design = pd.read_csv(PILOT / "m3_v4_dominant_design.csv")
    alloc = pd.read_csv(PILOT / "m3_v4_allocation_table.csv")
    queries = pd.read_csv(PREVIOUS)
    pilot_contract = read(PILOT_CORE)
    cfg = dict(pilot_contract["inputs"])
    # Use precisely the original public-I1 metadata loader and horizon contract.
    metadata, _, _ = load_rho_conditioned_i1_cards(
        (P4 / cfg["public_i1_root"]).resolve(),
        (P4 / cfg["public_i1_root"] / "i1_rho_conditioned_manifest_v1.json").resolve(),
    )
    horizons = list(map(float, common_horizon_support(metadata)))
    workload = _common_workload_contract(metadata)
    curves = _member_curves(
        design=design, allocations=alloc, selected=queries,
        ledger_dir=PILOT / "ledgers", horizons=horizons,
        workload=workload, budgets=[1400],
    )
    mass = float(design["joint_weight"].sum())
    produced = _aggregate_predictions(
        curves, retained_mass=mass, allocations=alloc.loc[alloc["budget"].eq(1400)]
    )
    expected = pd.read_csv(PILOT / "m3_v4_blind_predictions.csv")
    expected = expected.loc[
        expected["budget"].astype(int).eq(1400)
        & expected["horizon"].astype(float).between(60, 240)
    ].copy()
    produced = produced.loc[
        produced["budget"].astype(int).eq(1400)
        & produced["horizon"].astype(float).between(60, 240)
    ].copy()
    keys = ["budget", "rho_global", "regime", "horizon"]
    merged = produced[keys + ["sigma_m3_dominant"]].merge(
        expected[keys + ["sigma_m3_dominant"]],
        on=keys, validate="one_to_one", suffixes=("_replay", "_archived"),
    )
    if len(produced) != 555 or len(expected) != 555 or len(merged) != 555:
        raise RuntimeError("Pilot scoring keys/point count differ from archived 555")
    err = abs(
        merged["sigma_m3_dominant_replay"]
        - merged["sigma_m3_dominant_archived"]
    )
    if float(err.max()) > 1e-12:
        raise RuntimeError(f"Original 555 prediction values differ: {float(err.max())}")
    freeze("archived_scoring", {
        "n_pilot_queries": 15, "n_horizons": 37,
        "scored_points": 555,
        "max_abs_graph_prediction_difference": float(err.max()),
        "archived_predictions_sha256": digest(
            PILOT / "m3_v4_blind_predictions.csv"
        ),
    })


def graph_smoke():
    """Replay a few real original G0 seeds against the new G_PAR simulator."""
    if not (OUT / "deterministic.json").is_file():
        raise RuntimeError("Run --stage deterministic first")
    from audit_original_world_bridge_v1 import main as bridge
    result = bridge(ranks=3, n_per_rank=2, start_rank=1)
    if result != 0:
        raise RuntimeError("Matched original-world graph smoke differs")
    freeze("graph_smoke", {
        "tested_ranks": [1, 2, 3],
        "seeds_per_rank": 2,
        "matched_original_ip_t": 1e6,
        "pilot_15_query_scoring_checked": True,
        "scope": "subset only, not full B1400 reproduction",
    })


def _matched_trajectory(original, fresh, *, rank, seed):
    key = ["request_id"]
    a = original.sort_values(key).reset_index(drop=True)
    b = fresh.sort_values(key).reset_index(drop=True)
    if not a[key].equals(b[key]) or len(a) != len(b):
        raise RuntimeError(f"rank {rank} seed {seed}: request identities/rows differ")
    for col in ("emission", "completion", "L", "C", "Q"):
        x, y = a[col].to_numpy(float), b[col].to_numpy(float)
        if not np.isclose(x, y, rtol=1e-8, atol=1e-8, equal_nan=True).all():
            raise RuntimeError(f"rank {rank} seed {seed}: {col} differs")
    for col in ("status", "completed_by_stop"):
        if not a[col].astype(str).equals(b[col].astype(str)):
            raise RuntimeError(f"rank {rank} seed {seed}: {col} differs")
    return int(len(a))


def full_graph(*, max_trajectories=0):
    """Native ORIGINAL G0 replay, full B1400 seed bank, isolated per-seed checkpoints."""
    for name in ("deterministic", "archived_scoring", "graph_smoke"):
        if not (OUT / (name + ".json")).exists():
            raise RuntimeError("Run --stage " + name.replace("_", "-") + " first")
    from m1_graph_simulator_v2 import (
        GraphProviderSurrogate, execute_one_m1_graph_trajectory,
    )
    design = pd.read_csv(PILOT / "m3_v4_dominant_design.csv").sort_values("rank")
    weights = pd.read_csv(CVROOT / "m3_v3_provider_weights.csv")
    graph_spec = read(P3 / "config_phase3_m0_contract_v1.json")[
        "phase1_benchmark_adapter"
    ]
    legacy_contract = read(P3 / "config_phase3_m1_contract_v2.json")
    c = legacy_contract["fixed_closure_conventions"]
    sim = read(PILOT_CORE)["simulation_budget"]
    if sim["seed_base"] != 3600000 or sim["seed_block_stride"] != 10000:
        raise RuntimeError("Original graph seed contract changed")
    if len(design) != 14 or int(design["n_B1400"].sum()) != 1400:
        raise RuntimeError("Expected pilot Top14 B1400 allocations")
    # Public contract workload, not a new battery world.
    from run_m1_provider_lift_v2 import load_verified_public_i1_cards
    meta, _, _ = load_verified_public_i1_cards(PHASE2_CARD)
    workload = meta["ProviderA"]["workload_contract"]
    period = float(workload["period"])
    stop = 240.
    done = 0
    for row in design.itertuples(index=False):
        rank = int(row.rank)
        ids = {p: str(getattr(row, p + "_candidate_id")) for p in PROVIDERS}
        local = {}
        for provider in PROVIDERS:
            q = weights.loc[
                weights["provider"].astype(str).eq(provider)
                & weights["candidate_id"].astype(str).eq(ids[provider])
            ]
            if len(q) != 1:
                raise RuntimeError(f"Missing pilot provider hypothesis {ids[provider]}")
            v = q.iloc[0]
            local[provider] = GraphProviderSurrogate(
                mean_service_time=float(v["mean_service_time"]),
                cost_rate=float(v["cost_rate"]),
                service_cv=float(v["service_cv"]),
            )
        origin = PILOT / "ledgers" / f"M3Q_R{rank:02d}.csv"
        source_hash = digest(origin)
        archive = pd.read_csv(origin)
        for offset in range(int(row.n_B1400)):
            seed = int(row.seed_start) + offset
            checkpoint = OUT / "native_full" / f"rank_{rank:02d}" / f"seed_{seed}.json"
            if checkpoint.exists():
                t = read(checkpoint)
                if (t.get("seed") != seed or
                    t.get("archived_rank_ledger_sha256") != source_hash or
                    t.get("pilot_graph_contract_sha256") != digest(PILOT_CORE) or
                    t.get("reproduction_runner_sha256") != digest(Path(__file__))):
                    raise RuntimeError(f"Incompatible native replay checkpoint: {checkpoint}")
            else:
                archived_one = archive.loc[archive["trajectory_seed"].astype(int).eq(seed)]
                if len(archived_one) == 0:
                    raise RuntimeError(f"Pilot archived trajectory missing: rank={rank}, seed={seed}")
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", FutureWarning)
                    new = execute_one_m1_graph_trajectory(
                        provider_surrogates=local, graph_spec=graph_spec,
                        workload_period=period, stop_time=stop, trajectory_seed=seed,
                        canonical_ipt=float(c["canonical_IPT"]),
                        execution_fraction=float(legacy_contract["pilot_scope"]["execution_fraction"]),
                    )
                n = _matched_trajectory(archived_one, new, rank=rank, seed=seed)
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "rank": rank, "seed": seed, "requests": n,
                    "archived_rank_ledger_sha256": source_hash,
                    "pilot_graph_contract_sha256": digest(PILOT_CORE),
                    "reproduction_runner_sha256": digest(Path(__file__)),
                    "matched_original_native_G0": True,
                }
                tmp = checkpoint.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(payload, indent=2) + "\n")
                os.replace(tmp, checkpoint)
            done += 1
            if done == 1 or done % 25 == 0 or done == 1400:
                print(f"PILOT NATIVE REPLAY: {done}/1400 verified trajectories", flush=True)
            if max_trajectories and done >= max_trajectories:
                print("BOUNDED CHECKPOINT COMPLETE; full pilot gate NOT sealed.")
                return
    if done != 1400:
        raise RuntimeError(f"Full native pilot reproduction incomplete: {done}/1400")
    freeze("full_graph", {
        "replayed_native_trajectories": done, "n_joint_models": 14,
        "matched_archived_pilot_G0": True,
        "graph_seed_base": 3600000,
        "graph_ip_t": float(c["canonical_IPT"]),
        "pilot_retained_mass": float(design["joint_weight"].sum()),
        "original_ledger_sha256_by_rank": {
            str(int(row.rank)): digest(
                PILOT / "ledgers" / f"M3Q_R{int(row.rank):02d}.csv"
            ) for row in design.itertuples(index=False)
        },
    })


def seal():
    stages = ("deterministic", "archived_scoring", "graph_smoke", "full_graph")
    payload = {}
    for stage in stages:
        path = OUT / (stage + ".json")
        if not path.exists():
            raise RuntimeError(f"Pilot reproduction NOT complete; missing {path}")
        obj = read(path)
        if obj["status"] != "B1_PILOT_REPRODUCTION_" + stage.upper() + "_PASS":
            raise RuntimeError("Unexpected pilot parity stage status")
        for field, expected in (
            ("pilot_graph_contract_sha256", digest(PILOT_CORE)),
            ("pilot_cv_contract_sha256", digest(PILOT_CV)),
            ("transfer_contract_sha256", digest(CONFIG)),
            ("reproduction_runner_sha256", digest(Path(__file__))),
        ):
            if obj[field] != expected:
                raise RuntimeError(f"Pilot parity checkpoint is stale: {stage}/{field}")
        payload[stage] = digest(path)
    freeze("gate", {
        "decision": "PASS",
        "pilot_stages_sha256": payload,
        "transfer_code_sha256": digest(TRANSFER_CODE),
        "reproduction_runner_sha256": digest(Path(__file__)),
        "transfer_core_sha256": digest(TRANSFER_CORE),
        "scope": "exact archived pilot design/CV/support/scoring and matched-seed native G0",
        "not_a_new_test_of_battery_accuracy": True,
    })
    print("B1_PILOT_M3_REPRODUCTION_GATE_PASS")
    print("Pilot-only gate now permits starting the new battery transfer.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage", required=True,
        choices=("preflight", "deterministic", "archived-scoring",
                 "graph-smoke", "full-graph", "seal"),
    )
    parser.add_argument("--max-trajectories", type=int, default=0,
                        help="Optional bounded full-graph checkpoint, 0=all 1400")
    args = parser.parse_args()
    if args.max_trajectories < 0 or args.max_trajectories > 1400:
        parser.error("max-trajectories must be 0..1400")
    if args.stage == "preflight":
        check_inputs()
    elif args.stage == "deterministic":
        deterministic()
    elif args.stage == "archived-scoring":
        archived_scoring()
    elif args.stage == "graph-smoke":
        graph_smoke()
    elif args.stage == "full-graph":
        full_graph(max_trajectories=args.max_trajectories)
    elif args.stage == "seal":
        seal()


if __name__ == "__main__":
    main()
