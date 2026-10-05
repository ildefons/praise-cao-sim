"""Shared Phase-5 V2 execution helpers.

The purpose of this module is to keep scientific constants in the frozen JSON
contracts and keep executable scripts thin.  It provides config loading,
contract/status checks, canonical identifiers, seed-range helpers, hashing,
manifest construction, and battery-level prediction-freeze validation.

No hidden scientific parameter is defined here.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent

BATTERY_FILE = "config_phase5_recoverability_battery_v2.json"
SEED_FILE = "config_phase5_seed_registry_v2.json"
METHOD_FILE = "config_phase5_method_instantiation_v2.json"
EXECUTION_FILE = "config_phase5_execution_contract_v2.json"
ANALYSIS_FILE = "config_phase5_analysis_addendum_v2.json"

EXPECTED_STATUS = {
    "battery": "FROZEN_PHASE5_PROSPECTIVE_RECOVERABILITY_BATTERY_V2",
    "seeds": "FROZEN_PHASE5_SEED_REGISTRY_V2",
    "methods": "FROZEN_PHASE5_METHOD_INSTANTIATION_V2",
    "execution": "FROZEN_PHASE5_EXECUTION_AND_ARTIFACT_CONTRACT_V2",
    "analysis": "FROZEN_PHASE5_PROSPECTIVE_ANALYSIS_ADDENDUM_V2",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head(repo_root: Path | None = None) -> str | None:
    root = repo_root if repo_root is not None else FIRST_SCIENCE.parent
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except Exception:
        return None


@dataclass(frozen=True)
class Phase5Contracts:
    root: Path
    battery: dict[str, Any]
    seeds: dict[str, Any]
    methods: dict[str, Any]
    execution: dict[str, Any]
    analysis: dict[str, Any]

    @property
    def paths(self) -> dict[str, Path]:
        return {
            "battery": self.root / BATTERY_FILE,
            "seeds": self.root / SEED_FILE,
            "methods": self.root / METHOD_FILE,
            "execution": self.root / EXECUTION_FILE,
            "analysis": self.root / ANALYSIS_FILE,
        }

    @property
    def hashes(self) -> dict[str, str]:
        return {k: sha256_file(v) for k, v in self.paths.items()}


def load_phase5_contracts(root: Path = HERE) -> Phase5Contracts:
    root = root.resolve()
    objects = {
        "battery": read_json(root / BATTERY_FILE),
        "seeds": read_json(root / SEED_FILE),
        "methods": read_json(root / METHOD_FILE),
        "execution": read_json(root / EXECUTION_FILE),
        "analysis": read_json(root / ANALYSIS_FILE),
    }
    for key, expected in EXPECTED_STATUS.items():
        actual = objects[key].get("status")
        if actual != expected:
            raise RuntimeError(
                f"{key} status mismatch: expected {expected}, found {actual}"
            )

    source = objects["execution"]["source_of_truth"]
    required = {
        "battery": BATTERY_FILE,
        "seeds": SEED_FILE,
        "methods": METHOD_FILE,
        "analysis": ANALYSIS_FILE,
    }
    for key, filename in required.items():
        if source.get(key) != filename:
            raise RuntimeError(
                f"execution source_of_truth {key} mismatch: {source.get(key)!r}"
            )

    return Phase5Contracts(
        root=root,
        battery=objects["battery"],
        seeds=objects["seeds"],
        methods=objects["methods"],
        execution=objects["execution"],
        analysis=objects["analysis"],
    )


def canonical_provider_world_ids(contracts: Phase5Contracts) -> tuple[str, ...]:
    return tuple(str(x["id"]) for x in contracts.battery["provider_worlds"])


def canonical_graph_ids(contracts: Phase5Contracts) -> tuple[str, ...]:
    return tuple(str(x["id"]) for x in contracts.battery["graphs"])


def provider_world(contracts: Phase5Contracts, world_id: str) -> dict[str, Any]:
    matches = [
        x for x in contracts.battery["provider_worlds"]
        if str(x["id"]) == str(world_id)
    ]
    if len(matches) != 1:
        raise KeyError(f"unknown/duplicate provider world: {world_id}")
    return dict(matches[0])


def graph_record(contracts: Phase5Contracts, graph_id: str) -> dict[str, Any]:
    matches = [
        x for x in contracts.battery["graphs"]
        if str(x["id"]) == str(graph_id)
    ]
    if len(matches) != 1:
        raise KeyError(f"unknown/duplicate graph: {graph_id}")
    return dict(matches[0])


def physical_cell_id(provider_world_id: str, graph_id: str) -> str:
    return f"{provider_world_id}__{graph_id}"


def rho_records(contracts: Phase5Contracts) -> tuple[dict[str, Any], ...]:
    return tuple(dict(x) for x in contracts.execution["identifiers"]["rho"])


def query_id(
    provider_world_id: str,
    graph_id: str,
    rho_label: str,
    regime_id: str,
) -> str:
    return (
        f"{provider_world_id}__{graph_id}__{rho_label}__{regime_id}"
    )


def inclusive_seed_range(block: Mapping[str, Any]) -> tuple[int, ...]:
    start = int(block["start"])
    end = int(block["end_inclusive"])
    n = int(block["n"])
    seeds = tuple(range(start, end + 1))
    if len(seeds) != n:
        raise RuntimeError(
            f"seed block {start}..{end} has {len(seeds)} seeds, expected {n}"
        )
    return seeds


def assert_scientific_seed_banks_disjoint(contracts: Phase5Contracts) -> None:
    """Check cross-stage disjointness for all contiguous scientific banks.

    M3 graph streams are intentionally block-constructed and the LHS-MSE
    diagnostic intentionally reuses the first 100 rank-1 seeds, so that pair is
    excluded from the cross-stage disjointness check by design.
    """
    banks: list[tuple[str, set[int]]] = []

    for world_id, world in contracts.seeds["public_I1"].items():
        banks.append((f"I1/{world_id}/region", set(inclusive_seed_range(world["region"]))))
        banks.append((f"I1/{world_id}/sigma", set(inclusive_seed_range(world["sigma"]))))

    for key, block in contracts.seeds["step0"].items():
        banks.append((f"step0/{key}", set(inclusive_seed_range(block))))

    for key, block in contracts.seeds["provider_reconstruction"].items():
        banks.append((f"reconstruction/{key}", set(inclusive_seed_range(block))))

    banks.append((
        "graph_prediction/M1_M2_common_bank",
        set(inclusive_seed_range(
            contracts.seeds["graph_prediction"]["M1_M2_common_bank"]
        )),
    ))
    banks.append((
        "final_whitebox",
        set(inclusive_seed_range(contracts.seeds["final_whitebox"])),
    ))

    for i, (name_a, seeds_a) in enumerate(banks):
        for name_b, seeds_b in banks[i + 1:]:
            overlap = seeds_a.intersection(seeds_b)
            if overlap:
                raise RuntimeError(
                    f"scientific seed-bank overlap {name_a} vs {name_b}: "
                    f"{sorted(overlap)[:8]}"
                )

    smoke_base = int(contracts.seeds["engineering_smoke"]["seed_base"])
    scientific_union = set().union(*(seeds for _, seeds in banks))
    if smoke_base in scientific_union:
        raise RuntimeError("engineering smoke seed base collides with science")


def assert_v2_final_whitebox_contract(contracts: Phase5Contracts) -> None:
    wb = contracts.seeds["final_whitebox"]
    seeds = inclusive_seed_range(wb)
    if len(seeds) != 1000 or seeds[0] != 54000 or seeds[-1] != 54999:
        raise RuntimeError("Phase-5 V2 final-WB seed bank changed")
    if int(
        contracts.battery["final_whitebox"][
            "n_trajectories_per_physical_cell"
        ]
    ) != 1000:
        raise RuntimeError("Phase-5 V2 battery final-WB N is not 1000")
    if not bool(
        contracts.battery["final_whitebox"][
            "global_prediction_freeze_required"
        ]
    ):
        raise RuntimeError("global prediction freeze is not required")


def base_manifest(
    contracts: Phase5Contracts,
    *,
    stage_id: str,
    status: str,
    inputs: Mapping[str, Any],
    seed_banks: Mapping[str, Any],
    outputs: Mapping[str, str],
    started_utc: str,
    completed_utc: str | None = None,
) -> dict[str, Any]:
    hashes = contracts.hashes
    return {
        "status": status,
        "stage_id": stage_id,
        "protocol_version": "PHASE5_V2_2026-10-02",
        "battery_config_sha256": hashes["battery"],
        "seed_registry_sha256": hashes["seeds"],
        "method_contract_sha256": hashes["methods"],
        "analysis_contract_sha256": hashes["analysis"],
        "execution_contract_sha256": hashes["execution"],
        "code_commit": git_head(),
        "inputs": dict(inputs),
        "seed_banks": dict(seed_banks),
        "outputs": dict(outputs),
        "output_hashes_sha256": {
            name: sha256_file(Path(path))
            for name, path in outputs.items()
            if Path(path).is_file()
        },
        "started_utc": started_utc,
        "completed_utc": completed_utc or utc_now_iso(),
    }


def assert_m3_rank1_prefix_available(
    allocation_by_rank: Mapping[int, int] | Mapping[str, int],
) -> None:
    n1 = None
    if 1 in allocation_by_rank:
        n1 = int(allocation_by_rank[1])
    elif "1" in allocation_by_rank:
        n1 = int(allocation_by_rank["1"])
    if n1 is None:
        raise RuntimeError("M3 allocation has no rank-1 entry")
    if n1 < 100:
        raise RuntimeError(
            "Phase-5 V2 paired scoring diagnostic requires M3 rank 1 N>=100; "
            f"found N1={n1}"
        )


def validate_global_prediction_freeze_inputs(
    contracts: Phase5Contracts,
    *,
    prediction_manifests: Mapping[str, Path],
    gate_failed_cells: Iterable[str],
) -> dict[str, Any]:
    """Validate completeness before materializing the global freeze manifest.

    This function does not create or reveal WB evidence.
    """
    expected = {
        physical_cell_id(p, g)
        for p in canonical_provider_world_ids(contracts)
        for g in canonical_graph_ids(contracts)
    }
    failed = {str(x) for x in gate_failed_cells}
    predicted = {str(x) for x in prediction_manifests}

    if failed.intersection(predicted):
        raise RuntimeError(
            "a physical cell cannot be both prediction-frozen and gate-failed"
        )
    if failed.union(predicted) != expected:
        missing = sorted(expected.difference(failed.union(predicted)))
        extra = sorted(failed.union(predicted).difference(expected))
        raise RuntimeError(
            f"global prediction-freeze coverage mismatch; "
            f"missing={missing}, extra={extra}"
        )

    manifest_hashes: dict[str, str] = {}
    for cell, path in prediction_manifests.items():
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(p)
        payload = read_json(p)
        if not str(payload.get("status", "")).startswith("FROZEN_PHASE5_"):
            raise RuntimeError(
                f"{cell} prediction manifest is not frozen: "
                f"{payload.get('status')!r}"
            )
        manifest_hashes[str(cell)] = sha256_file(p)

    return {
        "expected_physical_cells": sorted(expected),
        "prediction_frozen_cells": sorted(predicted),
        "gate_failed_step0_cells": sorted(failed),
        "prediction_manifest_sha256": manifest_hashes,
        "complete": True,
    }
