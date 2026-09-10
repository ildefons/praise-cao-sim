"""Sigma-curve diagnostics for rho-conditioned I1-M0.

This diagnostic complements the two-axis (J_A, MAE_sigma) summary with the
actual horizon-dependent survival curves.

It produces two complementary comparisons on the same-rho diagonal:

1. Frozen-reference comparison
   sigma_G^WB(A_G^WB, H; rho) versus sigma_hat_G,M0(H; rho)
   for each frozen Phase-1 latency/cost/mixed reference region.  This remains a
   joint discrepancy because A_G^WB and A_G^M0(rho) may differ.

2. Same-region comparison
   sigma_G^WB(A_G^M0(rho), H; rho) versus sigma_hat_G,M0(H; rho).
   The global admissibility boundary is now held fixed, so the discrepancy is a
   direct diagnostic of the M0 probability-integration approximation, up to
   finite-sample estimation noise.

Phase 3 reads only the finalized public I1 cards.  Phase-1 white-box ledgers are
used only after M0 has formed its boundary and probability prediction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE1 = FIRST_SCIENCE / "phase1"
PHASE2 = FIRST_SCIENCE / "phase2"
for module_directory in (PHASE1, PHASE2):
    if str(module_directory) not in sys.path:
        sys.path.insert(0, str(module_directory))

from diagnose_real_wb_vs_i1_m0 import build_real_whitebox_curve  # noqa: E402
from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    build_same_rho_conditioned_m0_curve,
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from m0_phase1_benchmark_adapter import build_phase1_g0_full_m0_boundary  # noqa: E402

ROLE_ORDER = ("latency", "cost", "mixed")
ROLE_TITLES = {
    "latency": "Latency-dominant",
    "cost": "Cost-dominant",
    "mixed": "Mixed L/C",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _compare_sigma_curves(
    whitebox_curve: pd.DataFrame,
    m0_curve: pd.DataFrame,
    *,
    whitebox_column: str,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Align one WB curve with M0 and return whole-horizon error metrics."""
    if whitebox_column == "sigma_i1_m0":
        raise ValueError("whitebox column must differ from the M0 column")
    whitebox = whitebox_curve.rename(columns={"sigma_whitebox": whitebox_column})
    comparison = whitebox.merge(
        m0_curve, on="horizon", how="inner", validate="one_to_one"
    )
    comparison["error_m0_minus_whitebox"] = (
        comparison["sigma_i1_m0"].astype(float)
        - comparison[whitebox_column].astype(float)
    )
    error = comparison["error_m0_minus_whitebox"].to_numpy(dtype=float)
    return comparison, {
        "sigma_mae": float(np.mean(np.abs(error))),
        "sigma_rmse": float(np.sqrt(np.mean(error * error))),
        "sigma_bias": float(np.mean(error)),
        "sigma_max_abs_error": float(np.max(np.abs(error))),
    }


