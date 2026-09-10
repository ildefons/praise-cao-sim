"""Two-axis diagnostic for rho-conditioned I1 with the frozen M0 algebra.

This candidate Phase-3 path consumes only the public rho-conditioned I1 cards.
For each same-rho diagonal point rho_region=rho_query=rho_G it:

1. selects A_i(rho_G) from each provider card;
2. composes the bottom-up A_G^M0(rho_G);
3. computes region agreement J_A against each frozen Phase-1 v2 A_G^WB;
4. composes the M0 sigma curve by independent product; and
5. reports whole-horizon sigma MAE against the corresponding WB reference.

Unlike the historical applicability-only diagnostic, this two-axis diagnostic
does not suppress sigma discrepancy when regions differ. Region mismatch is
explicitly represented on the x axis by J_A; sigma discrepancy is represented
on the y axis by MAE. Containment is retained as an additional relation.
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

from i1_provider_card import load_i1_provider_card  # noqa: E402
from m0_analytic_composition import (  # noqa: E402
    AdmissibilityBoundary,
    independent_product_probability,
)
from m0_evaluation_diagnostics import boundary_overlap_metrics  # noqa: E402
from m0_phase1_benchmark_adapter import build_phase1_g0_full_m0_boundary  # noqa: E402
from diagnose_real_wb_vs_i1_m0 import build_real_whitebox_curve  # noqa: E402

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
ROLE_ORDER = ("latency", "cost", "mixed")
TOLERANCE = 1e-12


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


def load_rho_conditioned_i1_cards(
    card_root: Path,
    manifest_path: Path,
) -> tuple[dict[str, dict[str, object]], dict[str, pd.DataFrame], dict[str, Any]]:
    manifest = _read_json(manifest_path)
    if manifest.get("status") != "PHASE2_I1_RHO_CONDITIONED_CARD_INSTANCES_V1":
        raise ValueError("unexpected rho-conditioned I1 manifest status")
    cards = manifest.get("cards", {})
    if set(cards) != set(PROVIDERS):
        raise ValueError("rho-conditioned I1 manifest must contain ProviderA/B/C")

    metadata_by_provider: dict[str, dict[str, object]] = {}
    surfaces: dict[str, pd.DataFrame] = {}
    for provider in PROVIDERS:
        record = cards[provider]
        directory = card_root / str(record["directory"])
        card_json = directory / "card.json"
        surface_csv = directory / "sigma_surface.csv"
        if _sha256(card_json) != str(record["card_json_sha256"]):
            raise RuntimeError(f"{provider} public card.json hash mismatch")
        if _sha256(surface_csv) != str(record["sigma_surface_sha256"]):
            raise RuntimeError(f"{provider} public sigma surface hash mismatch")
        metadata, surface = load_i1_provider_card(directory)
        if str(metadata.get("provider_id")) != provider:
            raise RuntimeError(f"{provider} provider_id mismatch")
        if "region_rho" not in surface.columns:
            raise RuntimeError(f"{provider} surface is missing region_rho")
        metadata_by_provider[provider] = metadata
        surfaces[provider] = surface
    return metadata_by_provider, surfaces, manifest


def common_same_rho_support(
    metadata_by_provider: dict[str, dict[str, object]]
) -> tuple[float, ...]:
    supports: list[tuple[float, ...]] = []
    for provider in PROVIDERS:
        metadata = metadata_by_provider[provider]
        region = tuple(
            float(x) for x in metadata["supported_region_rho_values"]
        )
        query = tuple(
            float(x) for x in metadata["supported_query_rho_values"]
        )
        if region != query:
            raise RuntimeError(
                f"{provider} does not expose a common same-rho diagonal support"
            )
        supports.append(region)
    if len(set(supports)) != 1:
        raise RuntimeError("provider same-rho supports differ")
    return supports[0]


def common_horizon_support(
    metadata_by_provider: dict[str, dict[str, object]]
) -> list[float]:
    supports = [
        tuple(float(x) for x in metadata_by_provider[p]["supported_horizons"])
        for p in PROVIDERS
    ]
    if len(set(supports)) != 1:
        raise RuntimeError("provider horizon supports differ")
    return list(supports[0])


def provider_boundaries_at_region_rho(
    metadata_by_provider: dict[str, dict[str, object]],
    rho_region: float,
) -> dict[str, AdmissibilityBoundary]:
    result: dict[str, AdmissibilityBoundary] = {}
    for provider in PROVIDERS:
        candidates = [
            dict(region)
            for region in metadata_by_provider[provider]["rho_conditioned_regions"]
            if abs(float(region["region_rho"]) - float(rho_region)) <= TOLERANCE
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                f"{provider} expected one A_i(rho={rho_region:g}); "
                f"found {len(candidates)}"
            )
        region = candidates[0]
        result[provider] = AdmissibilityBoundary(
            l_max=float(region["l_max"]),
            c_max=float(region["c_max"]),
            q_min=float(region["q_min"]),
        )
    return result


def build_same_rho_conditioned_m0_curve(
    provider_surfaces: dict[str, pd.DataFrame],
    *,
    rho: float,
    horizons: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    for horizon in horizons:
        provider_sigma: dict[str, float] = {}
        for provider in PROVIDERS:
            surface = provider_surfaces[provider]
            selected = surface[
                np.isclose(
                    surface["region_rho"].astype(float),
                    float(rho),
                    atol=TOLERANCE,
                    rtol=0.0,
                )
                & np.isclose(
                    surface["rho"].astype(float),
                    float(rho),
                    atol=TOLERANCE,
                    rtol=0.0,
                )
                & np.isclose(
                    surface["horizon"].astype(float),
                    float(horizon),
                    atol=TOLERANCE,
                    rtol=0.0,
                )
            ]
            if len(selected) != 1:
                raise RuntimeError(
                    f"{provider}: expected one diagonal point at "
                    f"rho={rho:g}, H={horizon:g}; found {len(selected)}"
                )
            provider_sigma[provider] = float(selected.iloc[0]["sigma_hat"])
        rows.append(
            {
                "rho_global": float(rho),
                "horizon": float(horizon),
                "sigma_i1_m0": independent_product_probability(provider_sigma),
                "sigma_ProviderA": provider_sigma["ProviderA"],
                "sigma_ProviderB": provider_sigma["ProviderB"],
                "sigma_ProviderC": provider_sigma["ProviderC"],
            }
        )
    return pd.DataFrame(rows)


def _curve_error(
    whitebox_curve: pd.DataFrame,
    m0_curve: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    comparison = whitebox_curve.merge(
        m0_curve, on="horizon", how="inner", validate="one_to_one"
    )
    comparison["error_m0_minus_wb"] = (
        comparison["sigma_i1_m0"].astype(float)
        - comparison["sigma_whitebox"].astype(float)
    )
    error = comparison["error_m0_minus_wb"].to_numpy(dtype=float)
    return comparison, {
        "sigma_mae": float(np.mean(np.abs(error))),
        "sigma_rmse": float(np.sqrt(np.mean(error * error))),
        "sigma_bias": float(np.mean(error)),
        "sigma_max_abs_error": float(np.max(np.abs(error))),
    }


def plot_two_axis_scatter(points: pd.DataFrame, output_path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8.2, 5.4))
    for role in ROLE_ORDER:
        role_points = points[
            points["selection_role"] == role
        ].sort_values("rho_global")
        axis.scatter(
            role_points["J_A"],
            role_points["sigma_mae"],
            s=58,
            label=role.capitalize(),
        )
        for row in role_points.itertuples(index=False):
            axis.annotate(
                f"{float(row.rho_global):.3g}",
                (float(row.J_A), float(row.sigma_mae)),
                xytext=(5, 3),
                textcoords="offset points",
                fontsize=8,
            )
    axis.set_xlim(0.0, 1.02)
    axis.set_ylim(0.0, 1.02)
    axis.set_xlabel(r"Global-region agreement $J_A$")
    axis.set_ylabel(r"Whole-horizon $\mathrm{MAE}_\sigma$")
    axis.set_title("I1-M0 rho-conditioned two-axis diagnostic")
    axis.grid(True, alpha=0.22)
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(figure)


def run_rho_conditioned_m0_two_axis_diagnostic(
    *,
    whitebox_ledger_path: Path,
    whitebox_manifest_path: Path,
    phase1_physical_config_path: Path,
    i1_card_root: Path,
    i1_card_manifest_path: Path,
    output_directory: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    metadata, surfaces, _ = load_rho_conditioned_i1_cards(
        i1_card_root, i1_card_manifest_path
    )
    rho_support = common_same_rho_support(metadata)
    horizons = common_horizon_support(metadata)
    stop_time = max(horizons)

    wb_manifest = _read_json(whitebox_manifest_path)
    if wb_manifest.get("status") != "FROZEN_PHASE1_V2_AR_SELECTION_V1":
        raise ValueError("unexpected Phase-1 v2 white-box manifest status")
    by_role = {
        str(x["selection_role"]): x for x in wb_manifest["whiteboxes"]
    }
    all_top_level_ledgers = pd.read_csv(whitebox_ledger_path)
    if int(all_top_level_ledgers["trajectory"].nunique()) != 100:
        raise ValueError("white-box diagnostic expects exactly 100 trajectories")
    physical_config = _read_json(phase1_physical_config_path)

    output_directory.mkdir(parents=True, exist_ok=True)
    point_rows: list[dict[str, object]] = []
    curve_rows: list[pd.DataFrame] = []

    for rho in rho_support:
        provider_boundaries = provider_boundaries_at_region_rho(metadata, rho)
        induced, _ = build_phase1_g0_full_m0_boundary(
            physical_config, provider_boundaries
        )
        m0_curve = build_same_rho_conditioned_m0_curve(
            surfaces, rho=rho, horizons=horizons
        )

        for role in ROLE_ORDER:
            wb = by_role[role]
            reference = AdmissibilityBoundary(
                l_max=float(wb["l_max"]),
                c_max=float(wb["c_max"]),
                q_min=float(wb["q_min"]),
            )
            overlap = boundary_overlap_metrics(induced, reference)
            wb_curve = build_real_whitebox_curve(
                all_top_level_ledgers,
                wb,
                rho_global=float(rho),
                horizons=horizons,
                stop_time=stop_time,
            )
            comparison, error_metrics = _curve_error(wb_curve, m0_curve)
            comparison.insert(0, "selection_role", role)
            comparison.insert(0, "case_id", str(wb["case_id"]))
            curve_rows.append(comparison)

            point_rows.append(
                {
                    "case_id": str(wb["case_id"]),
                    "selection_role": role,
                    "rho_global": float(rho),
                    "A_G_M0_l_max": induced.l_max,
                    "A_G_M0_c_max": induced.c_max,
                    "A_G_M0_q_min": induced.q_min,
                    "A_G_WB_l_max": reference.l_max,
                    "A_G_WB_c_max": reference.c_max,
                    "A_G_WB_q_min": reference.q_min,
                    **overlap,
                    **error_metrics,
                }
            )

    points = pd.DataFrame(point_rows).sort_values(
        ["selection_role", "rho_global"]
    ).reset_index(drop=True)
    curves = pd.concat(curve_rows, ignore_index=True).sort_values(
        ["selection_role", "rho_global", "horizon"]
    ).reset_index(drop=True)

    points.to_csv(
        output_directory / "i1_m0_two_axis_points.csv", index=False
    )
    curves.to_csv(
        output_directory / "i1_m0_two_axis_curves.csv", index=False
    )
    plot_two_axis_scatter(
        points,
        output_directory / "i1_m0_JA_vs_sigma_MAE_scatter.png",
    )

    manifest: dict[str, Any] = {
        "status": "PHASE3_RHO_CONDITIONED_I1_M0_TWO_AXIS_DIAGNOSTIC_V1",
        "scientific_status": "candidate_correction_pending_result_review",
        "phase3_reads_private_provider_traces": False,
        "phase1_whitebox_used_only_for_external_evaluation": True,
        "same_rho_diagonal": "rho_region=rho_query=rho_G",
        "rho_values": [float(x) for x in rho_support],
        "region_metric": (
            "J_A=mu(A_G_WB intersection A_G_M0)/"
            "mu(A_G_WB union A_G_M0)"
        ),
        "sigma_metric": "whole-horizon arithmetic MAE on the common H grid",
        "containment_is_secondary_descriptor": True,
        "sigma_error_suppressed_when_not_contained": False,
        "sigma_error_interpretation": (
            "Joint reference discrepancy. When A_G_M0 differs from A_G_WB, "
            "the sigma MAE is not isolated probability-composition error; J_A "
            "is reported alongside it to expose the region mismatch."
        ),
        "i1_manifest_sha256": _sha256(i1_card_manifest_path),
        "whitebox_manifest_sha256": _sha256(whitebox_manifest_path),
        "git_commit": _git_head(HERE.parents[1]),
        "result_files": {
            "two_axis_points": "i1_m0_two_axis_points.csv",
            "two_axis_curves": "i1_m0_two_axis_curves.csv",
            "scatter": "i1_m0_JA_vs_sigma_MAE_scatter.png",
        },
    }
    (
        output_directory / "i1_m0_two_axis_manifest_v1.json"
    ).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("PHASE3_RHO_CONDITIONED_I1_M0_TWO_AXIS_PASS")
    print("PHASE3_PUBLIC_I1_ONLY_FIREWALL_PASS")
    print("A_G_M0_DEPENDS_ON_RHO_REGION_PASS")
    print("JA_AND_SIGMA_MAE_REPORTED_TOGETHER_PASS")
    print("CONTAINMENT_RETAINED_NOT_USED_AS_SUPPRESSION_PASS")
    print(f"output={output_directory.resolve()}")
    return points, curves, manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate rho-conditioned I1-M0 on the J_A vs sigma-MAE plane"
        )
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public",
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
        default=HERE
        / "results"
        / "rho_conditioned_i1_m0_two_axis_v1",
    )
    args = parser.parse_args()

    run_rho_conditioned_m0_two_axis_diagnostic(
        whitebox_ledger_path=args.whitebox_ledgers.resolve(),
        whitebox_manifest_path=args.whitebox_manifest.resolve(),
        phase1_physical_config_path=args.phase1_physical_config.resolve(),
        i1_card_root=args.i1_card_root.resolve(),
        i1_card_manifest_path=args.i1_card_manifest.resolve(),
        output_directory=args.output.resolve(),
    )


if __name__ == "__main__":
    main()
