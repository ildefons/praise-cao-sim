#!/usr/bin/env python3
"""Parallel scheduling adapter for the original pilot B1400 native G0 -> G_PAR replay.

Scientific inputs, simulation function, request-level parity tolerances, graph
seeds, and archived ledgers are identical to the original reproduction gate.
Original gate code and all Phase-4/5 science results remain unchanged.

Previously checked original-format per-seed checkpoints are reused. After all
1,400 are present, the original gate.full_graph() validates and seals its own
canonical full_graph.json stage. This adapter never writes a PASS stage itself.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import fcntl
import os
import time
import warnings
from pathlib import Path

import pandas as pd

import run_pilot_m3_reproduction_gate_v1 as gate


_WORKER = {}
_ARCHIVE_CACHE = {}


def checkpoint_path(rank: int, seed: int) -> Path:
    return gate.OUT / "native_full" / f"rank_{rank:02d}" / f"seed_{seed}.json"


def verified_cache(rank, seed, source_sha, pilot_sha, runner_sha):
    path = checkpoint_path(rank, seed)
    if not path.exists():
        return False
    old = gate.read(path)
    if not (
        old.get("rank") == rank
        and old.get("seed") == seed
        and int(old.get("requests", 0)) > 0
        and old.get("archived_rank_ledger_sha256") == source_sha
        and old.get("pilot_graph_contract_sha256") == pilot_sha
        and old.get("reproduction_runner_sha256") == runner_sha
        and old.get("matched_original_native_G0_with_new_G_PAR_runtime") is True
    ):
        raise RuntimeError(f"Stale or invalid native graph checkpoint: {path}")
    return True


def init_worker(models, graph_ast, graph_invariants, period, ipt, fraction):
    # The original bridge sets the necessary PRAISE-modified YAFS path before
    # importing the same underlying native Phase-5 simulator as the gate.
    from audit_original_world_bridge_v1 import (
        GraphProviderSurrogate, execute_one_phase5_graph_trajectory,
    )
    _WORKER.clear()
    _WORKER.update({
        "models": {
            rank: {
                provider: GraphProviderSurrogate(
                    mean_service_time=values["mean_service_time"],
                    cost_rate=values["cost_rate"],
                    service_cv=values["service_cv"],
                )
                for provider, values in by_provider.items()
            }
            for rank, by_provider in models.items()
        },
        "simulate": execute_one_phase5_graph_trajectory,
        "graph_ast": graph_ast,
        "invariants": graph_invariants,
        "period": period,
        "ipt": ipt,
        "fraction": fraction,
    })
    _ARCHIVE_CACHE.clear()


def simulate_and_verify(task):
    """One pilot seed, unchanged inputs and the original gate parity function."""
    rank, seed, source_sha, pilot_sha, runner_sha = task
    path = checkpoint_path(rank, seed)
    if path.exists():
        raise RuntimeError(f"Concurrent checkpoint writer or stale schedule: {path}")

    if rank not in _ARCHIVE_CACHE:
        source = gate.PILOT / "ledgers" / f"M3Q_R{rank:02d}.csv"
        if gate.digest(source) != source_sha:
            raise RuntimeError(f"Archived ledger changed: {source}")
        _ARCHIVE_CACHE[rank] = pd.read_csv(source)
    original = _ARCHIVE_CACHE[rank]
    archived_one = original.loc[original["trajectory_seed"].astype(int).eq(seed)]
    if archived_one.empty:
        raise RuntimeError(f"Original pilot trajectory missing: rank {rank}, seed {seed}")

    with warnings.catch_warnings(), open(os.devnull, "w") as null:
        warnings.simplefilter("ignore", FutureWarning)
        with contextlib.redirect_stdout(null):
            new, _ = _WORKER["simulate"](
                graph_id="G_PAR",
                graph_ast=_WORKER["graph_ast"],
                graph_invariants=_WORKER["invariants"],
                provider_surrogates=_WORKER["models"][rank],
                workload_period=_WORKER["period"],
                stop_time=240.0,
                trajectory_seed=seed,
                canonical_ipt=_WORKER["ipt"],
                execution_fraction=_WORKER["fraction"],
            )
    count = gate._matched_trajectory(archived_one, new, rank=rank, seed=seed)
    payload = {
        "rank": rank, "seed": seed, "requests": count,
        "archived_rank_ledger_sha256": source_sha,
        "pilot_graph_contract_sha256": pilot_sha,
        "reproduction_runner_sha256": runner_sha,
        "matched_original_native_G0_with_new_G_PAR_runtime": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        if path.exists():
            raise RuntimeError(f"Concurrent checkpoint writer detected: {path}")
        tmp.write_text(__import__("json").dumps(payload, indent=2) + "\n",
                       encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return rank, seed


def _validated_inputs():
    for name in ("deterministic", "local_replay", "archived_scoring", "graph_smoke"):
        path = gate.OUT / (name + ".json")
        if not path.is_file():
            raise RuntimeError(f"Missing original pilot stage: {path}")
        recorded = gate.read(path)
        if recorded.get("status") != f"B1_PILOT_REPRODUCTION_{name.upper()}_PASS":
            raise RuntimeError(f"Unsuccessful original pilot stage: {name}")
        for field, source in (
            ("pilot_graph_contract_sha256", gate.PILOT_CORE),
            ("pilot_cv_contract_sha256", gate.PILOT_CV),
            ("transfer_contract_sha256", gate.CONFIG),
            ("reproduction_runner_sha256", Path(gate.__file__)),
        ):
            if recorded.get(field) != gate.digest(source):
                raise RuntimeError(f"Stale original pilot stage: {name}/{field}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-trajectories", type=int, default=0,
                        help="Check only the first N original seeds (0 = all 1,400)")
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be 1..16")
    if not 0 <= args.max_trajectories <= 1400:
        parser.error("--max-trajectories must be 0..1400")

    gate.check_inputs()
    _validated_inputs()
    gate.OUT.mkdir(parents=True, exist_ok=True)
    lockfile = gate.OUT / "native_full_parallel_v1.lock"
    with lockfile.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another parallel graph replay is running") from exc

        design = pd.read_csv(
            gate.PILOT / "m3_v4_dominant_design.csv"
        ).sort_values("rank", kind="mergesort")
        weights = pd.read_csv(gate.CVROOT / "m3_v3_provider_weights.csv")
        if len(design) != 14 or int(design["n_B1400"].sum()) != 1400:
            raise RuntimeError("Original pilot Top14/B1400 contract mismatch")
        if len(weights) != 144:
            raise RuntimeError("Expected exactly 144 original pilot provider weights")

        # Same original G_PAR configuration and graph invariants as gate.full_graph.
        phase5 = gate.read(gate.P5 / "config_phase5_recoverability_battery_v2.json")
        graph = next(g for g in phase5["graphs"] if g["id"] == "G_PAR")
        family = phase5["provider_family"]
        invariants = dict(phase5["graph_invariants"])
        invariants["effective_IPT"] = float(family["effective_IPT"])
        invariants["cost_rate"] = float(family["cost_rate"])
        legacy = gate.read(gate.P3 / "config_phase3_m1_contract_v2.json")
        closure = legacy["fixed_closure_conventions"]
        sim = gate.read(gate.PILOT_CORE)["simulation_budget"]
        if sim["seed_base"] != 3600000 or sim["seed_block_stride"] != 10000:
            raise RuntimeError("Original pilot graph seed contract changed")
        from run_m1_provider_lift_v2 import load_verified_public_i1_cards
        public_meta, _, _ = load_verified_public_i1_cards(gate.PHASE2_CARD)
        period = float(public_meta["ProviderA"]["workload_contract"]["period"])

        models = {}
        seeds = []
        rank_sources = {}
        for row in design.itertuples(index=False):
            rank = int(row.rank)
            rank_file = gate.PILOT / "ledgers" / f"M3Q_R{rank:02d}.csv"
            rank_sources[rank] = gate.digest(rank_file)
            by_provider = {}
            for provider in gate.PROVIDERS:
                candidate_id = str(getattr(row, provider + "_candidate_id"))
                matches = weights.loc[
                    weights["provider"].astype(str).eq(provider)
                    & weights["candidate_id"].astype(str).eq(candidate_id)
                ]
                if len(matches) != 1:
                    raise RuntimeError(f"Missing pilot hypothesis: {provider}/{candidate_id}")
                item = matches.iloc[0]
                by_provider[provider] = {
                    field: float(item[field])
                    for field in ("mean_service_time", "cost_rate", "service_cv")
                }
            models[rank] = by_provider
            seeds.extend(
                (rank, int(row.seed_start) + offset)
                for offset in range(int(row.n_B1400))
            )
        if len(seeds) != 1400 or len(set(seeds)) != 1400:
            raise RuntimeError("Original pilot B1400 seed schedule invalid")

        target = seeds[:args.max_trajectories] if args.max_trajectories else seeds
        pilot_sha = gate.digest(gate.PILOT_CORE)
        runner_sha = gate.digest(Path(gate.__file__))
        cached = 0
        tasks = []
        for rank, seed in target:
            if verified_cache(
                rank, seed, rank_sources[rank], pilot_sha, runner_sha
            ):
                cached += 1
            else:
                tasks.append((rank, seed, rank_sources[rank], pilot_sha, runner_sha))
        n = len(target)
        print(f"PILOT FULL GRAPH PARALLEL: {n}/1400 targeted, {cached} verified "
              f"cached, {len(tasks)} to simulate, workers={args.workers}",
              flush=True)
        started = time.monotonic()
        if tasks:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=args.workers,
                initializer=init_worker,
                initargs=(
                    models, graph["ast"], invariants, period,
                    float(closure["canonical_IPT"]),
                    float(legacy["pilot_scope"]["execution_fraction"]),
                ),
            ) as pool:
                futures = [pool.submit(simulate_and_verify, task) for task in tasks]
                completed = 0
                try:
                    for future in concurrent.futures.as_completed(futures):
                        future.result()  # propagate the exact request-parity failure
                        completed += 1
                        if (completed == 1 or completed % 25 == 0
                                or completed == len(tasks)):
                            print(
                                f"PILOT FULL GRAPH PARALLEL: "
                                f"{cached + completed}/{n} verified "
                                f"({completed} new, {cached} reused); "
                                f"elapsed {time.monotonic()-started:.1f}s",
                                flush=True,
                            )
                except BaseException:
                    for future in futures:
                        future.cancel()
                    raise

        # The original script is the sole authority for final full_graph.json.
        gate.full_graph(max_trajectories=args.max_trajectories)
        print("PILOT_FULL_GRAPH_PARALLEL_CHECKPOINTS_VERIFIED", flush=True)


if __name__ == "__main__":
    main()
