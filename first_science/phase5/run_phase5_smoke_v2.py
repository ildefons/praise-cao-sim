"""Mandatory engineering smoke for Phase-5 V2.

This script uses throwaway seeds and writes only under phase5/smoke/.  It is
explicitly non-scientific.  It exercises all four frozen graph ASTs through the
native simulator, checks deterministic replay, passive interarrival extraction,
contract/seed integrity, M3 rank-1 diagnostic-prefix validation, manifest
hashing, and battery-level global prediction-freeze bookkeeping.

It does not generate or read any official Phase-5 I1, Step-0, prediction, or
final-WB artifact.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from phase5_graph_ast_v2 import assert_frozen_graph_compilation
from phase5_graph_simulator_v2 import (
    GraphProviderSurrogate,
    execute_one_phase5_graph_trajectory,
)
from phase5_runtime_v2 import (
    assert_m3_rank1_prefix_available,
    assert_scientific_seed_banks_disjoint,
    assert_v2_final_whitebox_contract,
    base_manifest,
    canonical_graph_ids,
    canonical_provider_world_ids,
    graph_record,
    load_phase5_contracts,
    physical_cell_id,
    sha256_file,
    utc_now_iso,
    validate_global_prediction_freeze_inputs,
    write_json,
)

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "smoke" / "phase5_v2"


def _synthetic_surrogates() -> dict[str, GraphProviderSurrogate]:
    # Engineering-only values chosen for short, non-saturated smoke runs.
    return {
        "ProviderA": GraphProviderSurrogate(
            mean_service_time=0.050,
            cost_rate=3.0,
            service_cv=0.3,
        ),
        "ProviderB": GraphProviderSurrogate(
            mean_service_time=0.060,
            cost_rate=3.0,
            service_cv=0.3,
        ),
        "ProviderC": GraphProviderSurrogate(
            mean_service_time=0.070,
            cost_rate=3.0,
            service_cv=0.3,
        ),
    }


def _write_fake_prediction_manifests_for_global_freeze(
    output: Path,
    contracts,
) -> None:
    fake_root = output / "global_freeze_probe"
    fake_root.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, Path] = {}
    for p in canonical_provider_world_ids(contracts):
        for g in canonical_graph_ids(contracts):
            cell = physical_cell_id(p, g)
            path = fake_root / f"{cell}.json"
            write_json(
                path,
                {
                    "status": "FROZEN_PHASE5_SMOKE_PREDICTION_V2",
                    "stage_id": "BLIND_PREDICTION",
                    "physical_cell_id": cell,
                    "scientific_evidence": False,
                },
            )
            mapping[cell] = path

    payload = validate_global_prediction_freeze_inputs(
        contracts,
        prediction_manifests=mapping,
        gate_failed_cells=(),
    )
    if not payload["complete"] or len(payload["prediction_frozen_cells"]) != 16:
        raise RuntimeError("global prediction-freeze smoke validation failed")
    write_json(fake_root / "global_freeze_probe.json", payload)


def run(output: Path, *, reset: bool) -> None:
    started = utc_now_iso()
    contracts = load_phase5_contracts(HERE)
    assert_scientific_seed_banks_disjoint(contracts)
    assert_v2_final_whitebox_contract(contracts)

    smoke_cfg = contracts.seeds["engineering_smoke"]
    smoke_base = int(smoke_cfg["seed_base"])
    if smoke_base < 90_000_000:
        raise RuntimeError("engineering smoke seed base is unexpectedly low")

    # Exercise the explicit N1>=100 assertion used by the common-bank scoring
    # diagnostic.  Scientific allocations are checked again when they exist.
    assert_m3_rank1_prefix_available({1: 100, 2: 100, 3: 100})

    output = output.resolve()
    phase5_root = HERE.resolve()
    try:
        output.relative_to(phase5_root)
    except ValueError as exc:
        raise RuntimeError("smoke output must remain inside phase5/") from exc
    if "results" in output.parts:
        raise RuntimeError("engineering smoke must not write under scientific results/")

    if reset and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    graph_invariants = dict(contracts.battery["graph_invariants"])
    graph_invariants["effective_IPT"] = float(
        contracts.battery["provider_family"]["effective_IPT"]
    )
    graph_invariants["cost_rate"] = float(
        contracts.battery["provider_family"]["cost_rate"]
    )
    surrogates = _synthetic_surrogates()
    workload_period = float(contracts.battery["workload"]["period_seconds"])
    stop_time = 3.0
    canonical_ipt = float(
        contracts.battery["provider_family"]["effective_IPT"]
    )
    execution_fraction = float(
        contracts.battery["provider_family"]["execution_fraction_x"]
    )

    output_hashes: dict[str, str] = {}
    graph_summary: list[dict[str, object]] = []

    for graph_index, graph_id in enumerate(canonical_graph_ids(contracts)):
        record = graph_record(contracts, graph_id)
        plan = assert_frozen_graph_compilation(graph_id, record["ast"])
        seed = smoke_base + graph_index

        ledger_a, diag_a = execute_one_phase5_graph_trajectory(
            graph_id=graph_id,
            graph_ast=record["ast"],
            provider_surrogates=surrogates,
            graph_invariants=graph_invariants,
            workload_period=workload_period,
            stop_time=stop_time,
            trajectory_seed=seed,
            canonical_ipt=canonical_ipt,
            execution_fraction=execution_fraction,
        )
        ledger_b, diag_b = execute_one_phase5_graph_trajectory(
            graph_id=graph_id,
            graph_ast=record["ast"],
            provider_surrogates=surrogates,
            graph_invariants=graph_invariants,
            workload_period=workload_period,
            stop_time=stop_time,
            trajectory_seed=seed,
            canonical_ipt=canonical_ipt,
            execution_fraction=execution_fraction,
        )

        pd.testing.assert_frame_equal(
            ledger_a.reset_index(drop=True),
            ledger_b.reset_index(drop=True),
            check_dtype=False,
        )
        pd.testing.assert_frame_equal(
            diag_a.reset_index(drop=True),
            diag_b.reset_index(drop=True),
            check_dtype=False,
        )
        if ledger_a.empty:
            raise RuntimeError(f"{graph_id} smoke ledger is empty")
        if int(ledger_a["completed_by_stop"].astype(bool).sum()) == 0:
            raise RuntimeError(f"{graph_id} produced no completed smoke request")

        graph_dir = output / graph_id
        graph_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = graph_dir / "ledger.csv"
        diag_path = graph_dir / "provider_interarrival.csv"
        plan_path = graph_dir / "compiled_graph_plan.json"
        ledger_a.to_csv(ledger_path, index=False)
        diag_a.to_csv(diag_path, index=False)
        write_json(
            plan_path,
            {
                "graph_id": graph_id,
                "expression": record["expression"],
                "dependencies": {
                    k: list(v) for k, v in plan.dependencies.items()
                },
                "dependency_branch_ids": {
                    k: list(v)
                    for k, v in plan.dependency_branch_ids().items()
                },
                "entry_providers": list(plan.entry_providers),
                "terminal_providers": list(plan.terminal_providers),
            },
        )

        for path in (ledger_path, diag_path, plan_path):
            output_hashes[str(path.relative_to(output))] = sha256_file(path)

        graph_summary.append(
            {
                "graph_id": graph_id,
                "seed": seed,
                "n_requests": int(len(ledger_a)),
                "n_completed": int(
                    ledger_a["completed_by_stop"].astype(bool).sum()
                ),
                "interarrival_statuses": sorted(
                    set(diag_a["status"].astype(str))
                ),
                "deterministic_replay_equal": True,
            }
        )

    _write_fake_prediction_manifests_for_global_freeze(output, contracts)

    summary_path = output / "smoke_graph_summary.csv"
    pd.DataFrame(graph_summary).to_csv(summary_path, index=False)
    output_hashes[str(summary_path.relative_to(output))] = sha256_file(
        summary_path
    )

    manifest_path = output / "phase5_v2_smoke_manifest.json"
    manifest = base_manifest(
        contracts,
        stage_id="ENGINEERING_SMOKE",
        status="FROZEN_PHASE5_ENGINEERING_SMOKE_PASS_V2",
        inputs={
            "scientific_evidence": False,
            "synthetic_provider_parameters": {
                provider: {
                    "mean_service_time": model.mean_service_time,
                    "cost_rate": model.cost_rate,
                    "service_cv": model.service_cv,
                }
                for provider, model in surrogates.items()
            },
            "stop_time": stop_time,
            "all_four_graph_asts_executed": True,
            "deterministic_replay_checked": True,
            "global_prediction_freeze_logic_checked": True,
            "controlling_child_diagnostic": "NOT_AVAILABLE_IN_CURRENT_SMOKE",
        },
        seed_banks={
            "engineering_smoke_seed_base": smoke_base,
            "graph_seeds": {
                graph_id: smoke_base + i
                for i, graph_id in enumerate(canonical_graph_ids(contracts))
            },
        },
        outputs={
            "smoke_graph_summary": str(summary_path),
        },
        started_utc=started,
    )
    manifest["scientific_evidence"] = False
    manifest["all_output_hashes_sha256"] = output_hashes
    write_json(manifest_path, manifest)

    # Resume/hash sanity: round-trip the completed manifest and verify the
    # summary hash remains stable without re-running simulation.
    reloaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    if reloaded["status"] != "FROZEN_PHASE5_ENGINEERING_SMOKE_PASS_V2":
        raise RuntimeError("smoke manifest round-trip failed")
    if sha256_file(summary_path) != output_hashes[str(summary_path.relative_to(output))]:
        raise RuntimeError("smoke summary hash changed after write")

    print("PHASE5_V2_ENGINEERING_SMOKE_PASS")
    print(pd.DataFrame(graph_summary).to_string(index=False))
    print(f"manifest={manifest_path}")
    print("scientific_evidence=False")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the mandatory non-scientific Phase-5 V2 smoke"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing smoke output directory before running.",
    )
    args = parser.parse_args()
    run(args.output, reset=bool(args.reset))


if __name__ == "__main__":
    main()
