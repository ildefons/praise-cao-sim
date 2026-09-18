"""Plot frozen M0, M1 and M2 graph-sigma approximations against white-box truth.

M2 is fundamentally set-valued in this stage, so the primary figure shows the
nine frozen A4 one-at-a-time predictions as an envelope. A second figure may
highlight the post-hoc best frozen M2 member, clearly labelled as such.

No graph simulation, search, fitting or candidate selection occurs here.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
for directory in (PHASE2, PHASE3):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    build_same_rho_conditioned_m0_curve,
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
)

TOL = 1e-12


def _metrics(pred: pd.Series, truth: pd.Series) -> dict[str, float]:
    err = pred.to_numpy(float) - truth.to_numpy(float)
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err * err))),
        "bias": float(np.mean(err)),
        "max_abs_error": float(np.max(np.abs(err))),
    }


def _m0_surface(
    metadata: dict[str, dict[str, object]],
    provider_surfaces: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rho_support = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    rows: list[pd.DataFrame] = []
    for rho in rho_support:
        curve = build_same_rho_conditioned_m0_curve(
            provider_surfaces,
            rho=float(rho),
            horizons=horizons,
        )
        # Function already includes rho_global in current implementation, but
        # preserve compatibility if that ever changes.
        if "rho_global" not in curve.columns:
            curve.insert(0, "rho_global", float(rho))
        rows.append(curve[["rho_global", "horizon", "sigma_i1_m0"]])
    return pd.concat(rows, ignore_index=True)


def _plot_panels(
    merged: pd.DataFrame,
    output: Path,
    *,
    show_best_member: bool,
    best_member_id: str | None,
) -> None:
    rho_values = sorted(float(v) for v in merged["rho_global"].unique())
    fig, axes = plt.subplots(2, 3, figsize=(13.4, 7.6), sharex=True, sharey=True)
    flat = list(axes.flat)

    for axis, rho in zip(flat, rho_values):
        rg = merged[
            np.isclose(merged["rho_global"].astype(float), rho, atol=TOL, rtol=0.0)
        ].sort_values("horizon")
        x = rg["horizon"].to_numpy(float)

        axis.plot(x, rg["sigma_whitebox"], linewidth=2.4, label="WB")
        axis.plot(x, rg["sigma_i1_m0"], linewidth=1.8, linestyle="--", label="M0")
        axis.plot(x, rg["sigma_m1"], linewidth=1.8, linestyle=":", label="M1")

        if show_best_member:
            axis.plot(
                x,
                rg["sigma_m2_best"],
                linewidth=1.8,
                label=f"M2 post-hoc member ({best_member_id})",
            )
        else:
            axis.fill_between(
                x,
                rg["sigma_m2_min"].to_numpy(float),
                rg["sigma_m2_max"].to_numpy(float),
                alpha=0.22,
                label="M2 frozen envelope",
            )

        axis.set_title(f"rho={rho:g}")
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, alpha=0.2)

    for axis in flat[len(rho_values):]:
        axis.axis("off")

    flat[0].legend(frameon=False, fontsize=8)
    title = (
        "Graph sigma: WB vs M0, M1 and post-hoc best frozen M2 member"
        if show_best_member
        else "Graph sigma: WB vs M0, M1 and frozen M2 prediction envelope"
    )
    fig.suptitle(title)
    fig.supxlabel("Horizon H (s)")
    fig.supylabel("sigma_G")
    fig.tight_layout(rect=(0.02, 0.02, 1.0, 0.95))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot WB, M0, M1, and frozen M2 graph sigma curves"
    )
    parser.add_argument(
        "--b4-comparison",
        type=Path,
        default=HERE / "results" / "m2_b4_frozen_prediction_whitebox_v1"
        / "m2_b4_prediction_whitebox_comparison.csv",
    )
    parser.add_argument(
        "--b4-accuracy-summary",
        type=Path,
        default=HERE / "results" / "m2_b4_frozen_prediction_whitebox_v1"
        / "m2_b4_variant_accuracy_summary.csv",
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_b4_frozen_prediction_whitebox_v1",
    )
    args = parser.parse_args()

    comparison = pd.read_csv(args.b4_comparison.resolve())
    accuracy = pd.read_csv(args.b4_accuracy_summary.resolve())
    metadata, provider_surfaces, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    m0 = _m0_surface(metadata, provider_surfaces)

    base = comparison[
        comparison["variant_id"].astype(str) == "BASE_M1"
    ][["rho_global", "horizon", "sigma_whitebox", "sigma_prediction"]].copy()
    base = base.rename(columns={"sigma_prediction": "sigma_m1"})

    a4 = comparison[
        comparison["variant_id"].astype(str) != "BASE_M1"
    ].copy()
    envelope = a4.groupby(["rho_global", "horizon"], as_index=False).agg(
        sigma_m2_min=("sigma_prediction", "min"),
        sigma_m2_max=("sigma_prediction", "max"),
    )

    ranked = accuracy[
        accuracy["variant_id"].astype(str) != "BASE_M1"
    ].sort_values(["mae", "variant_id"], kind="mergesort")
    if ranked.empty:
        raise RuntimeError("B4 accuracy summary contains no frozen M2 candidates")
    best_member_id = str(ranked.iloc[0]["variant_id"])
    best = comparison[
        comparison["variant_id"].astype(str) == best_member_id
    ][["rho_global", "horizon", "sigma_prediction"]].rename(
        columns={"sigma_prediction": "sigma_m2_best"}
    )

    # Tolerant canonicalization for the recurring 0.983333... CSV representation.
    def canon_rho(series: pd.Series) -> pd.Series:
        values = series.astype(float).to_numpy()
        refs = np.array([0.95, 0.975, 0.9833333333333333, 0.99, 0.995])
        out = []
        for value in values:
            nearest = refs[int(np.argmin(np.abs(refs - value)))]
            out.append(float(nearest) if abs(nearest - value) <= TOL else float(value))
        return pd.Series(out, index=series.index)

    for frame in (base, envelope, best, m0):
        frame["rho_global"] = canon_rho(frame["rho_global"])

    merged = (
        base.merge(m0, on=["rho_global", "horizon"], validate="one_to_one")
        .merge(envelope, on=["rho_global", "horizon"], validate="one_to_one")
        .merge(best, on=["rho_global", "horizon"], validate="one_to_one")
        .sort_values(["rho_global", "horizon"])
        .reset_index(drop=True)
    )

    args.output.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output / "m2_b4_m0_m1_m2_vs_whitebox_curves.csv", index=False)

    summary_rows = []
    for label, column in [
        ("M0", "sigma_i1_m0"),
        ("M1", "sigma_m1"),
        (f"M2_POSTHOC_{best_member_id}", "sigma_m2_best"),
    ]:
        summary_rows.append({"method": label, **_metrics(merged[column], merged["sigma_whitebox"])})
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(args.output / "m2_b4_m0_m1_m2_vs_whitebox_summary.csv", index=False)

    _plot_panels(
        merged,
        args.output / "m2_b4_m0_m1_m2_envelope_vs_whitebox.png",
        show_best_member=False,
        best_member_id=None,
    )
    _plot_panels(
        merged,
        args.output / "m2_b4_m0_m1_m2_posthoc_best_vs_whitebox.png",
        show_best_member=True,
        best_member_id=best_member_id,
    )

    print("M2_B4_M0_M1_M2_CURVES_READY")
    print(f"posthoc_best_frozen_m2_member={best_member_id}")
    print(summary.to_string(index=False))
    print(f"output={args.output.resolve()}")


if __name__ == "__main__":
    main()
