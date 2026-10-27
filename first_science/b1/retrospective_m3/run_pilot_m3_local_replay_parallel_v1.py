#!/usr/bin/env python3
"""Four-worker-capable replay of ORIGINAL pilot provider-local M3 candidates.

This is a scheduling adapter, NOT a new scientific method. It preserves the
September pilot inputs, simulator, trajectories, comparison, and checkpoint
format of run_pilot_m3_reproduction_gate_v1.py. In particular, that original
script remains unchanged, so previously verified checkpoints stay valid.

When all 144 candidates exist, the ORIGINAL local_replay() verifies every
checkpoint and writes its standard local_replay.json PASS record.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

import run_pilot_m3_reproduction_gate_v1 as gate

_WORKER_PUBLIC = None


def _initialize_worker():
    """Load the frozen original public cards once per worker process."""
    global _WORKER_PUBLIC
    from run_m1_provider_lift_v2 import load_verified_public_i1_cards

    meta, surfaces, _ = load_verified_public_i1_cards(gate.PHASE2_CARD)
    _WORKER_PUBLIC = (meta, surfaces)


def _checkpoint_path(provider, candidate_id):
    return gate.OUT / "local_replay" / provider / (candidate_id + ".json")


def _archive_path(candidate_id):
    return gate.LOCAL / "local_surfaces" / (candidate_id + "_comparison.csv")


def _verify_cached(provider, candidate_id, runner_hash):
    """Fail closed on stale/mismatched checkpoints; never silently replace."""
    path = _checkpoint_path(provider, candidate_id)
    if not path.exists():
        return False
    archive = _archive_path(candidate_id)
    old = gate.read(path)
    if not (
        old.get("provider") == provider
        and old.get("candidate_id") == candidate_id
        and old.get("original_candidate_curve_sha256") == gate.digest(archive)
        and old.get("reproduction_runner_sha256") == runner_hash
        and old.get("matched_original_local_curve") is True
        and int(old.get("n_local_seeds", -1)) == 100
        and float(old.get("max_abs_probability_diff", float("inf"))) <= 1e-12
    ):
        raise RuntimeError(f"Stale or incompatible original replay checkpoint: {path}")
    return True


def _score_one(record):
    """Worker: same _simulate_and_score inputs and parity test as original gate."""
    if _WORKER_PUBLIC is None:
        raise RuntimeError("Worker public I1 cards were not initialized")
    from run_m1_provider_lift_v2 import _simulate_and_score

    provider = str(record["provider"])
    candidate_id = str(record["candidate_id"])
    meta, surfaces = _WORKER_PUBLIC
    legacy = gate.read(gate.P3 / "config_phase3_m1_contract_v2.json")
    ipt = float(legacy["fixed_closure_conventions"]["canonical_IPT"])
    fraction = float(legacy["pilot_scope"]["execution_fraction"])

    original = _archive_path(candidate_id)
    source_hash = gate.digest(original)
    _metrics, _simulated, new = _simulate_and_score(
        metadata=meta[provider],
        public_surface=surfaces[provider],
        mean_service_time=float(record["mean_service_time"]),
        cost_rate=float(record["cost_rate"]),
        service_cv=float(record["service_cv"]),
        trajectory_seeds=tuple(range(35000, 35100)),
        canonical_ipt=ipt,
        execution_fraction=fraction,
        quiet=True,
    )
    archived = pd.read_csv(original)
    keys = ["provider_id", "region_id", "horizon", "region_rho", "rho"]
    fields = ["sigma_i1", "sigma_m1_local"]
    for frame in (new, archived):
        if not set(keys + fields).issubset(frame.columns):
            raise RuntimeError(f"Local curve columns differ for {candidate_id}")
        if frame.duplicated(keys).any():
            raise RuntimeError(f"Duplicate local prediction keys for {candidate_id}")
    pair = new[keys + fields].merge(
        archived[keys + fields], on=keys, validate="one_to_one",
        suffixes=("_replay", "_archive"),
    )
    if len(pair) != len(archived) or len(pair) != len(new):
        raise RuntimeError(f"Local curve query support differs for {candidate_id}")
    delta = max(
        float(abs(pair[field + "_replay"] - pair[field + "_archive"]).max())
        for field in fields
    )
    if not np.isfinite(delta) or delta > 1e-12:
        raise RuntimeError(f"Pilot local simulation mismatch {candidate_id}: {delta}")

    destination = _checkpoint_path(provider, candidate_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": provider, "candidate_id": candidate_id,
        "scored_points": len(pair), "n_local_seeds": 100,
        "max_abs_probability_diff": delta,
        "original_candidate_curve_sha256": source_hash,
        "reproduction_runner_sha256": gate.digest(Path(gate.__file__)),
        "matched_original_local_curve": True,
    }
    tmp = destination.with_name(destination.name + f".{os.getpid()}.tmp")
    try:
        if destination.exists():
            raise RuntimeError(f"Concurrent checkpoint writer detected: {destination}")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, destination)
    finally:
        tmp.unlink(missing_ok=True)
    return candidate_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--max-candidates", type=int, default=0,
        help="First N original candidates (0=all 144); for a 4-worker smoke use 7",
    )
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    if not 0 <= args.max_candidates <= 144:
        parser.error("--max-candidates must be between 0 and 144")

    gate.check_inputs()
    deterministic = gate.OUT / "deterministic.json"
    if not deterministic.exists():
        raise RuntimeError("Run the original --stage deterministic first")
    d = gate.read(deterministic)
    if (
        d.get("status") != "B1_PILOT_REPRODUCTION_DETERMINISTIC_PASS"
        or d.get("reproduction_runner_sha256") != gate.digest(Path(gate.__file__))
    ):
        raise RuntimeError("Original deterministic reproduction checkpoint is stale")

    gate.OUT.mkdir(parents=True, exist_ok=True)
    lock = gate.OUT / "local_replay_parallel_v1.lock"
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another parallel pilot replay is running") from exc

        design = pd.read_csv(gate.DESIGN).sort_values(
            ["provider", "lhs_index"], kind="mergesort"
        ).reset_index(drop=True)
        if len(design) != 144:
            raise RuntimeError("Original pilot candidate design must contain 144 rows")
        selected = design.iloc[:args.max_candidates] if args.max_candidates else design
        runner_hash = gate.digest(Path(gate.__file__))
        pending = []
        cached = 0
        for record in selected.to_dict("records"):
            provider, cid = str(record["provider"]), str(record["candidate_id"])
            if _verify_cached(provider, cid, runner_hash):
                cached += 1
            else:
                if not _archive_path(cid).is_file():
                    raise FileNotFoundError(_archive_path(cid))
                pending.append(record)

        n = len(selected)
        print(
            f"PILOT LOCAL PARALLEL: {n}/144 targeted, {cached} verified cached, "
            f"{len(pending)} to simulate, workers={args.workers}",
            flush=True,
        )
        if pending:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=args.workers, initializer=_initialize_worker
            ) as pool:
                futures = [pool.submit(_score_one, record) for record in pending]
                completed = 0
                try:
                    for future in concurrent.futures.as_completed(futures):
                        future.result()  # propagate any scientific parity failure
                        completed += 1
                        if completed == 1 or completed % 4 == 0 or completed == len(pending):
                            print(
                                f"PILOT LOCAL PARALLEL: {cached + completed}/{n} complete "
                                f"({completed} new, {cached} reused)",
                                flush=True,
                            )
                except BaseException:
                    for future in futures:
                        future.cancel()
                    raise

        # Canonical serial validator reads all cached outputs and freezes only
        # when every one of the original 144 models has passed the same checks.
        gate.local_replay(max_candidates=args.max_candidates)
        print("PILOT_LOCAL_PARALLEL_REPLAY_CHECKPOINTS_VERIFIED", flush=True)


if __name__ == "__main__":
    main()
