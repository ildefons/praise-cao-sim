"""Run and consolidate the frozen preliminary I1-M0 diagnostic sweep.

This script is intentionally preliminary. It consumes the already-materialized
public I1 cards, evaluates the frozen official M0 baseline at the predeclared
same-rho slices, and adds two evaluation-only views without changing I1 or M0:

1. geometric agreement between the white-box/reference A_G and the bottom-up
   analytically induced A_G^M0;
2. the H->sigma_hat shape family over every rho vector already exposed by the
   public I1 cards.

Only the same-rho diagonal is the official M0 prediction rule. Off-diagonal
rho-vector results are sensitivity diagnostics, not predictions for a common
rho_G. The script does not modify I1, A_i, M0, or the Phase-1 benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from diagnose_real_wb_vs_i1_m0 import (
    _common_horizon_support,
    _rho_tag,
    extract_provider_boundaries_from_public_cards,
    load_hash_frozen_i1_cards,
    run_real_trace_diagnostic,
)
from m0_analytic_composition import AdmissibilityBoundary
from m0_evaluation_diagnostics import (
    boundary_overlap_metrics,
    build_rho_vector_sigma_family,
    common_rho_support,
    summarize_rho_vector_shapes,
)
from m0_phase1_benchmark_adapter import build_phase1_g0_full_m0_boundary

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


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_region_overlap_table(
    *,
    i1_card_root: Path,
    i1_card_manifest_path: Path,
    whitebox_manifest_path: Path,
    phase1_physical_config_path: Path,
) -> tuple[pd.DataFrame, AdmissibilityBoundary]:
    """Compare the bottom-up A_G^M0 with every frozen Phase-1 v2 A_G."""
    metadata_by_provider, provider_surfaces, _ = load_hash_frozen_i1_cards(
        i1_card_root, i1_card_manifest_path
    )
    provider_boundaries = extract_provider_boundaries_from_public_cards(
        metadata_by_provider, provider_surfaces
    )
    induced_global_boundary, _ = build_phase1_g0_full_m0_boundary(
        _read_json(phase1_physical_config_path), provider_boundaries
    )

    whitebox_manifest = _read_json(whitebox_manifest_path)
    if whitebox_manifest.get("status") != "FROZEN_PHASE1_V2_AR_SELECTION_V1":
        raise ValueError("unexpected Phase-1 v2 white-box manifest status")

    rows: list[dict[str, object]] = []
    for whitebox in whitebox_manifest["whiteboxes"]:
        reference = AdmissibilityBoundary(
            l_max=float(whitebox["l_max"]),
            c_max=float(whitebox["c_max"]),
            q_min=float(whitebox["q_min"]),
        )
        metrics = boundary_overlap_metrics(induced_global_boundary, reference)
        rows.append(
            {
                "case_id": str(whitebox["case_id"]),
                "selection_role": str(whitebox["selection_role"]),
                "A_G_WB_l_max": reference.l_max,
                "A_G_WB_c_max": reference.c_max,
                "A_G_WB_q_min": reference.q_min,
                "A_G_M0_l_max": induced_global_boundary.l_max,
                "A_G_M0_c_max": induced_global_boundary.c_max,
                "A_G_M0_q_min": induced_global_boundary.q_min,
                **metrics,
            }
        )
    return pd.DataFrame(rows), induced_global_boundary


def _build_rho_vector_outputs(
    *,
    i1_card_root: Path,
    i1_card_manifest_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, tuple[float, ...]]:
    """Build the public-card-only R^3 M0 probability sensitivity family."""
    metadata_by_provider, provider_surfaces, _ = load_hash_frozen_i1_cards(
        i1_card_root, i1_card_manifest_path
    )
    horizons = _common_horizon_support(metadata_by_provider)
    rho_support = common_rho_support(provider_surfaces)
    family = build_rho_vector_sigma_family(
        provider_surfaces=provider_surfaces,
        horizons=horizons,
        rho_values=rho_support,
    )
    shape_summary = summarize_rho_vector_shapes(family)
    return family, shape_summary, rho_support


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
    """Run official same-rho sweep plus region/rho-vector diagnostics."""
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

    region_overlap, induced_global_boundary = _build_region_overlap_table(
        i1_card_root=i1_card_root,
        i1_card_manifest_path=i1_card_manifest_path,
        whitebox_manifest_path=whitebox_manifest_path,
        phase1_physical_config_path=phase1_physical_config_path,
    )
    region_overlap.to_csv(
        output_root / "preliminary_i1_m0_region_overlap.csv", index=False
    )

    rho_vector_family, rho_vector_shape_summary, rho_support = _build_rho_vector_outputs(
        i1_card_root=i1_card_root,
        i1_card_manifest_path=i1_card_manifest_path,
    )
    rho_vector_family.to_csv(
        output_root / "preliminary_i1_m0_rho_vector_family.csv", index=False
    )
    rho_vector_shape_summary.to_csv(
        output_root / "preliminary_i1_m0_rho_vector_shape_summary.csv", index=False
    )

    predicted = summary_table[summary_table["m0_status"] == "PREDICTED"].copy()
    not_applicable = summary_table[summary_table["m0_status"] == "NOT_APPLICABLE"].copy()
    distinct_rho_vectors = rho_vector_shape_summary[
        ["rho_ProviderA", "rho_ProviderB", "rho_ProviderC"]
    ]
    diagonal_vectors = rho_vector_shape_summary[
        rho_vector_shape_summary["is_same_rho_diagonal"].astype(bool)
    ]

    manifest: dict[str, object] = {
        "status": "PRELIMINARY_I1_M0_DIAGNOSTIC_V2",
        "scientific_status": "preliminary_not_final_evaluation",
        "official_global_rho_values": [float(value) for value in rho_values],
        "phase2_I1_is_hash_frozen_before_phase3_evaluation": True,
        "phase3_reads_private_provider_traces": False,
        "core_M0_changed_by_this_diagnostic_extension": False,
        "i1_card_manifest_sha256": _sha256(i1_card_manifest_path),
        "whitebox_manifest_sha256": _sha256(whitebox_manifest_path),
        "git_commit": _git_head(HERE.parents[1]),
        "evaluation_axes": {
            "region": {
                "reference": "A_G_WB",
                "estimate": "A_G_M0_bottom_up",
                "primary_overlap_metric": "J_A=mu(intersection)/mu(union)",
                "current_measure_semantics": "LC_projection_exact_same_Q_threshold",
                "additional_metrics": [
                    "intersection_over_A_G_WB",
                    "intersection_over_A_G_M0",
                    "delta_l_M0_minus_WB",
                    "delta_c_M0_minus_WB",
                    "delta_q_M0_minus_WB",
                    "region_relation",
                ],
            },
            "probability": {
                "official_M0_rule": "rho_A=rho_B=rho_C=rho_G then product_i sigma_i",
                "sensitivity_family": "all public rho vectors in R^3",
                "off_diagonal_semantics": "diagnostic_only_not_a_prediction_for_common_global_rho_G",
                "public_rho_support": [float(value) for value in rho_support],
            },
        },
        "induced_A_G_M0": {
            "l_max": induced_global_boundary.l_max,
            "c_max": induced_global_boundary.c_max,
            "q_min": induced_global_boundary.q_min,
        },
        "n_predicted_rows": int(len(predicted)),
        "n_not_applicable_rows": int(len(not_applicable)),
        "applicable_cases": sorted(set(predicted["case_id"].astype(str))),
        "not_applicable_cases": sorted(set(not_applicable["case_id"].astype(str))),
        "n_rho_vectors": int(len(distinct_rho_vectors)),
        "n_same_rho_diagonal_vectors": int(len(diagonal_vectors)),
        "result_files": {
            "official_same_rho_summary": "preliminary_i1_m0_summary.csv",
            "official_same_rho_sigma_snapshot": "preliminary_i1_m0_sigma_snapshot.csv",
            "region_overlap": "preliminary_i1_m0_region_overlap.csv",
            "rho_vector_family": "preliminary_i1_m0_rho_vector_family.csv",
            "rho_vector_shape_summary": "preliminary_i1_m0_rho_vector_shape_summary.csv",
        },
        "interpretation_guard": (
            "A_G_WB and bottom-up A_G_M0 are separate result objects and are compared geometrically; "
            "they are not forced equal. Official M0 sigma errors are defined only for PREDICTED same-rho "
            "cases. Off-diagonal rho-vector curves characterize sensitivity of the probability-composition "
            "operator only and are not predictions for a common global rho_G."
        ),
    }
    (output_root / "preliminary_i1_m0_manifest_v2.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print("PHASE3_PRELIMINARY_I1_M0_CONSOLIDATION_V2_PASS")
    print("PUBLIC_HASH_FROZEN_I1_INPUT_PASS")
    print("FOUR_RHO_OFFICIAL_M0_SWEEP_PASS")
    print("A_G_WB_VS_A_G_M0_REGION_OVERLAP_PASS")
    print("M0_RHO_VECTOR_R3_SENSITIVITY_PASS")
    print("OFF_DIAGONAL_RHO_VECTOR_DIAGNOSTIC_ONLY_PASS")
    print("PRELIMINARY_RESULT_MANIFEST_V2_WRITTEN_PASS")
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
        default=HERE / "results" / "preliminary_i1_m0_v2",
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
