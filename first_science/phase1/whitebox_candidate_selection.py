"""Select Phase-1 white-box finalists using N=10 SLA-compliance sigma curves.

The selector consumes offline metrics computed from the sealed N=10 physical
request ledgers. It applies the configured normalized SLA-compliance-area gate
at rho*=0.95, then identifies latency-dominant, cost-dominant and mixed L/C
request-failure regimes using all decided request failures. The area band is a
gate only; candidates are never optimized toward its midpoint. M0 and M1 remain
outside the selection loop.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from selection_policy import (
    SlaComplianceAreaSelectionPolicy,
    load_sla_compliance_area_selection_policy,
)
from sla_compliance_analysis import (
    calculate_empirical_sla_sigma_from_ledgers,
    calculate_exact_sla_sigma_step_curve,
)

SELECTION_ROLES = ("latency", "cost", "mixed")


def build_whitebox_candidate_table(
    sla_candidate_metrics: pd.DataFrame,
    policy: SlaComplianceAreaSelectionPolicy,
) -> pd.DataFrame:
    """Prepare N=10 SLA metrics for transparent role ranking.

    Called by:
        - ``execute_whitebox_candidate_selection`` in this module.
        - unit tests in ``test_whitebox_candidate_selection.py``.
    """
    required = {
        "physical_setting_id",
        "region_id",
        "center_instruction_mean",
        "dispersion",
        "l_max",
        "c_max",
        "q_min",
        "rho",
        "normalized_sla_compliance_area",
        "sla_compliance_area_seconds",
        "sigma_120_reporting",
        "sigma_240_reporting",
        "decided_request_count",
        "unresolved_request_count",
        "compliant_request_count",
        "failed_request_count",
        "latency_failure_count",
        "cost_failure_count",
        "quality_failure_count",
        "latency_failure_fraction_of_lc",
        "cost_failure_fraction_of_lc",
        "n_sigma_transition_times",
        "maximum_empirical_sigma_jump",
        "longest_sigma_plateau_fraction_of_domain",
    }
    missing = required.difference(sla_candidate_metrics.columns)
    if missing:
        raise ValueError(
            "SLA candidate metrics are incomplete: "
            + ", ".join(sorted(missing))
        )
    candidates = sla_candidate_metrics.copy()
    if not np.allclose(
        candidates["rho"].astype(float),
        float(policy.sla_definition.rho),
        atol=1e-12,
    ):
        raise ValueError("candidate rho differs from frozen search rho")

    candidates["inside_sla_compliance_area_band"] = (
        candidates["normalized_sla_compliance_area"].astype(float)
        >= policy.area_min - 1e-12
    ) & (
        candidates["normalized_sla_compliance_area"].astype(float)
        <= policy.area_max + 1e-12
    )
    candidates["lc_failure_count"] = (
        candidates["latency_failure_count"].astype(int)
        + candidates["cost_failure_count"].astype(int)
    )
    candidates["lc_failure_balance_error"] = (
        candidates["latency_failure_fraction_of_lc"].astype(float) - 0.5
    ).abs()
    return candidates


def filter_nondegenerate_n10_candidates(
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    """Apply only the configured SLA-compliance-area nondegeneracy gate.

    Called by:
        - ``rank_candidates_for_role`` in this module.
        - unit tests in ``test_whitebox_candidate_selection.py``.
    """
    return candidates[
        candidates["inside_sla_compliance_area_band"].astype(bool)
    ].copy()


def rank_candidates_for_role(
    candidates: pd.DataFrame,
    role: str,
    policy: SlaComplianceAreaSelectionPolicy,
) -> pd.DataFrame:
    """Rank area-eligible candidates by all-request L/C failure composition.

    Latency/cost dominance uses the configured ratio. Mixed means both L and C
    failures are present and neither dominates the other by that ratio. This
    uses all decided request-level failures, never one first failure per
    trajectory.

    Called by:
        - ``select_complementary_whitebox_proposal`` in this module.
        - ``diagnose_whitebox_selection.py``.
        - unit tests in ``test_whitebox_candidate_selection.py``.
    """
    if role not in SELECTION_ROLES:
        raise ValueError(f"unknown selection role: {role}")

    ranked = filter_nondegenerate_n10_candidates(candidates)
    latency = ranked["latency_failure_count"].astype(int)
    cost = ranked["cost_failure_count"].astype(int)
    ratio = float(policy.dominance_ratio)

    if role == "latency":
        ranked = ranked[
            (latency > 0) & (latency >= ratio * cost.clip(lower=1))
        ].copy()
        role_sort = ["latency_failure_fraction_of_lc"]
        role_ascending = [False]
    elif role == "cost":
        ranked = ranked[
            (cost > 0) & (cost >= ratio * latency.clip(lower=1))
        ].copy()
        role_sort = ["cost_failure_fraction_of_lc"]
        role_ascending = [False]
    else:
        smaller = pd.concat([latency, cost], axis=1).min(axis=1)
        larger = pd.concat([latency, cost], axis=1).max(axis=1)
        failure_ratio = larger / smaller.replace(0, np.nan)
        ranked = ranked[
            (latency > 0)
            & (cost > 0)
            & (failure_ratio < ratio - 1e-12)
        ].copy()
        role_sort = ["lc_failure_balance_error"]
        role_ascending = [True]

    if ranked.empty:
        return ranked

    sort_columns = [
        *role_sort,
        "n_sigma_transition_times",
        "longest_sigma_plateau_fraction_of_domain",
        "maximum_empirical_sigma_jump",
        "physical_setting_id",
        "region_id",
    ]
    sort_ascending = [
        *role_ascending,
        False,
        True,
        True,
        True,
        True,
    ]
    output = ranked.sort_values(
        sort_columns, ascending=sort_ascending
    ).reset_index(drop=True)
    output["role_rank"] = np.arange(1, len(output) + 1, dtype=int)
    return output


def _select_distinct_rows_in_one_setting(
    ranked_by_role: dict[str, pd.DataFrame],
    physical_setting_id: str,
) -> list[pd.Series] | None:
    """Choose the best distinct L/C/mixed rows inside one physical regime.

    Called by:
        - ``select_complementary_whitebox_proposal`` in this module.
    """
    role_rows: dict[str, pd.DataFrame] = {}
    for role in SELECTION_ROLES:
        rows = ranked_by_role[role][
            ranked_by_role[role]["physical_setting_id"].astype(str)
            == str(physical_setting_id)
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
    policy: SlaComplianceAreaSelectionPolicy,
    prefer_matched_physical_regime: bool = True,
) -> pd.DataFrame:
    """Select one latency, cost and mixed SLA finalist.

    Called by:
        - ``execute_whitebox_candidate_selection`` in this module.
        - unit tests in ``test_whitebox_candidate_selection.py``.
    """
    ranked_by_role = {
        role: rank_candidates_for_role(candidates, role, policy)
        for role in SELECTION_ROLES
    }
    missing = [role for role, rows in ranked_by_role.items() if rows.empty]
    if missing:
        raise ValueError(
            "no SLA-area-qualified N=10 candidate for role(s) "
            + ",".join(missing)
            + "; keep rho*=0.95 and the configured area band fixed, then "
            "report/refine discovery rather than tuning on M0/M1"
        )

    selected_rows: list[pd.Series] | None = None
    matched = False
    if prefer_matched_physical_regime:
        common_settings = set(
            ranked_by_role[SELECTION_ROLES[0]]["physical_setting_id"].astype(str)
        )
        for role in SELECTION_ROLES[1:]:
            common_settings &= set(
                ranked_by_role[role]["physical_setting_id"].astype(str)
            )
        best_match: tuple[float, str, list[pd.Series]] | None = None
        for setting_id in sorted(common_settings):
            rows = _select_distinct_rows_in_one_setting(
                ranked_by_role, setting_id
            )
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
            available = ranked_by_role[role][
                ~ranked_by_role[role]["region_id"].astype(str).isin(used)
            ]
            if available.empty:
                raise ValueError(
                    f"cannot select a distinct candidate for role {role}"
                )
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
    policy: SlaComplianceAreaSelectionPolicy,
    policy_configuration_path: Path,
) -> dict[str, object]:
    """Convert selected SLA rows to a reviewable pre-confirmation manifest.

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
                "equivalent_region_ids": str(
                    row.get("equivalent_region_ids", row["region_id"])
                ),
                "center_instruction_mean": float(
                    row["center_instruction_mean"]
                ),
                "dispersion": float(row["dispersion"]),
                "l_max": float(row["l_max"]),
                "c_max": float(row["c_max"]),
                "q_min": float(row["q_min"]),
                "rho": float(policy.sla_definition.rho),
                "accounting_origin": float(
                    policy.sla_definition.accounting_origin
                ),
                "accounting_window": "cumulative_[0,H]_from_t0",
                "discovery_normalized_sla_compliance_area": float(
                    row["normalized_sla_compliance_area"]
                ),
                "discovery_sla_compliance_area_seconds": float(
                    row["sla_compliance_area_seconds"]
                ),
                "discovery_sigma_120": float(row["sigma_120_reporting"]),
                "discovery_sigma_240": float(row["sigma_240_reporting"]),
                "decided_request_count": int(row["decided_request_count"]),
                "failed_request_count": int(row["failed_request_count"]),
                "latency_failure_count": int(
                    row["latency_failure_count"]
                ),
                "cost_failure_count": int(row["cost_failure_count"]),
                "quality_failure_count": int(
                    row["quality_failure_count"]
                ),
                "n_sigma_transition_times": int(
                    row["n_sigma_transition_times"]
                ),
                "longest_sigma_plateau_fraction_of_domain": float(
                    row["longest_sigma_plateau_fraction_of_domain"]
                ),
            }
        )

    return {
        "status": "PROPOSED_FROM_N10_SLA_DISCOVERY_REQUIRES_REVIEW",
        "selection_semantics": (
            "N=10 offline SLA-compliance reranking of sealed physical request "
            "ledgers. Search rho*=0.95 is fixed. Every H uses cumulative [0,H] "
            "accounting from the prescribed t=0 origin. The normalized SLA-area "
            "interval is a nondegeneracy gate only; no midpoint optimization. "
            "Failure roles use all decided request-level L/C failures. Review "
            "once, freeze exact physical parameters/A/semantics, then assign a "
            "new disjoint N=100 confirmation seed bank."
        ),
        "policy_configuration": str(policy_configuration_path),
        "search_rho": float(policy.sla_definition.rho),
        "accounting_origin": float(policy.sla_definition.accounting_origin),
        "accounting_window": "cumulative_[0,H]_from_t0",
        "normalized_sla_compliance_area_gate": {
            "horizon_min": policy.horizon_min,
            "horizon_max": policy.horizon_max,
            "minimum": policy.area_min,
            "maximum": policy.area_max,
            "optimize_to_midpoint": False,
        },
        "role_evidence": {
            "dominance_ratio": policy.dominance_ratio,
            "mixed_semantics": (
                "both L and C failures present and neither dominates by the "
                "configured dominance ratio"
            ),
        },
        "paired_matched_physical_regime": bool(
            selected["matched_physical_regime"].all()
        ),
        "source_results_directory": str(source_results_directory),
        "whiteboxes": whiteboxes,
    }


