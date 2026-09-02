"""Select complementary Phase-1 white-box finalists from N=10 discovery results.

This module is simulator-independent. It consumes the already generated
white-box atlas tables and exact-event sigma diagnostics. It never uses I1, M0,
or M1 outcomes. Selection is discovery-only: the resulting JSON is a proposal
that must be reviewed and frozen before N=100 confirmation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


SELECTION_ROLES = ("latency", "cost", "mixed")
MIN_FAILED_BY_STOP = 4
MIN_UNIQUE_FIRST_VIOLATION_TIMES = 4
MIN_DOMINANT_CAUSE_COUNT = 3
MIN_MIXED_CAUSE_COUNT = 2
MAX_MIXED_CAUSE_IMBALANCE = 2
MAX_N10_TARGET_DISTANCE = 0.051


def summarize_reported_curve_shape(
    survival_curves: pd.DataFrame,
    anchor_horizon: float,
) -> pd.DataFrame:
    """Summarize coarse stored curve shape without redefining exact-event sigma.

    The stored horizon grid is used only for descriptive ranking quantities. Exact
    first-violation timing remains supplied by ``sigma_curve_diagnostics.py``.

    Args:
        survival_curves: Stored reporting-grid curves for all scanned regions.
        anchor_horizon: Frozen anchor horizon H*.

    Returns:
        One row per region with start/anchor/stop survival and level counts.

    Called by:
        - ``build_whitebox_candidate_table`` in this module.
        - ``test_curve_shape_summary`` in ``test_whitebox_candidate_selection.py``.
    """
    required = {"physical_setting_id", "region_id", "horizon", "sigma"}
    missing = required.difference(survival_curves.columns)
    if missing:
        raise ValueError(f"survival_curves missing columns: {sorted(missing)}")

    rows: list[dict[str, object]] = []
    for (physical_setting_id, region_id), curve in survival_curves.groupby(
        ["physical_setting_id", "region_id"], sort=True
    ):
        ordered = curve.sort_values("horizon")
        horizons = ordered["horizon"].astype(float).to_numpy()
        sigmas = ordered["sigma"].astype(float).to_numpy()
        anchor_index = int(np.argmin(np.abs(horizons - float(anchor_horizon))))
        if abs(float(horizons[anchor_index]) - float(anchor_horizon)) > 1e-12:
            raise ValueError("anchor horizon must be present in stored reporting curve")
        post_anchor = sigmas[horizons >= float(anchor_horizon) - 1e-12]
        rows.append(
            {
                "physical_setting_id": str(physical_setting_id),
                "region_id": str(region_id),
                "sigma_start": float(sigmas[0]),
                "sigma_anchor_from_curve": float(sigmas[anchor_index]),
                "sigma_stop": float(sigmas[-1]),
                "post_anchor_drop": float(sigmas[anchor_index] - sigmas[-1]),
                "n_distinct_sigma_levels": int(len(np.unique(sigmas))),
                "n_post_anchor_sigma_levels": int(len(np.unique(post_anchor))),
            }
        )
    return pd.DataFrame(rows)


def build_whitebox_candidate_table(
    representative_regions: pd.DataFrame,
    sigma_diagnostics: pd.DataFrame,
    survival_curves: pd.DataFrame,
    anchor_horizon: float,
    target_survival: float,
) -> pd.DataFrame:
    """Merge N=10 AR, exact-event, cause, and curve-shape diagnostics.

    Args:
        representative_regions: Representative AR table from the offline scan.
        sigma_diagnostics: Exact-event resolution/convergence diagnostics.
        survival_curves: Reporting-grid survival curves for all regions.
        anchor_horizon: Frozen H*.
        target_survival: Nominal target used only to define bracket proximity.

    Returns:
        Candidate table containing only regions with exact diagnostics.

    Called by:
        - ``select_complementary_whitebox_proposal`` in this module.
        - ``execute_whitebox_candidate_selection`` in this module.
        - unit tests in ``test_whitebox_candidate_selection.py``.
    """
    merge_keys = ["physical_setting_id", "region_id", "l_max", "c_max", "q_min"]
    candidates = representative_regions.merge(
        sigma_diagnostics,
        on=merge_keys,
        how="inner",
        suffixes=("", "_diagnostic"),
    )
    curve_summary = summarize_reported_curve_shape(survival_curves, anchor_horizon)
    candidates = candidates.merge(
        curve_summary,
        on=["physical_setting_id", "region_id"],
        how="left",
    )
    if candidates.empty:
        raise ValueError("no representative ARs have exact-event diagnostics")

    # At N=10 the 0.9/1.0 values are intentionally treated as an empirical
    # bracket around 0.95. Round the distance so binary floating representation
    # cannot spuriously make one side of that symmetric bracket rank first.
    candidates["target_distance"] = (
        candidates["sigma_anchor"].astype(float) - float(target_survival)
    ).abs().round(12)
    candidates["observed_first_violations"] = (
        candidates["latency_first_count"].astype(int)
        + candidates["cost_first_count"].astype(int)
        + candidates["quality_first_count"].astype(int)
        + candidates["tie_first_count"].astype(int)
    )
    candidates["latency_minus_cost"] = (
        candidates["latency_first_count"].astype(int)
        - candidates["cost_first_count"].astype(int)
    )
    candidates["cost_minus_latency"] = -candidates["latency_minus_cost"]
    candidates["cause_imbalance"] = candidates["latency_minus_cost"].abs()
    candidates["balanced_cause_support"] = candidates[
        ["latency_first_count", "cost_first_count"]
    ].min(axis=1)
    return candidates


def filter_informative_n10_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    """Reject N=10 ARs that are too sparse to be useful next-phase benchmarks.

    Discovery does not require precision, but a finalist must expose enough
    first-violation structure to provide an informative sigma curve. A case with
    only one or two failures by H=240 is therefore retained in raw discovery
    tables but is not eligible for the final white-box battery.

    Called by:
        - ``rank_candidates_for_role`` in this module.
        - ``test_sparse_candidates_fail_information_gate`` in
          ``test_whitebox_candidate_selection.py``.
    """
    return candidates[
        (candidates["target_distance"] <= MAX_N10_TARGET_DISTANCE)
        & (candidates["n_failed_by_stop"] >= MIN_FAILED_BY_STOP)
        & (
            candidates["n_unique_first_violation_times"]
            >= MIN_UNIQUE_FIRST_VIOLATION_TIMES
        )
        & (candidates["n_distinct_sigma_levels"] >= MIN_FAILED_BY_STOP)
    ].copy()


def rank_candidates_for_role(candidates: pd.DataFrame, role: str) -> pd.DataFrame:
    """Rank informative candidates for one transparent diagnostic role.

    A hard information gate is applied before role assignment. Latency/cost
    finalists require at least three first violations from the named cause and
    at least a 2:1 dominance over the opposite cause. Mixed finalists require at
    least two latency-first and two cost-first trajectories with an imbalance of
    at most two. Within those role constraints, target-bracketing and temporal
    curve informativeness are ranked before additional cause purity.

    Args:
        candidates: Merged discovery candidate table.
        role: One of ``latency``, ``cost``, or ``mixed``.

    Returns:
        Qualifying candidates ordered best-first for the requested role.

    Called by:
        - ``select_complementary_whitebox_proposal`` in this module.
        - unit tests in ``test_whitebox_candidate_selection.py``.
    """
    if role not in SELECTION_ROLES:
        raise ValueError(f"unknown selection role: {role}")

    ranked = filter_informative_n10_candidates(candidates)
    if role == "latency":
        ranked = ranked[
            (ranked["latency_first_count"] >= MIN_DOMINANT_CAUSE_COUNT)
            & (
                ranked["latency_first_count"]
                >= 2 * ranked["cost_first_count"].clip(lower=1)
            )
        ].copy()
        role_sort = ["latency_minus_cost", "latency_first_count"]
        role_ascending = [False, False]
    elif role == "cost":
        ranked = ranked[
            (ranked["cost_first_count"] >= MIN_DOMINANT_CAUSE_COUNT)
            & (
                ranked["cost_first_count"]
                >= 2 * ranked["latency_first_count"].clip(lower=1)
            )
        ].copy()
        role_sort = ["cost_minus_latency", "cost_first_count"]
        role_ascending = [False, False]
    else:
        ranked = ranked[
            (ranked["latency_first_count"] >= MIN_MIXED_CAUSE_COUNT)
            & (ranked["cost_first_count"] >= MIN_MIXED_CAUSE_COUNT)
            & (ranked["cause_imbalance"] <= MAX_MIXED_CAUSE_IMBALANCE)
        ].copy()
        role_sort = ["cause_imbalance", "balanced_cause_support"]
        role_ascending = [True, False]

    if ranked.empty:
        return ranked

    ranked["split_half_curve_supremum_difference"] = ranked[
        "split_half_curve_supremum_difference"
    ].fillna(np.inf)
    sort_columns = [
        "target_distance",
        "n_unique_first_violation_times",
        "longest_plateau_fraction_of_domain",
        "n_failed_by_stop",
        *role_sort,
        "split_half_curve_supremum_difference",
        "physical_setting_id",
        "region_id",
    ]
    sort_ascending = [
        True,
        False,
        True,
        False,
        *role_ascending,
        True,
        True,
        True,
    ]
    return ranked.sort_values(sort_columns, ascending=sort_ascending).reset_index(drop=True)


def select_complementary_whitebox_proposal(candidates: pd.DataFrame) -> pd.DataFrame:
    """Select one distinct informative candidate for each diagnostic role.

    Args:
        candidates: Merged discovery candidate table.

    Returns:
        Three-row proposal ordered latency, cost, mixed. A candidate region is
        not reused across roles.

    Raises:
        ValueError: If the current N=10 discovery results do not contain a
            genuinely informative candidate for one of the roles. This is a
            signal to expand/refine discovery, not to weaken the quality gate.

    Called by:
        - ``execute_whitebox_candidate_selection`` in this module.
        - ``test_complementary_selection_uses_distinct_regions`` in tests.
    """
    selected_rows: list[pd.Series] = []
    used_region_ids: set[str] = set()
    for role in SELECTION_ROLES:
        ranked = rank_candidates_for_role(candidates, role)
        ranked = ranked[~ranked["region_id"].astype(str).isin(used_region_ids)]
        if ranked.empty:
            raise ValueError(
                f"no informative N=10 candidate for role '{role}'; "
                "expand/refine discovery rather than freezing a sparse curve"
            )
        row = ranked.iloc[0].copy()
        row["selection_role"] = role
        selected_rows.append(row)
        used_region_ids.add(str(row["region_id"]))
    return pd.DataFrame(selected_rows).reset_index(drop=True)


def proposal_dataframe_to_manifest(
    selected: pd.DataFrame,
    source_results_directory: Path,
    target_survival: float,
    anchor_horizon: float,
) -> dict[str, object]:
    """Convert selected full-precision rows into a reviewable JSON proposal.

    Called by:
        - ``execute_whitebox_candidate_selection`` in this module.
    """
    whiteboxes: list[dict[str, object]] = []
    for index, row in selected.iterrows():
        whiteboxes.append(
            {
                "case_id": f"WB{index + 1}_{row['selection_role']}",
                "selection_role": str(row["selection_role"]),
                "physical_setting_id": str(row["physical_setting_id"]),
                "source_region_id": str(row["region_id"]),
                "center_instruction_mean": float(row["center_instruction_mean"]),
                "dispersion": float(row["dispersion"]),
                "l_max": float(row["l_max"]),
                "c_max": float(row["c_max"]),
                "q_min": float(row["q_min"]),
                "discovery_sigma_anchor": float(row["sigma_anchor"]),
                "latency_first_count": int(row["latency_first_count"]),
                "cost_first_count": int(row["cost_first_count"]),
                "n_unique_first_violation_times": int(row["n_unique_first_violation_times"]),
                "n_failed_by_stop": int(row["n_failed_by_stop"]),
                "longest_plateau_fraction_of_domain": float(
                    row["longest_plateau_fraction_of_domain"]
                ),
                "split_half_curve_supremum_difference": float(
                    row["split_half_curve_supremum_difference"]
                ),
            }
        )
    return {
        "status": "PROPOSED_FROM_N10_DISCOVERY_REQUIRES_REVIEW",
        "selection_semantics": (
            "White-box-only N=10 discovery proposal. Every finalist passed the "
            "minimum information gate before role ranking. Review once, then copy "
            "the exact physical parameters and A into selected_whiteboxes.json "
            "with status FROZEN_FOR_CONFIRMATION before any N=100 run. "
            "Confirmation must not recalibrate A."
        ),
        "quality_gate": {
            "min_failed_by_stop": MIN_FAILED_BY_STOP,
            "min_unique_first_violation_times": MIN_UNIQUE_FIRST_VIOLATION_TIMES,
            "min_dominant_cause_count": MIN_DOMINANT_CAUSE_COUNT,
            "min_mixed_cause_count_each": MIN_MIXED_CAUSE_COUNT,
            "max_mixed_cause_imbalance": MAX_MIXED_CAUSE_IMBALANCE,
            "max_n10_target_distance": MAX_N10_TARGET_DISTANCE,
        },
        "source_results_directory": str(source_results_directory),
        "anchor_horizon": float(anchor_horizon),
        "target_survival": float(target_survival),
        "whiteboxes": whiteboxes,
    }


def execute_whitebox_candidate_selection(
    results_directory: Path,
    target_survival: float,
) -> pd.DataFrame:
    """Rank discovery candidates and write a three-whitebox proposal.

    Side effects:
        Writes ``whitebox_selection/whitebox_candidate_ranking.csv`` and
        ``whitebox_selection/selected_whiteboxes_proposal.json`` below the
        supplied results directory.

    Called by:
        - ``main`` in this module.
    """
    representatives = pd.read_csv(results_directory / "representative_regions_by_sigma.csv")
    diagnostics = pd.read_csv(
        results_directory / "sigma_plots" / "sigma_curve_resolution_diagnostics.csv"
    )
    survival_curves = pd.read_csv(results_directory / "survival_curves.csv")
    configuration = json.loads(
        (results_directory / "effective_config.json").read_text(encoding="utf-8")
    )
    anchor_horizon = float(configuration["admissibility_scan"]["anchor_horizon"])

    candidates = build_whitebox_candidate_table(
        representatives,
        diagnostics,
        survival_curves,
        anchor_horizon=anchor_horizon,
        target_survival=target_survival,
    )

    output_directory = results_directory / "whitebox_selection"
    output_directory.mkdir(parents=True, exist_ok=True)
    candidates.sort_values(
        ["target_distance", "physical_setting_id", "sigma_anchor", "region_id"]
    ).to_csv(output_directory / "whitebox_candidate_ranking.csv", index=False)

    selected = select_complementary_whitebox_proposal(candidates)
    manifest = proposal_dataframe_to_manifest(
        selected,
        source_results_directory=results_directory,
        target_survival=target_survival,
        anchor_horizon=anchor_horizon,
    )
    (output_directory / "selected_whiteboxes_proposal.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    display_columns = [
        "selection_role",
        "physical_setting_id",
        "region_id",
        "center_instruction_mean",
        "dispersion",
        "l_max",
        "c_max",
        "q_min",
        "sigma_anchor",
        "latency_first_count",
        "cost_first_count",
        "n_unique_first_violation_times",
        "n_failed_by_stop",
        "longest_plateau_fraction_of_domain",
        "split_half_curve_supremum_difference",
    ]
    print("PHASE1_WHITEBOX_SELECTION_PROPOSAL_PASS")
    print(selected[display_columns].to_string(index=False))
    print(
        "proposal_manifest="
        + str(output_directory / "selected_whiteboxes_proposal.json")
    )
    return selected


def main() -> None:
    """Command-line entry point for N=10 white-box discovery selection."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=module_directory / "results" / "development_atlas",
    )
    parser.add_argument("--target-survival", type=float, default=0.95)
    args = parser.parse_args()
    execute_whitebox_candidate_selection(
        args.results.resolve(),
        target_survival=float(args.target_survival),
    )


if __name__ == "__main__":
    main()
