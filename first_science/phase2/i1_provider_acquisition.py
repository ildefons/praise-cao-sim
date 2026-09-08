"""Acquire the frozen private provider-local evidence corpus for Phase-2 I1.

Scientific role
---------------
Phase 2 needs provider-side evidence that is statistically separate from the
final Phase-1 white-box evaluation bank. For every fresh acquisition seed this
module reruns the *full* frozen composed graph once, reads the native YAFS trace,
extracts provider-local request evidence for A/B/C, and then discards the full
white-box trace.

Main call path
--------------
``main`` -> ``run_i1_acquisition`` -> ``execute_one_whitebox_trajectory``
-> native ``Stats.df`` -> ``extract_provider_local_ledgers_from_metric_rows``
-> one persistent provider-local ledger per provider.

Information boundary
--------------------
The persistent scientific artifact is the provider-local ledger corpus plus its
private provenance/checksums. Native full-graph traces and the temporary
Phase-1 top-level ledger are not retained. Public I1 cards are materialized
later from this frozen corpus for exact predeclared A_i queries; changing A_i,
H, or rho never causes another simulator run.
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
    """Read one frozen JSON configuration or manifest."""
    return json.loads(path.read_text(encoding="utf-8"))


def _branch_link_delay_seconds(configuration: dict) -> float:
    """Return the native Fpre-to-provider network delay in simulated seconds.

    Scientific meaning
    ------------------
    A provider-local request starts when the branch message actually arrives at
    that provider, not when the root request was emitted. For requests that are
    still queued at the simulation stop, YAFS has no completed provider metric
    row, so we reconstruct that arrival from Fpre completion plus the same
    transmission/propagation formula used by the native simulator.

    Called by
    ---------
    ``extract_provider_local_ledgers_from_metric_rows``.
    """
    branch_message_bytes = float(configuration["topology"]["branch_bytes"])
    bandwidth_mbps = float(configuration["topology"]["network_bw_mbps"])
    propagation_seconds = float(configuration["topology"]["network_pr"])
    if (
        bandwidth_mbps <= 0.0
        or propagation_seconds < 0.0
        or branch_message_bytes < 0.0
    ):
        raise ValueError("invalid branch-link parameters")

    # AICon/YAFS uses message.bytes/(BW*1e6) + PR for this branch.
    transmission_seconds = branch_message_bytes / (bandwidth_mbps * 1_000_000.0)
    return propagation_seconds + transmission_seconds


def extract_provider_local_ledgers_from_metric_rows(
    metric_rows: pd.DataFrame,
    configuration: dict,
    trajectory: int,
    stop_time: float,
    reception_tolerance: float = 1e-8,
) -> dict[str, pd.DataFrame]:
    """Reduce one full native trace to provider-local request ledgers.

    Scientific object
    -----------------
    For each provider and every branch that has actually arrived by the frozen
    simulation stop, construct one request row with provider-local arrival,
    completion, latency L, native execution cost C, and quality Q.

    Provider-local latency is

        L_i = provider completion - provider arrival,

    so it includes provider queue waiting plus native service time. A branch
    that has arrived but has not completed by the stop remains in the ledger
    with null completion/L/C/Q so later SLA accounting can treat it correctly.

    Important invariant
    -------------------
    When a completed provider metric row exists, reconstructed arrival must
    agree with native ``time_reception``. This makes arrival reconstruction an
    audited semantic identity rather than an approximation.

    Called by
    ---------
    ``run_i1_acquisition`` once per fresh Phase-2 trajectory.
    """
    missing_metric_columns = _REQUIRED_METRIC_COLUMNS.difference(metric_rows.columns)
    if missing_metric_columns:
        raise ValueError(
            "native metric table missing columns: "
            + ", ".join(sorted(missing_metric_columns))
        )

    simulation_stop_time = float(stop_time)
    if simulation_stop_time <= 0.0:
        raise ValueError("stop_time must be positive")

    branch_link_delay = _branch_link_delay_seconds(configuration)
    provider_cost_rate = float(configuration["provider_family"]["cost_rate"])
    if provider_cost_rate < 0.0:
        raise ValueError("provider cost rate must be non-negative")

    # Fpre completion is the point at which one root invocation releases all
    # three provider branches. If Fpre has not completed, no provider request
    # exists yet for that root invocation.
    completed_fpre_rows = metric_rows[
        metric_rows["module"] == PREPROCESS_MODULE
    ].copy()
    if completed_fpre_rows.empty:
        raise RuntimeError("native trace has no Fpre rows")
    completed_fpre_rows = completed_fpre_rows[
        completed_fpre_rows["time_out"].astype(float)
        <= simulation_stop_time + 1e-12
    ].copy()
    if completed_fpre_rows.empty:
        raise RuntimeError("no Fpre request completed before the acquisition stop")
    if completed_fpre_rows["id"].duplicated().any():
        raise RuntimeError("Fpre request ids are not unique within one trajectory")

    provider_ledgers: dict[str, pd.DataFrame] = {}
    for provider in PROVIDER_MODULES:
        provider_metric_rows = metric_rows[
            metric_rows["module"] == provider
        ].copy()
        if provider_metric_rows["id"].duplicated().any():
            raise RuntimeError(f"{provider} has duplicate native metric rows")

        provider_metric_row_by_request_id = {
            int(metric_row.id): metric_row
            for metric_row in provider_metric_rows.itertuples(index=False)
        }

        ledger_rows: list[dict[str, object]] = []
        for fpre_row in completed_fpre_rows.itertuples(index=False):
            request_id = int(fpre_row.id)
            provider_arrival_time = float(fpre_row.time_out) + branch_link_delay

            # A branch whose network arrival is after Hmax has not entered the
            # provider-local workload during the I1 card domain.
            if provider_arrival_time > simulation_stop_time + 1e-12:
                continue

            provider_completion_time = None
            provider_latency = None
            provider_cost = None
            provider_quality = None

            provider_metric_row = provider_metric_row_by_request_id.get(request_id)
            if provider_metric_row is not None:
                native_reception_time = float(provider_metric_row.time_reception)
                if abs(native_reception_time - provider_arrival_time) > float(
                    reception_tolerance
                ):
                    raise RuntimeError(
                        f"{provider} request {request_id} native reception "
                        f"{native_reception_time} disagrees with reconstructed "
                        f"arrival {provider_arrival_time}"
                    )

                possible_completion_time = float(provider_metric_row.time_out)
                if possible_completion_time <= simulation_stop_time + 1e-12:
                    provider_completion_time = possible_completion_time
                    provider_latency = (
                        provider_completion_time - provider_arrival_time
                    )
                    if provider_latency < -1e-12:
                        raise RuntimeError(
                            "provider completion precedes provider arrival"
                        )
                    provider_cost = (
                        provider_cost_rate * float(provider_metric_row.service)
                    )
                    provider_quality = float(provider_metric_row.qos)

            ledger_rows.append(
                {
                    "trajectory": int(trajectory),
                    "request_id": request_id,
                    # The shared SLA-accounting layer calls this column
                    # 'emission'. In I1 it explicitly means provider-local
                    # arrival, not root-source emission.
                    "emission": provider_arrival_time,
                    "completion": provider_completion_time,
                    "L": provider_latency,
                    "C": provider_cost,
                    "Q": provider_quality,
                }
            )

        provider_ledger = pd.DataFrame(
            ledger_rows, columns=_PROVIDER_LEDGER_COLUMNS
        )
        if provider_ledger.empty:
            raise RuntimeError(f"provider-local ledger is empty for {provider}")
        if provider_ledger[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"duplicate request ids in provider ledger {provider}")

        provider_ledgers[provider] = provider_ledger.sort_values(
            ["emission", "request_id"]
        ).reset_index(drop=True)

    return provider_ledgers


def _validate_acquisition_protocol(
    acquisition_configuration: dict,
    phase1_configuration: dict,
) -> list[int]:
    """Validate that Phase-2 acquisition cannot drift from its frozen contract.

    The checks enforce a fresh disjoint seed bank and the same root workload and
    simulation stop as the frozen Phase-1 physical context.

    Returns
    -------
    The exact ordered Phase-2 trajectory seed bank.
    """
    if (
        acquisition_configuration.get("status")
        != "FROZEN_PHASE2_I1_ACQUISITION_PROTOCOL_V1"
    ):
        raise ValueError("unexpected I1 acquisition protocol status")

    acquisition_specification = acquisition_configuration["acquisition"]
    seed_start = int(acquisition_specification["seed_start"])
    seed_end = int(acquisition_specification["seed_end_inclusive"])
    trajectory_seeds = list(range(seed_start, seed_end + 1))

    if len(trajectory_seeds) != int(
        acquisition_specification["n_trajectories"]
    ):
        raise ValueError("seed range does not match n_trajectories")
    if len(set(trajectory_seeds)) != len(trajectory_seeds):
        raise ValueError("I1 acquisition seeds must be unique")
    if min(trajectory_seeds) <= int(
        acquisition_specification["forbidden_seed_max_inclusive"]
    ):
        raise ValueError("I1 acquisition overlaps an earlier Phase-1 seed range")

    acquisition_workload = acquisition_configuration["workload"]
    if abs(
        float(acquisition_workload["period"])
        - float(phase1_configuration["workload"]["period"])
    ) > 1e-12:
        raise ValueError("I1 workload period differs from frozen Phase-1 context")
    if abs(
        float(acquisition_workload["simulation_stop_time"])
        - float(phase1_configuration["horizon"]["simulation_stop_time"])
    ) > 1e-12:
        raise ValueError("I1 stop time differs from frozen Phase-1 context")

    return trajectory_seeds


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 fingerprint used to freeze one provider corpus."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_i1_acquisition(
    acquisition_config_path: Path,
    output_directory: Path,
) -> dict[str, object]:
    """Acquire and freeze the independent Phase-2 provider evidence corpus.

    Scientific sequence
    -------------------
    1. Load and validate the frozen Phase-2 acquisition protocol.
    2. For each fresh seed, execute the complete frozen Phase-1 graph once.
    3. Read the native trace while it still exists in a temporary directory.
    4. Reduce that trace to provider-local A/B/C ledgers.
    5. Delete the full trace automatically when the temporary directory closes.
    6. Concatenate the N trajectories per provider, write the private corpus,
       fingerprint it, and write a safe public completion summary.

    This function does not construct an A_i-specific I1 card. It freezes the
    reusable evidence from which later exact card queries are materialized.
    """
    acquisition_configuration = _read_json(acquisition_config_path)
    phase1_configuration_path = (
        acquisition_config_path.parent
        / acquisition_configuration["phase1_base_configuration"]
    ).resolve()
    phase1_configuration = _read_json(phase1_configuration_path)
    trajectory_seeds = _validate_acquisition_protocol(
        acquisition_configuration, phase1_configuration
    )

    frozen_physical_reference = acquisition_configuration[
        "frozen_physical_reference"
    ]
    center_instruction_mean = float(
        frozen_physical_reference["center_instruction_mean"]
    )
    provider_dispersion = float(frozen_physical_reference["dispersion"])
    simulation_stop_time = float(
        acquisition_configuration["workload"]["simulation_stop_time"]
    )

    provider_ledgers_by_trajectory: dict[str, list[pd.DataFrame]] = {
        provider: [] for provider in PROVIDER_MODULES
    }

    for trajectory_index, trajectory_seed in enumerate(trajectory_seeds):
        with tempfile.TemporaryDirectory(
            prefix=f"praise_i1_seed_{trajectory_seed}_"
        ) as temporary_directory_name:
            trajectory_directory = Path(temporary_directory_name)

            # PRIVATE WHITE-BOX ACQUISITION STEP.
            # Reuse the frozen Phase-1 runner read-only. It executes the full
            # Fpre -> ParAll(A,B,C) -> Fpost graph, not three independent
            # provider simulations. Its top-level ledger and native trace live
            # only inside this temporary directory.
            execute_one_whitebox_trajectory(
                phase1_configuration,
                center_instruction_mean=center_instruction_mean,
                dispersion=provider_dispersion,
                trajectory_seed=int(trajectory_seed),
                trajectory_output_directory=trajectory_directory,
            )

            native_metric_rows = Stats(
                defaultPath=str(trajectory_directory / "sim_trace")
            ).df.copy()

            # PRIVATE PROVIDER-EVIDENCE STEP.
            # Extract only the local observations allowed to survive Phase 2.
            provider_ledgers_for_trajectory = (
                extract_provider_local_ledgers_from_metric_rows(
                    native_metric_rows,
                    phase1_configuration,
                    trajectory=trajectory_index,
                    stop_time=simulation_stop_time,
                )
            )
            for provider in PROVIDER_MODULES:
                provider_ledgers_by_trajectory[provider].append(
                    provider_ledgers_for_trajectory[provider]
                )

        # Leaving the TemporaryDirectory is the white-box firewall: the native
        # full-graph trace and temporary top-level ledger no longer exist here.

    output_directory.mkdir(parents=True, exist_ok=True)
    provider_checksums: dict[str, str] = {}
    provider_row_counts: dict[str, int] = {}
    provider_trajectory_counts: dict[str, int] = {}

    # FROZEN PRIVATE EVIDENCE STEP.
    # Persist only the reduced provider-local corpus required by I1.
    for provider in PROVIDER_MODULES:
        provider_ledger = pd.concat(
            provider_ledgers_by_trajectory[provider], ignore_index=True
        )
        if int(provider_ledger["trajectory"].nunique()) != len(
            trajectory_seeds
        ):
            raise RuntimeError(
                f"{provider} does not contain every acquisition trajectory"
            )
        if provider_ledger[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(
                f"{provider} acquisition corpus contains duplicate requests"
            )

        provider_directory = output_directory / "private" / provider
        provider_directory.mkdir(parents=True, exist_ok=True)
        ledger_path = provider_directory / "provider_request_ledgers.csv"
        provider_ledger.to_csv(ledger_path, index=False)

        provider_checksums[provider] = _sha256_file(ledger_path)
        provider_row_counts[provider] = int(len(provider_ledger))
        provider_trajectory_counts[provider] = int(
            provider_ledger["trajectory"].nunique()
        )

    # Private provenance intentionally contains hidden physical/seeding details
    # and must never be copied into a public I1 card.
    private_manifest = {
        "status": "FROZEN_PHASE2_I1_PRIVATE_ACQUISITION_CORPUS_V1",
        "acquisition_config": acquisition_configuration,
        "phase1_base_configuration": str(phase1_configuration_path),
        "seed_bank": trajectory_seeds,
        "provider_sha256": provider_checksums,
        "provider_rows": provider_row_counts,
        "provider_trajectories": provider_trajectory_counts,
    }
    private_manifest_path = (
        output_directory / "private" / "acquisition_manifest.json"
    )
    private_manifest_path.write_text(
        json.dumps(private_manifest, indent=2), encoding="utf-8"
    )

    # PUBLIC COMPLETION STEP.
    # This summary proves that acquisition completed without revealing seeds or
    # hidden physical generator parameters.
    public_summary = {
        "status": "PHASE2_I1_ACQUISITION_COMPLETE",
        "n_trajectories": len(trajectory_seeds),
        "providers": list(PROVIDER_MODULES),
        "provider_rows": provider_row_counts,
        "workload_contract": {
            "period": float(acquisition_configuration["workload"]["period"]),
            "accounting_origin": float(
                acquisition_configuration["workload"]["accounting_origin"]
            ),
            "horizon_max": float(
                acquisition_configuration["workload"]["horizon_max"]
            ),
        },
        "public_card_generation": (
            "deterministic post-processing of frozen private corpus"
        ),
    }
    (output_directory / "acquisition_public_summary.json").write_text(
        json.dumps(public_summary, indent=2), encoding="utf-8"
    )

    print("PHASE2_I1_ACQUISITION_RUN_PASS")
    print(f"n_trajectories={len(trajectory_seeds)}")
    for provider in PROVIDER_MODULES:
        print(
            f"{provider}: rows={provider_row_counts[provider]} "
            f"trajectories={provider_trajectory_counts[provider]}"
        )
    print(f"output={output_directory.resolve()}")
    return public_summary


def main() -> None:
    """Command-line entry point for the one-time frozen Phase-2 acquisition."""
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