def write_selected_sla_candidate_diagnostics(
    selected: pd.DataFrame,
    all_ledgers: pd.DataFrame,
    configuration: dict,
    policy: SlaComplianceAreaSelectionPolicy,
    output_directory: Path,
) -> None:
    """Write request-level and curve diagnostics for the three N=10 finalists.

    Args:
        selected: Three proposed white-box rows.
        all_ledgers: Sealed discovery request ledgers.
        configuration: Current Phase-1 configuration.
        policy: Frozen SLA search policy.
        output_directory: White-box selection output directory.

    Side effects:
        Writes detailed decision/trajectory/sigma CSVs and an overlay PNG.

    Called by:
        - ``execute_whitebox_candidate_selection`` in this module.
    """
    horizons = list(map(float, configuration["horizon"]["grid"]))
    stop_time = float(configuration["horizon"]["simulation_stop_time"])
    decision_frames: list[pd.DataFrame] = []
    trajectory_frames: list[pd.DataFrame] = []
    sigma_frames: list[pd.DataFrame] = []
    exact_frames: list[pd.DataFrame] = []

    figure, axis = plt.subplots(figsize=(8.0, 5.2))
    labels = {
        "latency": "L-dominant",
        "mixed": "Mixed L/C",
        "cost": "C-dominant",
    }

    for _, row in selected.iterrows():
        setting_ledgers = all_ledgers[
            all_ledgers["physical_setting_id"].astype(str)
            == str(row["physical_setting_id"])
        ].copy()
        sigma, trajectory_curves, decisions = (
            calculate_empirical_sla_sigma_from_ledgers(
                setting_ledgers,
                latency_threshold=float(row["l_max"]),
                cost_threshold=float(row["c_max"]),
                quality_threshold=float(row["q_min"]),
                horizons=horizons,
                stop_time=stop_time,
                sla_definition=policy.sla_definition,
            )
        )
        case_id = f"N10_{row['selection_role']}"
        for frame in (sigma, trajectory_curves, decisions):
            frame.insert(0, "selection_role", str(row["selection_role"]))
            frame.insert(0, "case_id", case_id)
        sigma_frames.append(sigma)
        trajectory_frames.append(trajectory_curves)
        decision_frames.append(decisions)

        decision_tables = [
            group.drop(
                columns=["case_id", "selection_role", "trajectory", "seed"],
                errors="ignore",
            )
            for _, group in decisions.groupby("trajectory", sort=True)
        ]
        exact = calculate_exact_sla_sigma_step_curve(
            decision_tables,
            policy.sla_definition,
            policy.horizon_min,
            policy.horizon_max,
        )
        exact.insert(0, "selection_role", str(row["selection_role"]))
        exact.insert(0, "case_id", case_id)
        exact_frames.append(exact)
        axis.step(
            exact["horizon"],
            exact["sigma"],
            where="post",
            linewidth=1.7,
            label=labels.get(str(row["selection_role"]), str(row["selection_role"])),
        )

    pd.concat(decision_frames, ignore_index=True).to_csv(
        output_directory / "selected_candidate_request_decisions.csv",
        index=False,
    )
    pd.concat(trajectory_frames, ignore_index=True).to_csv(
        output_directory / "selected_candidate_trajectory_compliance_curves.csv",
        index=False,
    )
    pd.concat(sigma_frames, ignore_index=True).to_csv(
        output_directory / "selected_candidate_sigma_curves.csv", index=False
    )
    pd.concat(exact_frames, ignore_index=True).to_csv(
        output_directory / "selected_candidate_exact_sigma_steps.csv",
        index=False,
    )

    axis.set_xlim(policy.horizon_min, policy.horizon_max)
    axis.set_ylim(0.0, 1.02)
    axis.set_xlabel("Horizon H since t=0")
    axis.set_ylabel(
        f"Empirical SLA compliance probability σ(H; ρ={policy.sla_definition.rho:.2f})"
    )
    axis.set_title("N=10 proposed white-box SLA-compliance curves")
    axis.grid(True, alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(
        output_directory / "n10_selected_sla_sigma_curves.png", dpi=180
    )
    plt.close(figure)


def execute_whitebox_candidate_selection(
    results_directory: Path,
    policy_configuration_path: Path,
) -> pd.DataFrame:
    """Apply SLA-area selection and write a three-whitebox proposal.

    Side effects:
        Writes candidate ranking, proposal manifest, detailed selected-case
        diagnostics and an N=10 SLA sigma plot.

    Called by:
        - ``main`` in this module.
    """
    configuration = json.loads(
        policy_configuration_path.read_text(encoding="utf-8")
    )
    policy = load_sla_compliance_area_selection_policy(configuration)
    metrics_path = (
        results_directory
        / "whitebox_selection"
        / "sla_candidate_metrics.csv"
    )
    if not metrics_path.exists():
        raise FileNotFoundError(
            f"missing {metrics_path}; run "
            "`python sla_compliance_candidate_metrics.py` first"
        )
    metrics = pd.read_csv(metrics_path)
    candidates = build_whitebox_candidate_table(metrics, policy)

    output_directory = results_directory / "whitebox_selection"
    output_directory.mkdir(parents=True, exist_ok=True)
    candidates.sort_values(
        [
            "inside_sla_compliance_area_band",
            "physical_setting_id",
            "normalized_sla_compliance_area",
            "region_id",
        ],
        ascending=[False, True, True, True],
    ).to_csv(
        output_directory / "whitebox_candidate_ranking.csv", index=False
    )

    prefer_matched = bool(
        configuration.get("confirmation", {}).get(
            "prefer_matched_physical_regime", True
        )
    )
    selected = select_complementary_whitebox_proposal(
        candidates,
        policy,
        prefer_matched_physical_regime=prefer_matched,
    )
    manifest = proposal_dataframe_to_manifest(
        selected,
        results_directory,
        policy,
        policy_configuration_path,
    )
    proposal_path = output_directory / "selected_whiteboxes_proposal.json"
    proposal_path.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    all_ledgers = pd.read_csv(
        results_directory / "all_top_level_request_ledgers.csv"
    )
    write_selected_sla_candidate_diagnostics(
        selected,
        all_ledgers,
        configuration,
        policy,
        output_directory,
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
        "normalized_sla_compliance_area",
        "sigma_120_reporting",
        "sigma_240_reporting",
        "latency_failure_count",
        "cost_failure_count",
        "decided_request_count",
        "n_sigma_transition_times",
        "longest_sigma_plateau_fraction_of_domain",
    ]
    print("PHASE1_WHITEBOX_SLA_SELECTION_PROPOSAL_PASS")
    print(
        f"rho={policy.sla_definition.rho:.6g} "
        f"area_gate=[{policy.area_min:.6g},{policy.area_max:.6g}] "
        f"horizon=[{policy.horizon_min:.6g},{policy.horizon_max:.6g}] "
        "accounting=cumulative_[0,H]_from_t0 midpoint_optimization=false"
    )
    print(selected[display_columns].to_string(index=False))
    print(f"proposal_manifest={proposal_path}")
    print(
        "plot="
        + str(output_directory / "n10_selected_sla_sigma_curves.png")
    )
    return selected


def main() -> None:
    """Command-line entry point for SLA-based N=10 white-box selection.

    Called by:
        - Python ``__main__`` entry point of this module.
    """
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=module_directory
        / "results"
        / "scientific_discovery_v1_full_domain_ar",
    )
    parser.add_argument(
        "--policy-config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    args = parser.parse_args()
    execute_whitebox_candidate_selection(
        args.results.resolve(), args.policy_config.resolve()
    )


if __name__ == "__main__":
    main()