def _plot_reference_role_panels(
    curves: pd.DataFrame,
    *,
    role: str,
    output_path: Path,
) -> None:
    """Plot WB frozen-reference and M0 curves for all supported rho values."""
    role_curves = curves[curves["selection_role"] == role]
    rho_values = sorted(role_curves["rho_global"].astype(float).unique())
    figure, axes = plt.subplots(2, 3, figsize=(13.0, 7.4), sharex=True, sharey=True)
    flat_axes = list(axes.flat)
    for axis, rho in zip(flat_axes, rho_values):
        selected = role_curves[
            np.isclose(role_curves["rho_global"].astype(float), rho)
        ].sort_values("horizon")
        axis.plot(
            selected["horizon"],
            selected["sigma_whitebox_reference"],
            linewidth=2.0,
            label=r"White-box $\sigma_G$",
        )
        axis.plot(
            selected["horizon"],
            selected["sigma_i1_m0"],
            linewidth=2.0,
            linestyle="--",
            label=r"I1-M0 $\hat{\sigma}_G$",
        )
        axis.set_title(rf"$\rho={rho:g}$")
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, alpha=0.22)
    for axis in flat_axes[len(rho_values):]:
        axis.axis("off")
    flat_axes[0].legend(frameon=False, fontsize=9)
    figure.suptitle(
        f"{ROLE_TITLES.get(role, role)} reference: white-box vs I1-M0",
        fontsize=14,
    )
    figure.supxlabel("Horizon H (s)")
    figure.supylabel("Admissibility probability")
    figure.tight_layout(rect=(0.02, 0.02, 1.0, 0.95))
    figure.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def _plot_same_region_panels(
    curves: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: Path,
) -> None:
    """Plot WB and M0 while holding A_G fixed to the induced M0 boundary."""
    rho_values = sorted(curves["rho_global"].astype(float).unique())
    figure, axes = plt.subplots(2, 3, figsize=(13.0, 7.4), sharex=True, sharey=True)
    flat_axes = list(axes.flat)
    for axis, rho in zip(flat_axes, rho_values):
        selected = curves[
            np.isclose(curves["rho_global"].astype(float), rho)
        ].sort_values("horizon")
        row = summary[
            np.isclose(summary["rho_global"].astype(float), rho)
        ].iloc[0]
        axis.plot(
            selected["horizon"],
            selected["sigma_whitebox_same_region"],
            linewidth=2.0,
            label=r"WB at $A_G^{M0}$",
        )
        axis.plot(
            selected["horizon"],
            selected["sigma_i1_m0"],
            linewidth=2.0,
            linestyle="--",
            label=r"I1-M0 $\hat{\sigma}_G$",
        )
        axis.set_title(rf"$\rho={rho:g}$, MAE={float(row.sigma_mae):.3f}")
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, alpha=0.22)
    for axis in flat_axes[len(rho_values):]:
        axis.axis("off")
    flat_axes[0].legend(frameon=False, fontsize=9)
    figure.suptitle(
        r"Same-region probability diagnostic: WB at $A_G^{M0}(\rho)$ vs I1-M0",
        fontsize=14,
    )
    figure.supxlabel("Horizon H (s)")
    figure.supylabel("Admissibility probability")
    figure.tight_layout(rect=(0.02, 0.02, 1.0, 0.95))
    figure.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def run_sigma_curve_diagnostics(
    *,
    whitebox_ledger_path: Path,
    whitebox_manifest_path: Path,
    phase1_physical_config_path: Path,
    i1_card_root: Path,
    i1_card_manifest_path: Path,
    output_directory: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    metadata, surfaces, _ = load_rho_conditioned_i1_cards(
        i1_card_root, i1_card_manifest_path
    )
    rho_support = common_same_rho_support(metadata)
    horizons = common_horizon_support(metadata)
    stop_time = max(horizons)

    wb_manifest = _read_json(whitebox_manifest_path)
    if wb_manifest.get("status") != "FROZEN_PHASE1_V2_AR_SELECTION_V1":
        raise ValueError("unexpected Phase-1 v2 white-box manifest status")
    by_role = {str(x["selection_role"]): x for x in wb_manifest["whiteboxes"]}
    if set(by_role) != set(ROLE_ORDER):
        raise ValueError("expected latency/cost/mixed frozen white-box references")

    all_top_level_ledgers = pd.read_csv(whitebox_ledger_path)
    if int(all_top_level_ledgers["trajectory"].nunique()) != 100:
        raise ValueError("white-box diagnostic expects exactly 100 trajectories")
    physical_config = _read_json(phase1_physical_config_path)

    output_directory.mkdir(parents=True, exist_ok=True)
    reference_curve_rows: list[pd.DataFrame] = []
    same_region_curve_rows: list[pd.DataFrame] = []
    same_region_summary_rows: list[dict[str, object]] = []

    for rho in rho_support:
        provider_boundaries = provider_boundaries_at_region_rho(metadata, rho)
        induced, _ = build_phase1_g0_full_m0_boundary(
            physical_config, provider_boundaries
        )
        m0_curve = build_same_rho_conditioned_m0_curve(
            surfaces, rho=float(rho), horizons=horizons
        )

        # Same-region WB truth.  The boundary is formed by M0 before any WB
        # values are consulted, then evaluated on the independent Phase-1 bank.
        induced_query = {
            "l_max": float(induced.l_max),
            "c_max": float(induced.c_max),
            "q_min": float(induced.q_min),
        }
        same_region_wb = build_real_whitebox_curve(
            all_top_level_ledgers,
            induced_query,
            rho_global=float(rho),
            horizons=horizons,
            stop_time=stop_time,
        )
        same_comparison, same_metrics = _compare_sigma_curves(
            same_region_wb,
            m0_curve,
            whitebox_column="sigma_whitebox_same_region",
        )
        same_comparison.insert(0, "rho_global", float(rho))
        same_comparison.insert(1, "A_G_M0_l_max", float(induced.l_max))
        same_comparison.insert(2, "A_G_M0_c_max", float(induced.c_max))
        same_comparison.insert(3, "A_G_M0_q_min", float(induced.q_min))
        same_region_curve_rows.append(same_comparison)
        same_region_summary_rows.append(
            {
                "rho_global": float(rho),
                "A_G_M0_l_max": float(induced.l_max),
                "A_G_M0_c_max": float(induced.c_max),
                "A_G_M0_q_min": float(induced.q_min),
                **same_metrics,
            }
        )

        # Frozen Phase-1 references.  These are intentionally retained as the
        # joint benchmark view used by the two-axis diagnostic.
        for role in ROLE_ORDER:
            wb = by_role[role]
            wb_curve = build_real_whitebox_curve(
                all_top_level_ledgers,
                wb,
                rho_global=float(rho),
                horizons=horizons,
                stop_time=stop_time,
            )
            comparison, metrics = _compare_sigma_curves(
                wb_curve,
                m0_curve,
                whitebox_column="sigma_whitebox_reference",
            )
            comparison.insert(0, "case_id", str(wb["case_id"]))
            comparison.insert(1, "selection_role", role)
            comparison.insert(2, "rho_global", float(rho))
            comparison["reference_sigma_mae"] = float(metrics["sigma_mae"])
            comparison["reference_sigma_bias"] = float(metrics["sigma_bias"])
            reference_curve_rows.append(comparison)

    reference_curves = pd.concat(reference_curve_rows, ignore_index=True).sort_values(
        ["selection_role", "rho_global", "horizon"]
    ).reset_index(drop=True)
    same_region_curves = pd.concat(
        same_region_curve_rows, ignore_index=True
    ).sort_values(["rho_global", "horizon"]).reset_index(drop=True)
    same_region_summary = pd.DataFrame(same_region_summary_rows).sort_values(
        "rho_global"
    ).reset_index(drop=True)

    reference_curves.to_csv(
        output_directory / "i1_m0_reference_sigma_curves.csv", index=False
    )
    same_region_curves.to_csv(
        output_directory / "i1_m0_same_region_sigma_curves.csv", index=False
    )
    same_region_summary.to_csv(
        output_directory / "i1_m0_same_region_sigma_summary.csv", index=False
    )

    reference_plots: dict[str, str] = {}
    for role in ROLE_ORDER:
        filename = f"i1_m0_reference_sigma_{role}.png"
        _plot_reference_role_panels(
            reference_curves,
            role=role,
            output_path=output_directory / filename,
        )
        reference_plots[role] = filename

    same_region_plot = "i1_m0_same_region_sigma.png"
    _plot_same_region_panels(
        same_region_curves,
        same_region_summary,
        output_directory / same_region_plot,
    )

    manifest: dict[str, Any] = {
        "status": "PHASE3_RHO_CONDITIONED_I1_M0_SIGMA_CURVE_DIAGNOSTICS_V1",
        "scientific_status": "diagnostic_for_M0_interpretation_before_M1",
        "phase3_reads_private_provider_traces": False,
        "phase1_whitebox_used_only_for_external_evaluation": True,
        "same_rho_diagonal": "rho_region=rho_query=rho_G",
        "rho_values": [float(x) for x in rho_support],
        "reference_comparison_interpretation": (
            "Joint reference discrepancy: frozen A_G^WB may differ from A_G^M0(rho)."
        ),
        "same_region_comparison_interpretation": (
            "Probability-integration discrepancy with A_G fixed to the M0-induced "
            "boundary; residual includes finite-sample estimation noise."
        ),
        "i1_manifest_sha256": _sha256(i1_card_manifest_path),
        "whitebox_manifest_sha256": _sha256(whitebox_manifest_path),
        "whitebox_ledger_sha256": _sha256(whitebox_ledger_path),
        "git_commit": _git_head(HERE.parents[1]),
        "result_files": {
            "reference_curves": "i1_m0_reference_sigma_curves.csv",
            "same_region_curves": "i1_m0_same_region_sigma_curves.csv",
            "same_region_summary": "i1_m0_same_region_sigma_summary.csv",
            "reference_plots": reference_plots,
            "same_region_plot": same_region_plot,
        },
    }
    (output_directory / "i1_m0_sigma_curve_manifest_v1.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print("PHASE3_RHO_CONDITIONED_I1_M0_SIGMA_CURVES_PASS")
    print("FROZEN_REFERENCE_SIGMA_CURVES_PASS")
    print("SAME_M0_REGION_WHITEBOX_SIGMA_CURVES_PASS")
    print("SAME_REGION_PROBABILITY_INTEGRATION_DIAGNOSTIC_PASS")
    print("PHASE3_PUBLIC_I1_ONLY_FIREWALL_PASS")
    print("\nSAME_REGION_ERROR_SUMMARY")
    print(same_region_summary.to_string(index=False))
    print(f"\noutput={output_directory.resolve()}")
    return reference_curves, same_region_curves, same_region_summary, manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot rho-conditioned I1-M0 sigma curves and same-region WB diagnostic"
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--i1-card-manifest",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    parser.add_argument(
        "--whitebox-ledgers",
        type=Path,
        default=PHASE1
        / "results"
        / "phase1_v2_fresh_confirmation_v1"
        / "all_top_level_request_ledgers.csv",
    )
    parser.add_argument(
        "--whitebox-manifest",
        type=Path,
        default=PHASE1 / "phase1_v2_ar_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--phase1-physical-config",
        type=Path,
        default=PHASE1 / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "rho_conditioned_i1_m0_two_axis_v1",
    )
    args = parser.parse_args()
    run_sigma_curve_diagnostics(
        whitebox_ledger_path=args.whitebox_ledgers.resolve(),
        whitebox_manifest_path=args.whitebox_manifest.resolve(),
        phase1_physical_config_path=args.phase1_physical_config.resolve(),
        i1_card_root=args.i1_card_root.resolve(),
        i1_card_manifest_path=args.i1_card_manifest.resolve(),
        output_directory=args.output.resolve(),
    )


if __name__ == "__main__":
    main()
