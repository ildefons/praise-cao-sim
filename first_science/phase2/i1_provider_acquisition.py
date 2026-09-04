"""Acquire the frozen private provider-local evidence corpus for Phase-2 I1.

The acquisition uses the frozen Phase-1 physical reference regime with a fresh
seed bank. Native full-graph traces exist only inside a temporary directory.
Only provider-local request ledgers persist. Public I1 cards are generated later
by deterministic post-processing of this frozen corpus for exact requested A_i
values; no simulator rerun is needed for another A_i, H, or rho.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

PHASE2_DIRECTORY = Path(__file__).resolve().parent
PHASE1_DIRECTORY = PHASE2_DIRECTORY.parent / "phase1"
if str(PHASE1_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(PHASE1_DIRECTORY))

from whitebox_atlas import (  # noqa: E402
    PREPROCESS_MODULE,
    PROVIDER_MODULES,
    execute_one_whitebox_trajectory,
)
from yafs.stats import Stats  # noqa: E402

_REQUIRED_METRIC_COLUMNS = {
    "id",
    "module",
    "time_out",
    "time_reception",
    "service",
    "qos",
}
_PROVIDER_LEDGER_COLUMNS = [
    "trajectory",
    "request_id",
    "emission",
    "completion",
    "L",
    "C",
    "Q",
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _branch_link_delay_seconds(configuration: dict) -> float:
    """Return the native frozen branch-link delay used by AICon/YAFS."""
    branch_units = float(configuration["topology"]["branch_bytes"])
    bandwidth_mbps = float(configuration["topology"]["network_bw_mbps"])
    propagation = float(configuration["topology"]["network_pr"])
    if bandwidth_mbps <= 0.0 or propagation < 0.0 or branch_units < 0.0:
        raise ValueError("invalid branch-link parameters")
    # AICon/YAFS core uses message.bytes/(BW*1e6) + PR for this branch.
    return propagation + branch_units / (bandwidth_mbps * 1_000_000.0)


def extract_provider_local_ledgers_from_metric_rows(
    metric_rows: pd.DataFrame,
    configuration: dict,
    trajectory: int,
    stop_time: float,
    reception_tolerance: float = 1e-8,
) -> dict[str, pd.DataFrame]:
    """Extract complete provider-local arrival ledgers from one native trace.

    Fpre completion plus the deterministic branch-link delay gives every actual
    provider arrival, including requests that may still be queued and therefore
    have no provider service metric row by the simulation stop. When a provider
    metric row exists, its native ``time_reception`` is required to agree with
    the reconstructed arrival.
    """
    missing = _REQUIRED_METRIC_COLUMNS.difference(metric_rows.columns)
    if missing:
        raise ValueError(
            "native metric table missing columns: " + ", ".join(sorted(missing))
        )
    stop = float(stop_time)
    if stop <= 0.0:
        raise ValueError("stop_time must be positive")

    branch_delay = _branch_link_delay_seconds(configuration)
    provider_cost_rate = float(configuration["provider_family"]["cost_rate"])
    if provider_cost_rate < 0.0:
        raise ValueError("provider cost rate must be non-negative")

    fpre_rows = metric_rows[metric_rows["module"] == PREPROCESS_MODULE].copy()
    if fpre_rows.empty:
        raise RuntimeError("native trace has no Fpre rows")
    # A branch is released only after Fpre has actually completed.
    fpre_rows = fpre_rows[
        fpre_rows["time_out"].astype(float) <= stop + 1e-12
    ].copy()
    if fpre_rows.empty:
        raise RuntimeError("no Fpre request completed before the acquisition stop")
    if fpre_rows["id"].duplicated().any():
        raise RuntimeError("Fpre request ids are not unique within one trajectory")

    outputs: dict[str, pd.DataFrame] = {}
    for provider in PROVIDER_MODULES:
        provider_rows = metric_rows[metric_rows["module"] == provider].copy()
        if provider_rows["id"].duplicated().any():
            raise RuntimeError(f"{provider} has duplicate native metric rows")
        provider_by_id = {
            int(row.id): row for row in provider_rows.itertuples(index=False)
        }

        rows: list[dict[str, object]] = []
        for fpre in fpre_rows.itertuples(index=False):
            request_id = int(fpre.id)
            arrival = float(fpre.time_out) + branch_delay
            # A branch whose network arrival is after Hmax has not entered the
            # provider-local workload during the card domain.
            if arrival > stop + 1e-12:
                continue

            completion = None
            latency = None
            cost = None
            quality = None
            provider_row = provider_by_id.get(request_id)
            if provider_row is not None:
                native_reception = float(provider_row.time_reception)
                if abs(native_reception - arrival) > float(reception_tolerance):
                    raise RuntimeError(
                        f"{provider} request {request_id} native reception "
                        f"{native_reception} disagrees with reconstructed arrival {arrival}"
                    )
                possible_completion = float(provider_row.time_out)
                if possible_completion <= stop + 1e-12:
                    completion = possible_completion
                    latency = completion - arrival
                    if latency < -1e-12:
                        raise RuntimeError("provider completion precedes provider arrival")
                    cost = provider_cost_rate * float(provider_row.service)
                    quality = float(provider_row.qos)

            rows.append(
                {
                    "trajectory": int(trajectory),
                    "request_id": request_id,
                    # The generic SLA-accounting code calls this 'emission'.
                    # For I1 it is explicitly the provider-local arrival time.
                    "emission": arrival,
                    "completion": completion,
                    "L": latency,
                    "C": cost,
                    "Q": quality,
                }
            )

        ledger = pd.DataFrame(rows, columns=_PROVIDER_LEDGER_COLUMNS)
        if ledger.empty:
            raise RuntimeError(f"provider-local ledger is empty for {provider}")
        if ledger[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"duplicate request ids in provider ledger {provider}")
        outputs[provider] = ledger.sort_values(
            ["emission", "request_id"]
        ).reset_index(drop=True)

    return outputs


def _validate_protocol(acquisition: dict, phase1_configuration: dict) -> list[int]:
    if acquisition.get("status") != "FROZEN_PHASE2_I1_ACQUISITION_PROTOCOL_V1":
        raise ValueError("unexpected I1 acquisition protocol status")
    spec = acquisition["acquisition"]
    start = int(spec["seed_start"])
    end = int(spec["seed_end_inclusive"])
    seeds = list(range(start, end + 1))
    if len(seeds) != int(spec["n_trajectories"]):
        raise ValueError("seed range does not match n_trajectories")
    if len(set(seeds)) != len(seeds):
        raise ValueError("I1 acquisition seeds must be unique")
    if min(seeds) <= int(spec["forbidden_seed_max_inclusive"]):
        raise ValueError("I1 acquisition overlaps an earlier Phase-1 seed range")

    workload = acquisition["workload"]
    if abs(float(workload["period"]) - float(phase1_configuration["workload"]["period"])) > 1e-12:
        raise ValueError("I1 workload period differs from frozen Phase-1 context")
    if abs(float(workload["simulation_stop_time"]) - float(phase1_configuration["horizon"]["simulation_stop_time"])) > 1e-12:
        raise ValueError("I1 stop time differs from frozen Phase-1 context")
    return seeds


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_i1_acquisition(
    acquisition_config_path: Path,
    output_directory: Path,
) -> dict[str, object]:
    """Run the fresh N-trajectory I1 acquisition and freeze provider ledgers."""
    acquisition = _read_json(acquisition_config_path)
    phase1_path = (acquisition_config_path.parent / acquisition["phase1_base_configuration"]).resolve()
    phase1_configuration = _read_json(phase1_path)
    seeds = _validate_protocol(acquisition, phase1_configuration)

    physical = acquisition["frozen_physical_reference"]
    center = float(physical["center_instruction_mean"])
    dispersion = float(physical["dispersion"])
    stop_time = float(acquisition["workload"]["simulation_stop_time"])

    collected: dict[str, list[pd.DataFrame]] = {
        provider: [] for provider in PROVIDER_MODULES
    }

    for trajectory, seed in enumerate(seeds):
        with tempfile.TemporaryDirectory(prefix=f"praise_i1_seed_{seed}_") as temporary:
            trajectory_directory = Path(temporary)
            # Phase-1 runner is consumed read-only. Its top-level ledger and
            # native trace remain temporary and are deleted on leaving this block.
            execute_one_whitebox_trajectory(
                phase1_configuration,
                center_instruction_mean=center,
                dispersion=dispersion,
                trajectory_seed=int(seed),
                trajectory_output_directory=trajectory_directory,
            )
            metric_rows = Stats(
                defaultPath=str(trajectory_directory / "sim_trace")
            ).df.copy()
            extracted = extract_provider_local_ledgers_from_metric_rows(
                metric_rows,
                phase1_configuration,
                trajectory=trajectory,
                stop_time=stop_time,
            )
            for provider in PROVIDER_MODULES:
                collected[provider].append(extracted[provider])

    output_directory.mkdir(parents=True, exist_ok=True)
    provider_checksums: dict[str, str] = {}
    provider_row_counts: dict[str, int] = {}
    provider_trajectory_counts: dict[str, int] = {}

    for provider in PROVIDER_MODULES:
        ledger = pd.concat(collected[provider], ignore_index=True)
        if int(ledger["trajectory"].nunique()) != len(seeds):
            raise RuntimeError(f"{provider} does not contain every acquisition trajectory")
        if ledger[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"{provider} acquisition corpus contains duplicate requests")
        provider_directory = output_directory / "private" / provider
        provider_directory.mkdir(parents=True, exist_ok=True)
        ledger_path = provider_directory / "provider_request_ledgers.csv"
        ledger.to_csv(ledger_path, index=False)
        provider_checksums[provider] = _sha256_file(ledger_path)
        provider_row_counts[provider] = int(len(ledger))
        provider_trajectory_counts[provider] = int(ledger["trajectory"].nunique())

    # Private freeze manifest: intentionally contains hidden physical/seeding
    # provenance and must never be copied into a public I1 card.
    private_manifest = {
        "status": "FROZEN_PHASE2_I1_PRIVATE_ACQUISITION_CORPUS_V1",
        "acquisition_config": acquisition,
        "phase1_base_configuration": str(phase1_path),
        "seed_bank": seeds,
        "provider_sha256": provider_checksums,
        "provider_rows": provider_row_counts,
        "provider_trajectories": provider_trajectory_counts,
    }
    private_manifest_path = output_directory / "private" / "acquisition_manifest.json"
    private_manifest_path.write_text(
        json.dumps(private_manifest, indent=2), encoding="utf-8"
    )

    # Safe summary contains no seeds or hidden physical parameters.
    public_summary = {
        "status": "PHASE2_I1_ACQUISITION_COMPLETE",
        "n_trajectories": len(seeds),
        "providers": list(PROVIDER_MODULES),
        "provider_rows": provider_row_counts,
        "workload_contract": {
            "period": float(acquisition["workload"]["period"]),
            "accounting_origin": float(acquisition["workload"]["accounting_origin"]),
            "horizon_max": float(acquisition["workload"]["horizon_max"]),
        },
        "public_card_generation": "deterministic post-processing of frozen private corpus",
    }
    (output_directory / "acquisition_public_summary.json").write_text(
        json.dumps(public_summary, indent=2), encoding="utf-8"
    )

    print("PHASE2_I1_ACQUISITION_RUN_PASS")
    print(f"n_trajectories={len(seeds)}")
    for provider in PROVIDER_MODULES:
        print(
            f"{provider}: rows={provider_row_counts[provider]} "
            f"trajectories={provider_trajectory_counts[provider]}"
        )
    print(f"output={output_directory.resolve()}")
    return public_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PHASE2_DIRECTORY / "config_phase2_i1_acquisition_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PHASE2_DIRECTORY / "results" / "i1_acquisition_v1",
    )
    args = parser.parse_args()
    run_i1_acquisition(args.config.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
