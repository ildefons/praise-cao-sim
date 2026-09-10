"""Run and consolidate the frozen preliminary I1-M0 diagnostic sweep.

This script is intentionally preliminary. It consumes the already-materialized
public I1 cards, evaluates the frozen M0 baseline at the predeclared rho slices,
compares applicable predictions with the frozen Phase-1 white-box truth, and
writes one auditable aggregate table and manifest. It does not modify I1, A_i,
rho policy, M0, or the Phase-1 benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from diagnose_real_wb_vs_i1_m0 import _rho_tag, run_real_trace_diagnostic

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1"
PHASE2 = HERE.parent / "phase2"
PRELIMINARY_RHOS = (0.95, 0.975, 0.9833333333333333, 0.99)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(repository_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
        ).strip()
    except Exception:
        return None


def consolidate_preliminary_results(
    *,
    i1_card_root: Path,
    i1_card_manifest_path: Path,
    whitebox_ledger_path: Path,
    whitebox_manifest_path: Path,
    phase1_physical_config_path: Path,
    output_root: Path,
    rho_values: tuple[float, ...] = PRELIMINARY_RHOS,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Run the fixed rho sweep and write aggregate preliminary evidence."""
    output_root.mkdir(parents=True, exist_ok=True)
    summaries: list[pd.DataFrame] = []
    snapshots: list[pd.DataFrame] = []
    for rho in rho_values:
        rho_output = output_root / f"rho_{_rho_tag(rho)}"
        summary = run_real_trace_diagnostic(
            whitebox_ledger_path=whitebox_ledger_path,
            whitebox_manifest_path=whitebox_manifest_path,
            phase1_physical_config_path=phase1_physical_config_path,
            i1_card_root=i1_card_root,
            i1_card_manifest_path=i1_card_manifest_path,
            rho_global=float(rho),
            output_directory=rho_output,
        )
        summaries.append(summary)
        snapshot = pd.read_csv(rho_output / "real_wb_vs_i1_m0_sigma_snapshot.csv")
        snapshot.insert(0, "rho_global", float(rho))
        snapshots.append(snapshot)

    summary_table = pd.concat(summaries, ignore_index=True)
    snapshot_table = pd.concat(snapshots, ignore_index=True)
    summary_table.to_csv(output_root / "preliminary_i1_m0_summary.csv", index=False)
    snapshot_table.to_csv(output_root / "preliminary_i1_m0_sigma_snapshot.csv", index=False)

    predicted = summary_table[summary_table["m0_status"] == "PREDICTED"].copy()
    not_applicable = summary_table[summary_table["m0_status"] == "NOT_APPLICABLE"].copy()
    manifest: dict[str, object] = {
        "status": "PRELIMINARY_I1_M0_DIAGNOSTIC_V1",
        "scientific_status": "preliminary_not_final_evaluation",
        "rho_values": [float(value) for value in rho_values],
        "phase2_I1_is_hash_frozen_before_phase3_evaluation": True,
        "phase3_reads_private_provider_traces": False,
        "i1_card_manifest_sha256": _sha256(i1_card_manifest_path),
        "whitebox_manifest_sha256": _sha256(whitebox_manifest_path),
        "git_commit": _git_head(HERE.parents[1]),
        "n_predicted_rows": int(len(predicted)),
        "n_not_applicable_rows": int(len(not_applicable)),
        "applicable_cases": sorted(set(predicted["case_id"].astype(str))),
        "not_applicable_cases": sorted(set(not_applicable["case_id"].astype(str))),
        "result_files": {
            "summary": "preliminary_i1_m0_summary.csv",
            "sigma_snapshot": "preliminary_i1_m0_sigma_snapshot.csv",
        },
        "interpretation_guard": (
            "M0 errors are defined only for PREDICTED cases. Raw probability products "
            "for NOT_APPLICABLE cases remain diagnostic-only and are not scored."
        ),
    }
    (output_root / "preliminary_i1_m0_manifest_v1.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print("PHASE3_PRELIMINARY_I1_M0_CONSOLIDATION_PASS")
    print("PUBLIC_HASH_FROZEN_I1_INPUT_PASS")
    print("FOUR_RHO_PRELIMINARY_SWEEP_PASS")
    print("PRELIMINARY_RESULT_MANIFEST_WRITTEN_PASS")
    print(f"output={output_root.resolve()}")
    return summary_table, snapshot_table, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate preliminary I1-M0 results")
    parser.add_argument(
        "--i1-card-root", type=Path,
        default=PHASE2 / "results" / "i1_cards_v1" / "public",
    )
    parser.add_argument(
        "--i1-card-manifest", type=Path,
        default=PHASE2 / "results" / "i1_cards_v1" / "public" / "i1_card_instances_manifest_v1.json",
    )
    parser.add_argument(
        "--whitebox-ledgers", type=Path,
        default=PHASE1 / "results" / "phase1_v2_fresh_confirmation_v1" / "all_top_level_request_ledgers.csv",
    )
    parser.add_argument(
        "--whitebox-manifest", type=Path,
        default=PHASE1 / "phase1_v2_ar_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--phase1-physical-config", type=Path,
        default=PHASE1 / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=HERE / "results" / "preliminary_i1_m0_v1",
    )
    args = parser.parse_args()
    consolidate_preliminary_results(
        i1_card_root=args.i1_card_root.resolve(),
        i1_card_manifest_path=args.i1_card_manifest.resolve(),
        whitebox_ledger_path=args.whitebox_ledgers.resolve(),
        whitebox_manifest_path=args.whitebox_manifest.resolve(),
        phase1_physical_config_path=args.phase1_physical_config.resolve(),
        output_root=args.output.resolve(),
    )


if __name__ == "__main__":
    main()
