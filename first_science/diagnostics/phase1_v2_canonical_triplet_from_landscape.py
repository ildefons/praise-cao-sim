"""Extract canonical Phase-1 v2 latency/cost/mixed representatives.

This is a read-only selection diagnostic over the already computed v2 candidate
landscape. It does not run AICon/YAFS, recompute sigma, or freeze the benchmark.

Scientific policy under review
------------------------------
1. Keep only canonical threshold values from the Phase-1 critical-value grid.
   The original generator deliberately emits v-epsilon, v, and v+epsilon around
   each critical threshold. The middle value v is the canonical representative;
   selecting one of the epsilon brackets because of a sub-resolution metric
   difference would be scientifically arbitrary.
2. Apply the proposed v2 gate:
       R_0.95 >= 0.95
       0.50 <= R_0.99 <= 0.95
3. Prefer semantically isolated source families when they contain a passing
   canonical candidate:
       latency: FULL_DOMAIN_LOOSE_COST, then ORIGINAL_ANCHOR_INFORMED
       cost:    FULL_DOMAIN_LOOSE_LATENCY, then ORIGINAL_ANCHOR_INFORMED
       mixed:   ORIGINAL_ANCHOR_INFORMED
4. Within the chosen source family, rank by largest R_0.95, then smaller
   R_0.99, then deterministic numerical/provenance tie-breakers.

The output is for human review before any v2 A_G freeze or fresh confirmation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_ROLES = ("latency", "cost", "mixed")
DEFAULT_NOMINAL_MIN = 0.95
DEFAULT_STRESS_MIN = 0.50
DEFAULT_STRESS_MAX = 0.95

SOURCE_PREFERENCE = {
    "latency": ("FULL_DOMAIN_LOOSE_COST", "ORIGINAL_ANCHOR_INFORMED"),
    "cost": ("FULL_DOMAIN_LOOSE_LATENCY", "ORIGINAL_ANCHOR_INFORMED"),
    "mixed": ("ORIGINAL_ANCHOR_INFORMED",),
}


def _presence_tolerance(value: float, epsilon_step: float) -> float:
    """Tolerance small relative to the deliberate epsilon bracket spacing."""
    scale = max(1.0, abs(float(value)))
    return max(1e-13 * scale, abs(float(epsilon_step)) * 1e-4)


def _contains_value(values: np.ndarray, target: float, tolerance: float) -> bool:
    return bool(np.any(np.isclose(values, float(target), atol=float(tolerance), rtol=0.0)))


def canonical_axis_value(
    value: float,
    axis_values: np.ndarray,
    relative_epsilon: float,
) -> float:
    """Map v-eps/v/v+eps Phase-1 threshold brackets to the middle value v.

    Values that do not belong to a complete deliberate epsilon triplet, such as
    a full-domain loose threshold, are returned unchanged.
    """
    x = float(value)
    values = np.asarray(axis_values, dtype=float)
    candidates: list[float] = []
    for center in values:
        center = float(center)
        step = float(relative_epsilon) * max(1.0, abs(center))
        tolerance = _presence_tolerance(center, step)
        if not _contains_value(values, center - step, tolerance):
            continue
        if not _contains_value(values, center + step, tolerance):
            continue
        if any(
            abs(x - target) <= tolerance
            for target in (center - step, center, center + step)
        ):
            candidates.append(center)

    if not candidates:
        return x
    unique = sorted(set(candidates))
    if len(unique) != 1:
        raise RuntimeError(
            f"ambiguous canonical threshold for value={x}: centers={unique}"
        )
    return float(unique[0])


def collapse_epsilon_brackets(
    landscape: pd.DataFrame,
    relative_epsilon: float,
) -> pd.DataFrame:
    """Collapse deliberate threshold brackets to the actual middle-grid rows."""
    required = {
        "region_id",
        "descriptive_role",
        "ar_augmentation_type",
        "l_max",
        "c_max",
        "q_min",
        "area_rho_0p95",
        "area_rho_0p99",
    }
    missing = required.difference(landscape.columns)
    if missing:
        raise ValueError(
            "landscape missing columns: " + ", ".join(sorted(missing))
        )
    if not 0.0 < float(relative_epsilon) < 1e-3:
        raise ValueError("relative_epsilon must be small and positive")

    frame = landscape.copy()
    l_values = np.sort(frame["l_max"].astype(float).unique())
    c_values = np.sort(frame["c_max"].astype(float).unique())
    frame["canonical_l_max"] = [
        canonical_axis_value(v, l_values, relative_epsilon)
        for v in frame["l_max"].astype(float)
    ]
    frame["canonical_c_max"] = [
        canonical_axis_value(v, c_values, relative_epsilon)
        for v in frame["c_max"].astype(float)
    ]
    frame["canonical_distance"] = (
        (frame["l_max"].astype(float) - frame["canonical_l_max"]).abs()
        + (frame["c_max"].astype(float) - frame["canonical_c_max"]).abs()
    )

    group_columns = [
        "descriptive_role",
        "ar_augmentation_type",
        "canonical_l_max",
        "canonical_c_max",
        "q_min",
    ]
    canonical = (
        frame.sort_values(
            group_columns + ["canonical_distance", "region_id"],
            kind="mergesort",
        )
        .groupby(group_columns, as_index=False, sort=True)
        .first()
    )

    # The representative must be the actual middle-grid row whenever a complete
    # epsilon triplet existed, not merely a neighboring bracket assigned to it.
    scale_l = np.maximum(1.0, np.abs(canonical["canonical_l_max"].astype(float)))
    scale_c = np.maximum(1.0, np.abs(canonical["canonical_c_max"].astype(float)))
    if np.any(
        np.abs(canonical["l_max"].astype(float) - canonical["canonical_l_max"].astype(float))
        > 1e-12 * scale_l
    ):
        raise RuntimeError("failed to recover canonical middle latency threshold row")
    if np.any(
        np.abs(canonical["c_max"].astype(float) - canonical["canonical_c_max"].astype(float))
        > 1e-12 * scale_c
    ):
        raise RuntimeError("failed to recover canonical middle cost threshold row")
    return canonical.reset_index(drop=True)


def select_canonical_v2_triplet(
    canonical_landscape: pd.DataFrame,
    *,
    nominal_min: float = DEFAULT_NOMINAL_MIN,
    stress_min: float = DEFAULT_STRESS_MIN,
    stress_max: float = DEFAULT_STRESS_MAX,
) -> pd.DataFrame:
    """Apply the proposed gate and source policy to canonical representatives."""
    passing = canonical_landscape[
        (canonical_landscape["area_rho_0p95"].astype(float) >= float(nominal_min))
        & (canonical_landscape["area_rho_0p99"].astype(float) >= float(stress_min))
        & (canonical_landscape["area_rho_0p99"].astype(float) <= float(stress_max))
        & canonical_landscape["descriptive_role"].astype(str).isin(REQUIRED_ROLES)
    ].copy()

    selected_rows: list[pd.Series] = []
    for role in REQUIRED_ROLES:
        role_rows = passing[passing["descriptive_role"].astype(str) == role].copy()
        if role_rows.empty:
            raise RuntimeError(f"proposed gate leaves no canonical candidate for role={role}")

        chosen_source = None
        source_rows = pd.DataFrame()
        for source in SOURCE_PREFERENCE[role]:
            candidate_source_rows = role_rows[
                role_rows["ar_augmentation_type"].astype(str) == source
            ].copy()
            if not candidate_source_rows.empty:
                chosen_source = source
                source_rows = candidate_source_rows
                break
        if chosen_source is None:
            available = sorted(role_rows["ar_augmentation_type"].astype(str).unique())
            raise RuntimeError(
                f"no allowed source family for role={role}; available={available}"
            )

        ranked = source_rows.sort_values(
            ["area_rho_0p95", "area_rho_0p99", "l_max", "c_max", "q_min", "region_id"],
            ascending=[False, True, True, True, True, True],
            kind="mergesort",
        )
        row = ranked.iloc[0].copy()
        row["v2_selected_source"] = chosen_source
        row["v2_nominal_gate_min"] = float(nominal_min)
        row["v2_stress_gate_min"] = float(stress_min)
        row["v2_stress_gate_max"] = float(stress_max)
        selected_rows.append(row)

    output = pd.DataFrame(selected_rows)
    output["selection_role"] = output["descriptive_role"].astype(str)
    return output.sort_values("selection_role").reset_index(drop=True)


def _load_relative_epsilon(configuration_path: Path) -> float:
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    return float(configuration["admissibility_scan"]["threshold_relative_epsilon"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "first_science/phase1/results/"
            "v2_multi_rho_candidate_landscape_D300000000_d0.200/"
            "candidate_multi_rho_summary.csv"
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("first_science/phase1/config_phase1_discovery_v1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "first_science/phase1/results/"
            "v2_multi_rho_candidate_landscape_D300000000_d0.200/"
            "v2_canonical_triplet_for_human_review.csv"
        ),
    )
    args = parser.parse_args()

    landscape = pd.read_csv(args.input)
    relative_epsilon = _load_relative_epsilon(args.config)
    canonical = collapse_epsilon_brackets(landscape, relative_epsilon)
    selected = select_canonical_v2_triplet(canonical)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(args.output, index=False)

    print("PHASE1_V2_CANONICAL_TRIPLET_PASS")
    print(f"threshold_relative_epsilon={relative_epsilon:g}")
    print("gate=R95>=0.95; 0.5<=R99<=0.95")
    print("selection_frozen=false")
    print("human_review_required_before_freeze=true")
    columns = [
        "selection_role",
        "region_id",
        "v2_selected_source",
        "l_max",
        "c_max",
        "q_min",
        "area_rho_0p95",
        "area_rho_0p975",
        "area_rho_0p99",
        "sigma_120_rho_0p95",
        "sigma_240_rho_0p95",
        "sigma_120_rho_0p99",
        "sigma_240_rho_0p99",
        "latency_failure_count",
        "cost_failure_count",
    ]
    available = [column for column in columns if column in selected.columns]
    pd.set_option("display.precision", 17)
    pd.set_option("display.max_columns", None)
    print(selected[available].to_string(index=False))
    print(f"output={args.output.resolve()}")


if __name__ == "__main__":
    main()
