"""Finalize an already-materialized Phase-4 M2-B graph diagnostic.

Use this only when the graph trajectories and m2_b_graph_sigma_curves.csv were
successfully materialized but the original runner failed during downstream
summary/postprocessing. This script performs no graph simulation, reads no
white-box data, and does not alter the frozen candidate set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"

import sys
for module_directory in (PHASE2, PHASE3, HERE):
    if str(module_directory) not in sys.path:
        sys.path.insert(0, str(module_directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
)
from m2_b_one_at_a_time_graph import (  # noqa: E402
    _request_summary,
    _surface_metrics,
)

TOLERANCE = 1e-12


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def finalize_existing(*, output_directory: Path, i1_card_root: Path, i1_manifest_path: Path) -> None:
    started = time.perf_counter()
    curves_path = output_directory / "m2_b_graph_sigma_curves.csv"
    design_path = output_directory / "m2_b_variant_design.csv"
    candidates_path = output_directory / "m2_b_frozen_candidate_set.csv"
    ledger_directory = output_directory / "ledgers"

    for required in (curves_path, design_path, candidates_path):
        if not required.exists():
            raise FileNotFoundError(f"required materialized M2-B artifact missing: {required}")

    all_curves = pd.read_csv(curves_path)
    variant_design = pd.read_csv(design_path, keep_default_na=False)
    candidates = pd.read_csv(candidates_path)

    required_curve_columns = {
        "variant_id", "rho_global", "horizon", "sigma",
        "A_G_l_max", "A_G_c_max", "A_G_q_min",
    }
    missing = sorted(required_curve_columns.difference(all_curves.columns))
    if missing:
        raise ValueError(f"graph sigma curves missing columns: {missing}")

    expected_variants = variant_design["variant_id"].astype(str).tolist()
    materialized_variants = sorted(all_curves["variant_id"].astype(str).unique())
    if sorted(expected_variants) != materialized_variants:
        raise RuntimeError(
            f"variant mismatch: design={sorted(expected_variants)}, curves={materialized_variants}"
        )

    metadata, _, _ = load_rho_conditioned_i1_cards(i1_card_root, i1_manifest_path)
    rho_support = common_same_rho_support(metadata)

    curves_by_variant: dict[str, pd.DataFrame] = {}
    for variant_id in expected_variants:
        frame = all_curves[all_curves["variant_id"].astype(str) == variant_id].copy()
        if frame.empty:
            raise RuntimeError(f"no graph sigma rows for {variant_id}")
        if frame[["rho_global", "horizon"]].duplicated().any():
            raise RuntimeError(f"duplicate rho/horizon graph sigma rows for {variant_id}")
        curves_by_variant[variant_id] = frame

    if "BASE_M1" not in curves_by_variant:
        raise RuntimeError("materialized graph curves lack BASE_M1")
    base = curves_by_variant["BASE_M1"]

    surface_rows: list[dict[str, object]] = []
    per_rho_rows: list[dict[str, object]] = []
    delta_frames: list[pd.DataFrame] = []

    for variant_id, curves in curves_by_variant.items():
        summary, merged = _surface_metrics(curves, base)
        surface_rows.append({"variant_id": variant_id, **summary})
        # _surface_metrics preserves variant_id from variant_curves. The original
        # runner attempted to insert it a second time and failed after all graph
        # simulations had already completed.
        if "variant_id" not in merged.columns:
            merged.insert(0, "variant_id", variant_id)
        delta_frames.append(merged)

        for rho in rho_support:
            variant_rho = curves[
                np.isclose(curves["rho_global"].astype(float), float(rho), atol=TOLERANCE, rtol=0.0)
            ].copy()
            base_rho = base[
                np.isclose(base["rho_global"].astype(float), float(rho), atol=TOLERANCE, rtol=0.0)
            ].copy()
            rho_summary, _ = _surface_metrics(variant_rho, base_rho)
            per_rho_rows.append(
                {"variant_id": variant_id, "rho_global": float(rho), **rho_summary}
            )

    surface_summary = pd.DataFrame(surface_rows).merge(
        variant_design, on="variant_id", how="left", validate="one_to_one"
    )
    surface_summary = surface_summary[
        [
            "variant_id", "changed_provider", "changed_candidate_id",
            "changed_selection_role", "mae_vs_base", "rmse_vs_base",
            "mean_delta_vs_base", "max_abs_delta_vs_base",
        ]
    ].sort_values(["mae_vs_base", "variant_id"], ascending=[False, True])
    surface_summary.to_csv(output_directory / "m2_b_surface_spread_summary.csv", index=False)

    pd.DataFrame(per_rho_rows).merge(
        variant_design, on="variant_id", how="left", validate="many_to_one"
    ).to_csv(output_directory / "m2_b_per_rho_spread_summary.csv", index=False)

    pd.concat(delta_frames, ignore_index=True).to_csv(
        output_directory / "m2_b_graph_sigma_deltas_vs_base.csv", index=False
    )

    request_summaries: list[dict[str, object]] = []
    total_request_rows = 0
    for variant_id in expected_variants:
        ledger_path = ledger_directory / f"{variant_id}.csv"
        if not ledger_path.exists():
            raise FileNotFoundError(f"materialized ledger missing: {ledger_path}")
        ledger = pd.read_csv(ledger_path)
        if "variant_id" not in ledger.columns:
            ledger.insert(0, "variant_id", variant_id)
        if set(ledger["variant_id"].astype(str).unique()) != {variant_id}:
            raise RuntimeError(f"ledger variant_id mismatch for {variant_id}")
        total_request_rows += len(ledger)
        request_summaries.append(_request_summary(variant_id, ledger))

    request_summary = pd.DataFrame(request_summaries).merge(
        variant_design, on="variant_id", how="left", validate="one_to_one"
    )
    request_summary.to_csv(
        output_directory / "m2_b_request_distribution_summary.csv", index=False
    )

    manifest = {
        "status": "PHASE4_M2_B_ONE_AT_A_TIME_GRAPH_DIAGNOSTIC_COMPLETE_V1_RECOVERED",
        "recovery_reason": (
            "All graph simulations and sigma curves were materialized, but the original "
            "runner failed during postprocessing because variant_id was inserted twice."
        ),
        "graph_simulation_rerun": False,
        "graph_whitebox_read": False,
        "graph_prediction_used_for_candidate_selection": False,
        "optuna_rerun": False,
        "private_phase2_provider_traces_read": False,
        "candidate_set_frozen_before_graph": True,
        "n_variants": len(expected_variants),
        "variant_ids": expected_variants,
        "total_request_rows": int(total_request_rows),
        "materialized_graph_sigma_curves_sha256": _sha256(curves_path),
        "variant_design_sha256": _sha256(design_path),
        "frozen_candidate_set_sha256": _sha256(candidates_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "postprocess_wall_seconds": float(time.perf_counter() - started),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "surface_spread_summary": "m2_b_surface_spread_summary.csv",
            "per_rho_spread_summary": "m2_b_per_rho_spread_summary.csv",
            "graph_sigma_deltas": "m2_b_graph_sigma_deltas_vs_base.csv",
            "request_distribution_summary": "m2_b_request_distribution_summary.csv",
        },
    }
    _write_json(output_directory / "m2_b_graph_diagnostic_manifest_v1.json", manifest)

    print("M2_B_EXISTING_GRAPH_OUTPUTS_VALIDATED_PASS")
    print("M2_B_POSTPROCESS_RECOVERY_NO_SIMULATION_RERUN_PASS")
    print("\nWHOLE_SURFACE_SPREAD_VS_BASE_M1")
    print(surface_summary.to_string(index=False))
    print("\nREQUEST_DISTRIBUTION_SUMMARY")
    print(request_summary.to_string(index=False))
    print("M2_B_ONE_AT_A_TIME_GRAPH_DIAGNOSTIC_COMPLETE_RECOVERED")
    print(f"output={output_directory.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize already-materialized M2-B graph outputs without rerunning simulations"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_b_one_at_a_time_graph_v1",
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2
        / "results" / "i1_cards_v2_rho_conditioned" / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    args = parser.parse_args()
    finalize_existing(
        output_directory=args.output.resolve(),
        i1_card_root=args.i1_card_root.resolve(),
        i1_manifest_path=args.i1_manifest.resolve(),
    )


if __name__ == "__main__":
    main()
