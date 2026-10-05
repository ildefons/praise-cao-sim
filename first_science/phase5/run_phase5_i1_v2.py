"""Official Phase-5 V2 public-I1 acquisition and materialization.

This stage is the first scientific execution in Phase 5.  For each provider
world it acquires two disjoint N=100 provider-local evidence corpora under the
frozen W0/ParAll acquisition mechanics:

    T_i^Gamma -> construct nested A_i(rho_region)
    T_i^sigma -> estimate public sigma_i(A_i,H;rho_query)

The same resulting public cards are reused across all four Phase-5 graph
structures.  This is intentional: downstream graph-induced workload shift is
part of the held-out topology test, not part of provider-card acquisition.

Only provider-local evidence survives each native trajectory.  Full native
traces and top-level white-box ledgers live in TemporaryDirectory and are
deleted after extraction.

The script is resumable at trajectory granularity.  It never overwrites a
completed frozen world unless --reset-world is explicitly supplied.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE1 = FIRST_SCIENCE / "phase1"
PHASE2 = FIRST_SCIENCE / "phase2"
for path in (PHASE1, PHASE2):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from whitebox_atlas import (  # noqa: E402
    PROVIDER_MODULES,
    execute_one_whitebox_trajectory,
)
from i1_provider_acquisition import (  # noqa: E402
    extract_provider_local_ledgers_from_metric_rows,
)
from i1_provider_card import (  # noqa: E402
    assert_public_i1_card_has_no_forbidden_information,
    build_i1_provider_card,
    write_i1_provider_card,
)
from i1_rho_conditioned_card import (  # noqa: E402
    load_rho_conditioned_i1_provider_card,
)
from i1_rho_conditioned_region import derive_nested_rho_regions  # noqa: E402
from yafs.stats import Stats  # noqa: E402

from phase5_runtime_v2 import (  # noqa: E402
    base_manifest,
    canonical_provider_world_ids,
    inclusive_seed_range,
    load_phase5_contracts,
    provider_world,
    read_json,
    sha256_file,
    utc_now_iso,
    write_json,
)

DEFAULT_RESULT_ROOT = HERE / "results" / "01_i1"
PHASE1_CONFIG = PHASE1 / "config_phase1_discovery_v1.json"
I1_CARD_CONTRACT = PHASE2 / "config_phase2_i1_provider_card_v3_rho_conditioned.json"

EXPECTED_PUBLIC_SCHEMA = "PRAISE_I1_PROVIDER_RHO_CONDITIONED_CARD_V1"


def _assert_phase1_matches_phase5(phase1: Mapping[str, Any], contracts) -> None:
    battery = contracts.battery
    workload = battery["workload"]
    family = battery["provider_family"]
    invariants = battery["graph_invariants"]

    checks = [
        (
            float(phase1["workload"]["period"]),
            float(workload["period_seconds"]),
            "workload period",
        ),
        (
            float(phase1["horizon"]["simulation_stop_time"]),
            float(battery["horizon"]["maximum_seconds"]),
            "simulation stop",
        ),
        (
            float(phase1["provider_family"]["instruction_cv"]),
            float(family["instruction_cv"]),
            "provider CV",
        ),
        (
            float(phase1["provider_family"]["effective_ipt"]),
            float(family["effective_IPT"]),
            "provider IPT",
        ),
        (
            float(phase1["provider_family"]["cost_rate"]),
            float(family["cost_rate"]),
            "provider cost rate",
        ),
        (
            float(phase1["provider_family"]["x"]),
            float(family["execution_fraction_x"]),
            "execution fraction",
        ),
        (
            float(phase1["topology"]["network_bw_mbps"]),
            float(invariants["network_bw_mbps"]),
            "network bandwidth",
        ),
        (
            float(phase1["topology"]["network_pr"]),
            float(invariants["network_pr_seconds"]),
            "network propagation",
        ),
        (
            float(phase1["graph"]["pre_instructions"]),
            float(invariants["Fpre_instructions"]),
            "Fpre instructions",
        ),
        (
            float(phase1["graph"]["post_instructions"]),
            float(invariants["Fpost_instructions"]),
            "Fpost instructions",
        ),
    ]
    for old, new, label in checks:
        if abs(old - new) > 1e-12 * max(1.0, abs(old), abs(new)):
            raise RuntimeError(
                f"Phase-1 acquisition mechanic drift in {label}: {old} != {new}"
            )


def _card_contract() -> dict[str, Any]:
    contract = read_json(I1_CARD_CONTRACT)
    if contract.get("status") != "PHASE2_I1_RHO_CONDITIONED_CONTRACT_V1":
        raise RuntimeError("unexpected rho-conditioned I1 card contract")
    return contract


def _trajectory_checkpoint_paths(
    world_root: Path,
    *,
    role: str,
    seed: int,
) -> dict[str, Path]:
    base = world_root / "private" / "checkpoints" / role / f"seed_{seed}"
    return {
        provider: base / f"{provider}.csv" for provider in PROVIDER_MODULES
    }


def _checkpoint_complete(paths: Mapping[str, Path]) -> bool:
    return all(path.is_file() for path in paths.values())


def _acquire_one_trajectory(
    *,
    phase1_configuration: dict[str, Any],
    world: Mapping[str, Any],
    seed: int,
    trajectory_ordinal: int,
    checkpoint_paths: Mapping[str, Path],
) -> None:
    with tempfile.TemporaryDirectory(
        prefix=f"praise_phase5_i1_{world['id']}_{seed}_"
    ) as temporary_name:
        temporary = Path(temporary_name)
        execute_one_whitebox_trajectory(
            phase1_configuration,
            center_instruction_mean=float(world["D_instructions"]),
            dispersion=float(world["delta"]),
            trajectory_seed=int(seed),
            trajectory_output_directory=temporary,
        )
        metric_rows = Stats(defaultPath=str(temporary / "sim_trace")).df.copy()
        provider_ledgers = extract_provider_local_ledgers_from_metric_rows(
            metric_rows,
            phase1_configuration,
            trajectory=int(trajectory_ordinal),
            stop_time=float(
                phase1_configuration["horizon"]["simulation_stop_time"]
            ),
        )

    # The TemporaryDirectory is already gone here.  Persist only provider-local
    # ledgers needed by I1.
    for provider, path in checkpoint_paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        frame = provider_ledgers[provider].copy()
        frame.insert(0, "trajectory_seed_private", int(seed))
        frame.to_csv(path, index=False)


def _acquire_corpus(
    *,
    phase1_configuration: dict[str, Any],
    world: Mapping[str, Any],
    world_root: Path,
    role: str,
    seeds: tuple[int, ...],
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    started = time.perf_counter()
    already_complete = sum(
        1
        for seed in seeds
        if _checkpoint_complete(
            _trajectory_checkpoint_paths(
                world_root, role=role, seed=int(seed)
            )
        )
    )
    newly_run = 0
    if already_complete:
        print(
            f"{world['id']} {role}: resuming with "
            f"{already_complete}/{len(seeds)} checkpoints already complete",
            flush=True,
        )

    for ordinal, seed in enumerate(seeds):
        paths = _trajectory_checkpoint_paths(
            world_root,
            role=role,
            seed=int(seed),
        )
        if _checkpoint_complete(paths):
            continue
        # Never accept a partially written trajectory checkpoint.
        for path in paths.values():
            if path.exists():
                path.unlink()
        _acquire_one_trajectory(
            phase1_configuration=phase1_configuration,
            world=world,
            seed=int(seed),
            trajectory_ordinal=int(ordinal),
            checkpoint_paths=paths,
        )
        newly_run += 1
        completed_now = sum(
            1
            for candidate_seed in seeds
            if _checkpoint_complete(
                _trajectory_checkpoint_paths(
                    world_root,
                    role=role,
                    seed=int(candidate_seed),
                )
            )
        )
        if completed_now % 10 == 0 or newly_run == 1 or completed_now == len(seeds):
            elapsed = time.perf_counter() - started
            sec_per_new = elapsed / max(1, newly_run)
            remaining = len(seeds) - completed_now
            eta_seconds = sec_per_new * remaining
            print(
                f"{world['id']} {role}: "
                f"{completed_now}/{len(seeds)} trajectories complete | "
                f"elapsed={elapsed/60.0:.1f} min | "
                f"avg={sec_per_new:.2f} s/traj | "
                f"ETA={eta_seconds/60.0:.1f} min",
                flush=True,
            )

    ledgers: dict[str, pd.DataFrame] = {}
    private_root = world_root / "private" / role
    private_root.mkdir(parents=True, exist_ok=True)
    provider_hashes: dict[str, str] = {}
    provider_rows: dict[str, int] = {}
    provider_trajectories: dict[str, int] = {}

    for provider in PROVIDER_MODULES:
        pieces: list[pd.DataFrame] = []
        for ordinal, seed in enumerate(seeds):
            path = _trajectory_checkpoint_paths(
                world_root,
                role=role,
                seed=int(seed),
            )[provider]
            if not path.is_file():
                raise RuntimeError(
                    f"missing completed checkpoint {role}/{seed}/{provider}"
                )
            piece = pd.read_csv(path)
            expected_seed = set(piece["trajectory_seed_private"].astype(int))
            if expected_seed != {int(seed)}:
                raise RuntimeError(
                    f"{world['id']} {role} {provider}: seed checkpoint mismatch"
                )
            if set(piece["trajectory"].astype(int)) != {int(ordinal)}:
                raise RuntimeError(
                    f"{world['id']} {role} {provider}: trajectory ordinal mismatch"
                )
            pieces.append(piece)

        merged = pd.concat(pieces, ignore_index=True)
        if int(merged["trajectory"].nunique()) != len(seeds):
            raise RuntimeError(
                f"{world['id']} {role} {provider}: incomplete trajectory set"
            )
        if merged[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(
                f"{world['id']} {role} {provider}: duplicate request rows"
            )

        # Seed is private acquisition provenance, not part of the provider
        # evidence schema supplied to card construction.
        evidence = merged.drop(columns=["trajectory_seed_private"])
        provider_dir = private_root / provider
        provider_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = provider_dir / "provider_request_ledgers.csv"
        evidence.to_csv(ledger_path, index=False)
        ledgers[provider] = evidence
        provider_hashes[provider] = sha256_file(ledger_path)
        provider_rows[provider] = int(len(evidence))
        provider_trajectories[provider] = int(
            evidence["trajectory"].nunique()
        )

    manifest = {
        "status": (
            "FROZEN_PHASE5_I1_REGION_EVIDENCE_V2"
            if role == "region"
            else "FROZEN_PHASE5_I1_SIGMA_EVIDENCE_V2"
        ),
        "stage_id": "I1",
        "provider_world_id": str(world["id"]),
        "corpus_role": (
            "region_construction_only"
            if role == "region"
            else "sigma_estimation_only"
        ),
        "n_trajectories": len(seeds),
        "seed_bank_private": list(map(int, seeds)),
        "provider_sha256": provider_hashes,
        "provider_rows": provider_rows,
        "provider_trajectories": provider_trajectories,
        "graph_acquisition_semantics": (
            "frozen W0 G_PAR acquisition mechanics; same public cards are "
            "reused across every Phase-5 graph"
        ),
        "hidden_world_private": {
            "D_instructions": int(world["D_instructions"]),
            "delta": float(world["delta"]),
            "provider_means": dict(world["provider_means"]),
        },
        "python_wall_seconds": float(time.perf_counter() - started),
    }
    return ledgers, manifest


def _materialize_public_cards(
    *,
    world_id: str,
    world_root: Path,
    region_ledgers: Mapping[str, pd.DataFrame],
    sigma_ledgers: Mapping[str, pd.DataFrame],
) -> tuple[dict[str, Any], list[Path]]:
    contract = _card_contract()
    horizons = [float(x) for x in contract["H"]["values"]]
    region_rhos = [float(x) for x in contract["region_rho"]["values"]]
    query_rhos = [float(x) for x in contract["query_rho"]["values"]]
    workload = dict(contract["workload_contract"])
    model = dict(contract["joint_model"])

    public_root = world_root / "public"
    audit_root = world_root / "private" / "region_fit_audit"
    public_root.mkdir(parents=True, exist_ok=True)
    audit_root.mkdir(parents=True, exist_ok=True)

    cards: dict[str, Any] = {}
    public_files: list[Path] = []

    for provider_index, provider in enumerate(PROVIDER_MODULES):
        provider_seed = int(model["random_state"]) + 1000 * provider_index
        regions, audit = derive_nested_rho_regions(
            region_ledgers[provider],
            region_rhos,
            max_components=int(model["max_components"]),
            model_samples=int(model["model_samples"]),
            random_state=provider_seed,
        )
        audit_path = audit_root / f"{provider}_rho_conditioned_region_fit.csv"
        audit.to_csv(audit_path, index=False)

        metadata, surface = build_i1_provider_card(
            provider_id=provider,
            private_provider_ledgers=sigma_ledgers[provider],
            local_regions=regions,
            rho_values=query_rhos,
            horizons=horizons,
            stop_time=float(workload["horizon_max"]),
            workload_contract={
                "period": float(workload["period"]),
                "accounting_origin": float(workload["accounting_origin"]),
                "horizon_max": float(workload["horizon_max"]),
            },
        )

        region_rho_by_id = {
            str(region["region_id"]): float(region["region_rho"])
            for region in regions
        }
        surface.insert(
            surface.columns.get_loc("region_id") + 1,
            "region_rho",
            surface["region_id"].map(region_rho_by_id).astype(float),
        )

        # Public metadata deliberately contains no provider-world identifier or
        # hidden generating parameter.
        metadata["schema"] = EXPECTED_PUBLIC_SCHEMA
        metadata["information_technology"] = str(
            contract["information_technology"]
        )
        metadata["card_instance"] = (
            "I1_i=({A_i(rho_region)},W_i,R_region,R_query,"
            "{sigma_i(A_i(rho_region),H;rho_query)})"
        )
        metadata["rho_conditioned_regions"] = [dict(x) for x in regions]
        metadata["supported_region_rho_values"] = region_rhos
        metadata["supported_query_rho_values"] = query_rhos
        metadata["construction"] = {
            "status": "JOINT_LOG_GMM_MIN_AREA_RHO_REGION_V1",
            "joint_coordinates": ["log_L", "log_C"],
            "quality_rule": "constant_Q_is_preserved_exactly",
            "component_selection": "minimum_BIC",
            "max_components": int(model["max_components"]),
            "covariance_type": "full",
            "model_samples": int(model["model_samples"]),
            "nested_regions": True,
            "finite_region_rho_requires_rho_less_than_1": True,
            "phase1_whitebox_used": False,
            "region_and_sigma_evidence_are_trajectory_disjoint": True,
            "region_fit_evidence": "private_T_i^Gamma",
            "sigma_estimation_evidence": "independent_private_T_i^sigma",
        }
        metadata["query_semantics"] = (
            "exact_materialized_A_i_of_rho_region_H_rho_query_points_v2"
        )
        assert_public_i1_card_has_no_forbidden_information(
            metadata, surface
        )

        card_dir = public_root / provider
        card_path, surface_path = write_i1_provider_card(
            metadata,
            surface,
            card_dir,
        )
        reloaded_metadata, reloaded_surface = (
            load_rho_conditioned_i1_provider_card(card_dir)
        )
        if str(reloaded_metadata["provider_id"]) != provider:
            raise RuntimeError(f"{provider}: public-card reload mismatch")
        expected_points = (
            len(region_rhos) * len(query_rhos) * len(horizons)
        )
        if len(reloaded_surface) != expected_points:
            raise RuntimeError(
                f"{provider}: expected {expected_points} public points, "
                f"found {len(reloaded_surface)}"
            )

        cards[provider] = {
            "directory": provider,
            "rho_conditioned_regions": [dict(x) for x in regions],
            "n_surface_points": int(len(surface)),
            "card_json_sha256": sha256_file(card_path),
            "sigma_surface_sha256": sha256_file(surface_path),
        }
        public_files.extend([card_path, surface_path])

    public_manifest = {
        "status": "FROZEN_PHASE5_PUBLIC_I1_CARDS_V2",
        "provider_world_id_private_container": str(world_id),
        "public_card_payloads_contain_hidden_world_parameters": False,
        "schema": EXPECTED_PUBLIC_SCHEMA,
        "same_cards_reused_across_all_four_graphs": True,
        "region_and_sigma_evidence_disjoint": True,
        "H": horizons,
        "region_rho": region_rhos,
        "query_rho": query_rhos,
        "cards": cards,
    }
    public_manifest_path = public_root / "i1_rho_conditioned_manifest_v2.json"
    write_json(public_manifest_path, public_manifest)
    public_files.append(public_manifest_path)
    return public_manifest, public_files


def run_world(
    world_id: str,
    *,
    result_root: Path,
    reset_world: bool,
) -> None:
    contracts = load_phase5_contracts(HERE)
    world = provider_world(contracts, world_id)
    world_root = result_root.resolve() / str(world_id)
    final_manifest_path = world_root / "i1_freeze_manifest.json"

    if final_manifest_path.is_file() and not reset_world:
        raise RuntimeError(
            f"{world_id} I1 is already frozen at {final_manifest_path}; "
            "refusing to overwrite scientific evidence"
        )
    if reset_world and world_root.exists():
        shutil.rmtree(world_root)

    started = utc_now_iso()
    world_wall_started = time.perf_counter()
    phase1 = read_json(PHASE1_CONFIG)
    _assert_phase1_matches_phase5(phase1, contracts)

    region_block = contracts.seeds["public_I1"][world_id]["region"]
    sigma_block = contracts.seeds["public_I1"][world_id]["sigma"]
    region_seeds = inclusive_seed_range(region_block)
    sigma_seeds = inclusive_seed_range(sigma_block)
    if set(region_seeds).intersection(sigma_seeds):
        raise RuntimeError("region and sigma I1 seed banks overlap")

    print(
        f"PHASE5_I1_START world={world_id} "
        f"region={region_seeds[0]}..{region_seeds[-1]} "
        f"sigma={sigma_seeds[0]}..{sigma_seeds[-1]}",
        flush=True,
    )

    region_ledgers, region_manifest = _acquire_corpus(
        phase1_configuration=phase1,
        world=world,
        world_root=world_root,
        role="region",
        seeds=region_seeds,
    )
    region_manifest_path = world_root / "i1_region_evidence_manifest.json"
    write_json(region_manifest_path, region_manifest)

    sigma_ledgers, sigma_manifest = _acquire_corpus(
        phase1_configuration=phase1,
        world=world,
        world_root=world_root,
        role="sigma",
        seeds=sigma_seeds,
    )
    sigma_manifest_path = world_root / "i1_sigma_evidence_manifest.json"
    write_json(sigma_manifest_path, sigma_manifest)

    public_manifest, public_files = _materialize_public_cards(
        world_id=world_id,
        world_root=world_root,
        region_ledgers=region_ledgers,
        sigma_ledgers=sigma_ledgers,
    )

    # Checkpoint files are no longer needed after both immutable merged corpora
    # and public cards exist.  Removing them avoids duplicate private evidence.
    checkpoints = world_root / "private" / "checkpoints"
    if checkpoints.exists():
        shutil.rmtree(checkpoints)

    output_map = {
        "i1_region_evidence_manifest": str(region_manifest_path),
        "i1_sigma_evidence_manifest": str(sigma_manifest_path),
        "public_manifest": str(
            world_root / "public" / "i1_rho_conditioned_manifest_v2.json"
        ),
    }
    manifest = base_manifest(
        contracts,
        stage_id="I1",
        status="FROZEN_PHASE5_I1_COMPLETE_V2",
        inputs={
            "provider_world_id": world_id,
            "phase1_acquisition_mechanics_sha256": sha256_file(PHASE1_CONFIG),
            "phase2_rho_conditioned_card_contract_sha256": sha256_file(
                I1_CARD_CONTRACT
            ),
            "same_public_cards_reused_across_graphs": True,
            "acquisition_graph_semantics": "G_PAR/W0 only",
            "public_card_payloads_contain_hidden_world_parameters": False,
        },
        seed_banks={
            "region": {
                "start": int(region_seeds[0]),
                "end_inclusive": int(region_seeds[-1]),
                "n": len(region_seeds),
            },
            "sigma": {
                "start": int(sigma_seeds[0]),
                "end_inclusive": int(sigma_seeds[-1]),
                "n": len(sigma_seeds),
            },
        },
        outputs=output_map,
        started_utc=started,
    )
    manifest["python_wall_seconds"] = float(
        time.perf_counter() - world_wall_started
    )
    manifest["provider_public_card_hashes"] = {
        provider: {
            "card_json_sha256": rec["card_json_sha256"],
            "sigma_surface_sha256": rec["sigma_surface_sha256"],
        }
        for provider, rec in public_manifest["cards"].items()
    }
    manifest["public_files_sha256"] = {
        str(path.relative_to(world_root)): sha256_file(path)
        for path in public_files
    }
    write_json(final_manifest_path, manifest)

    world_wall = time.perf_counter() - world_wall_started
    print(
        f"PHASE5_I1_FROZEN_PASS world={world_id} | "
        f"wall={world_wall/60.0:.1f} min"
    )
    print(f"manifest={final_manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire and freeze official Phase-5 V2 public I1"
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--world", choices=("P1", "P2", "P3", "P4"))
    target.add_argument("--all-worlds", action="store_true")
    parser.add_argument(
        "--result-root",
        type=Path,
        default=DEFAULT_RESULT_ROOT,
    )
    parser.add_argument(
        "--reset-world",
        action="store_true",
        help=(
            "Delete existing output for each requested world before running. "
            "Use only for an invalidated implementation run, never because of "
            "a scientific outcome."
        ),
    )
    args = parser.parse_args()

    contracts = load_phase5_contracts(HERE)
    worlds = (
        canonical_provider_world_ids(contracts)
        if args.all_worlds
        else (str(args.world),)
    )
    for world_id in worlds:
        run_world(
            world_id,
            result_root=args.result_root,
            reset_world=bool(args.reset_world),
        )


if __name__ == "__main__":
    main()
