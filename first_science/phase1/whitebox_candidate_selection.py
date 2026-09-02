"""Select Phase-1 white-box finalists using exact N=10 survival-area metrics.

The former sigma(120)≈0.95 / minimum-failure selection rule is superseded.
Selection now applies a configuration-driven normalized restricted survival-area
gate, then classifies latency-dominant, cost-dominant, and genuinely mixed L/C
roles. The area band is a gate only: candidates are never optimized toward its
midpoint. Temporal richness is secondary ranking information, not a hard common
failure-count gate. I1, M0 and M1 remain outside the selection loop.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from selection_policy import SurvivalAreaSelectionPolicy, load_survival_area_selection_policy

SELECTION_ROLES = ("latency", "cost", "mixed")


def build_whitebox_candidate_table(
    exact_auc_metrics: pd.DataFrame,
    policy: SurvivalAreaSelectionPolicy,
) -> pd.DataFrame:
    """Prepare exact-event N=10 metrics for transparent role ranking."""
    required = {
        "physical_setting_id", "region_id", "center_instruction_mean", "dispersion",
        "l_max", "c_max", "q_min", "normalized_restricted_survival_area",
        "restricted_survival_area_seconds", "sigma_120_reporting",
        "latency_first_count_exact", "cost_first_count_exact",
        "quality_first_count_exact", "tie_first_count_exact", "censored_count_exact",
        "n_unique_first_violation_times", "maximum_empirical_jump",
        "longest_plateau_fraction_of_domain",
    }
    missing = required.difference(exact_auc_metrics.columns)
    if missing:
        raise ValueError("exact AUC candidate metrics are incomplete: " + ", ".join(sorted(missing)))

    candidates = exact_auc_metrics.copy()
    candidates["latency_first_count"] = candidates["latency_first_count_exact"].astype(int)
    candidates["cost_first_count"] = candidates["cost_first_count_exact"].astype(int)
    candidates["quality_first_count"] = candidates["quality_first_count_exact"].astype(int)
    candidates["tie_first_count"] = candidates["tie_first_count_exact"].astype(int)
    candidates["censored_count"] = candidates["censored_count_exact"].astype(int)
    candidates["latency_minus_cost"] = candidates["latency_first_count"] - candidates["cost_first_count"]
    candidates["cost_minus_latency"] = -candidates["latency_minus_cost"]
    candidates["cause_imbalance"] = candidates["latency_minus_cost"].abs()
    candidates["balanced_cause_support"] = candidates[["latency_first_count", "cost_first_count"]].min(axis=1)
    candidates["inside_survival_area_band"] = (
        candidates["normalized_restricted_survival_area"].astype(float) >= policy.area_min - 1e-12
    ) & (
        candidates["normalized_restricted_survival_area"].astype(float) <= policy.area_max + 1e-12
    )
    return candidates


def filter_nondegenerate_n10_candidates(
    candidates: pd.DataFrame,
    policy: SurvivalAreaSelectionPolicy,
) -> pd.DataFrame:
    """Apply only the configured normalized survival-area nondegeneracy gate."""
    return candidates[candidates["inside_survival_area_band"]].copy()


def rank_candidates_for_role(
    candidates: pd.DataFrame,
    role: str,
    policy: SurvivalAreaSelectionPolicy,
) -> pd.DataFrame:
    """Rank area-eligible candidates for one failure-mechanism role."""
    if role not in SELECTION_ROLES:
        raise ValueError(f"unknown selection role: {role}")

    ranked = filter_nondegenerate_n10_candidates(candidates, policy)
    if role == "latency":
        opposite = ranked["cost_first_count"].clip(lower=1)
        ranked = ranked[
            (ranked["latency_first_count"] >= policy.min_dominant_cause_count)
            & (ranked["latency_first_count"] >= policy.dominance_ratio * opposite)
        ].copy()
        role_sort = ["latency_minus_cost", "latency_first_count"]
        role_ascending = [False, False]
    elif role == "cost":
        opposite = ranked["latency_first_count"].clip(lower=1)
        ranked = ranked[
            (ranked["cost_first_count"] >= policy.min_dominant_cause_count)
            & (ranked["cost_first_count"] >= policy.dominance_ratio * opposite)
        ].copy()
        role_sort = ["cost_minus_latency", "cost_first_count"]
        role_ascending = [False, False]
    else:
        ranked = ranked[
            (ranked["latency_first_count"] >= policy.min_mixed_cause_count_each)
            & (ranked["cost_first_count"] >= policy.min_mixed_cause_count_each)
            & (ranked["cause_imbalance"] <= policy.max_mixed_cause_imbalance)
        ].copy()
        role_sort = ["cause_imbalance", "balanced_cause_support"]
        role_ascending = [True, False]

    if ranked.empty:
        return ranked

    sort_columns = [
        *role_sort,
        "n_unique_first_violation_times",
        "longest_plateau_fraction_of_domain",
        "maximum_empirical_jump",
        "physical_setting_id",
        "region_id",
    ]
    sort_ascending = [*role_ascending, False, True, True, True, True]
    output = ranked.sort_values(sort_columns, ascending=sort_ascending).reset_index(drop=True)
    output["role_rank"] = np.arange(1, len(output) + 1, dtype=int)
    return output


def _select_distinct_rows_in_one_setting(
    ranked_by_role: dict[str, pd.DataFrame],
    physical_setting_id: str,
) -> list[pd.Series] | None:
    """Choose the best distinct role rows within one matched physical regime."""
    role_rows: dict[str, pd.DataFrame] = {}
    for role in SELECTION_ROLES:
        rows = ranked_by_role[role][
            ranked_by_role[role]["physical_setting_id"].astype(str) == str(physical_setting_id)
        ].head(20)
        if rows.empty:
            return None
        role_rows[role] = rows

    best: tuple[float, list[pd.Series]] | None = None
    for latency_row, cost_row, mixed_row in itertools.product(
        [row for _, row in role_rows["latency"].iterrows()],
        [row for _, row in role_rows["cost"].iterrows()],
        [row for _, row in role_rows["mixed"].iterrows()],
    ):
        rows = [latency_row, cost_row, mixed_row]
        if len({str(row["region_id"]) for row in rows}) != 3:
            continue
        score = float(sum(int(row["role_rank"]) for row in rows))
        if best is None or score < best[0]:
            best = (score, rows)
    return None if best is None else best[1]


def select_complementary_whitebox_proposal(
    candidates: pd.DataFrame,
    policy: SurvivalAreaSelectionPolicy,
    prefer_matched_physical_regime: bool = True,
) -> pd.DataFrame:
    """Select one latency, cost and mixed finalist from the AUC-qualified pool."""
    ranked_by_role = {role: rank_candidates_for_role(candidates, role, policy) for role in SELECTION_ROLES}
    missing = [role for role, rows in ranked_by_role.items() if rows.empty]
    if missing:
        raise ValueError(
            "no survival-area-qualified N=10 candidate for role(s) " + ",".join(missing)
            + "; keep the configured area band fixed and report/refine discovery"
        )

    selected_rows: list[pd.Series] | None = None
    matched = False
    if prefer_matched_physical_regime:
        common_settings = set(ranked_by_role[SELECTION_ROLES[0]]["physical_setting_id"].astype(str))
        for role in SELECTION_ROLES[1:]:
            common_settings &= set(ranked_by_role[role]["physical_setting_id"].astype(str))
        best_match: tuple[float, str, list[pd.Series]] | None = None
        for setting_id in sorted(common_settings):
            rows = _select_distinct_rows_in_one_setting(ranked_by_role, setting_id)
            if rows is None:
                continue
            score = float(sum(int(row["role_rank"]) for row in rows))
            candidate = (score, setting_id, rows)
            if best_match is None or candidate[:2] < best_match[:2]:
                best_match = candidate
        if best_match is not None:
            selected_rows = best_match[2]
            matched = True

    if selected_rows is None:
        selected_rows = []
        used: set[str] = set()
        for role in SELECTION_ROLES:
            available = ranked_by_role[role][~ranked_by_role[role]["region_id"].astype(str).isin(used)]
            if available.empty:
                raise ValueError(f"cannot select a distinct candidate for role {role}")
            row = available.iloc[0].copy()
            selected_rows.append(row)
            used.add(str(row["region_id"]))

    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    selected["selection_role"] = list(SELECTION_ROLES)
    selected["matched_physical_regime"] = bool(matched)
    return selected


def proposal_dataframe_to_manifest(
    selected: pd.DataFrame,
    source_results_directory: Path,
    policy: SurvivalAreaSelectionPolicy,
    policy_configuration_path: Path,
) -> dict[str, object]:
    """Convert exact AUC-selected rows into a reviewable proposal manifest."""
    whiteboxes: list[dict[str, object]] = []
    for index, row in selected.iterrows():
        whiteboxes.append(
            {
                "case_id": f"WB{index + 1}_{row['selection_role']}",
                "selection_role": str(row["selection_role"]),
                "physical_setting_id": str(row["physical_setting_id"]),
                "source_region_id": str(row["region_id"]),
                "equivalent_region_ids": str(row.get("equivalent_region_ids", row["region_id"])),
                "center_instruction_mean": float(row["center_instruction_mean"]),
                "dispersion": float(row["dispersion"]),
                "l_max": float(row["l_max"]),
                "c_max": float(row["c_max"]),
                "q_min": float(row["q_min"]),
                "discovery_normalized_restricted_survival_area": float(row["normalized_restricted_survival_area"]),
                "discovery_restricted_survival_area_seconds": float(row["restricted_survival_area_seconds"]),
                "discovery_sigma_120_reporting": float(row["sigma_120_reporting"]),
                "latency_first_count": int(row["latency_first_count"]),
                "cost_first_count": int(row["cost_first_count"]),
                "censored_count": int(row["censored_count"]),
                "n_unique_first_violation_times": int(row["n_unique_first_violation_times"]),
                "longest_plateau_fraction_of_domain": float(row["longest_plateau_fraction_of_domain"]),
                "maximum_empirical_jump": float(row["maximum_empirical_jump"]),
            }
        )

    return {
        "status": "PROPOSED_FROM_N10_AUC_DISCOVERY_REQUIRES_REVIEW",
        "selection_semantics": (
            "Exact-event N=10 normalized restricted survival-area gate followed by "
            "failure-mechanism and temporal-richness ranking. The configured area "
            "interval is a gate only; no midpoint optimization and no sigma(120) "
            "target are used. Review once, freeze exact A/physical parameters, "
            "then confirm using a new disjoint N=100 seed bank."
        ),
        "policy_configuration": str(policy_configuration_path),
        "normalized_restricted_survival_area_gate": {
            "horizon_min": policy.horizon_min,
            "horizon_max": policy.horizon_max,
            "minimum": policy.area_min,
            "maximum": policy.area_max,
            "optimize_to_midpoint": False,
        },
        "role_evidence": {
            "min_dominant_cause_count": policy.min_dominant_cause_count,
            "dominance_ratio": policy.dominance_ratio,
            "min_mixed_cause_count_each": policy.min_mixed_cause_count_each,
            "max_mixed_cause_imbalance": policy.max_mixed_cause_imbalance,
        },
        "matched_physical_regime": bool(selected["matched_physical_regime"].all()),
        "source_results_directory": str(source_results_directory),
        "whiteboxes": whiteboxes,
    }


def execute_whitebox_candidate_selection(
    results_directory: Path,
    policy_configuration_path: Path,
) -> pd.DataFrame:
    """Apply the versioned AUC gate and write a three-whitebox proposal."""
    configuration = json.loads(policy_configuration_path.read_text(encoding="utf-8"))
    policy = load_survival_area_selection_policy(configuration)
    metrics_path = results_directory / "whitebox_selection" / "auc_candidate_metrics.csv"
    if not metrics_path.exists():
        raise FileNotFoundError(
            f"missing {metrics_path}; run `python exact_auc_candidate_metrics.py --results {results_directory}` first"
        )
    exact_metrics = pd.read_csv(metrics_path)
    candidates = build_whitebox_candidate_table(exact_metrics, policy)

    output_directory = results_directory / "whitebox_selection"
    output_directory.mkdir(parents=True, exist_ok=True)
    candidates.sort_values(
        ["inside_survival_area_band", "physical_setting_id", "normalized_restricted_survival_area", "region_id"],
        ascending=[False, True, True, True],
    ).to_csv(output_directory / "whitebox_candidate_ranking.csv", index=False)

    prefer_matched = bool(configuration.get("confirmation", {}).get("prefer_matched_physical_regime", True))
    selected = select_complementary_whitebox_proposal(
        candidates, policy, prefer_matched_physical_regime=prefer_matched
    )
    manifest = proposal_dataframe_to_manifest(
        selected, results_directory, policy, policy_configuration_path
    )
    proposal_path = output_directory / "selected_whiteboxes_proposal.json"
    proposal_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    display_columns = [
        "selection_role", "physical_setting_id", "region_id", "center_instruction_mean",
        "dispersion", "l_max", "c_max", "q_min",
        "normalized_restricted_survival_area", "restricted_survival_area_seconds",
        "sigma_120_reporting", "latency_first_count", "cost_first_count",
        "censored_count", "n_unique_first_violation_times",
        "longest_plateau_fraction_of_domain",
    ]
    print("PHASE1_WHITEBOX_AUC_SELECTION_PROPOSAL_PASS")
    print(
        f"area_gate=[{policy.area_min:.6g},{policy.area_max:.6g}] "
        f"horizon=[{policy.horizon_min:.6g},{policy.horizon_max:.6g}] "
        "midpoint_optimization=false"
    )
    print(selected[display_columns].to_string(index=False))
    print(f"proposal_manifest={proposal_path}")
    return selected


def main() -> None:
    """Command-line entry point for revised Phase-1 white-box selection."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=module_directory / "results" / "scientific_discovery_v1_full_domain_ar",
    )
    parser.add_argument(
        "--policy-config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    args = parser.parse_args()
    execute_whitebox_candidate_selection(args.results.resolve(), args.policy_config.resolve())


if __name__ == "__main__":
    main()
