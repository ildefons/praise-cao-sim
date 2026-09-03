"""Freeze the top-five matched Phase-1 N=10 SLA batteries before N=100 screening.

The shortlist is derived only from the sealed N=10 SLA-native candidate metrics
and the already-frozen role ranking. N=100 results are not read here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from selection_policy import load_sla_compliance_area_selection_policy
from whitebox_candidate_selection import (
    SELECTION_ROLES,
    _select_distinct_rows_in_one_setting,
    build_whitebox_candidate_table,
    rank_candidates_for_role,
)


def build_ranked_matched_shortlist(
    candidates: pd.DataFrame,
    policy,
    shortlist_size: int,
) -> list[dict[str, object]]:
    """Return the pre-ranked top matched triplets using N=10 information only."""
    ranked_by_role = {
        role: rank_candidates_for_role(candidates, role, policy)
        for role in SELECTION_ROLES
    }
    common_settings = set(
        ranked_by_role[SELECTION_ROLES[0]]["physical_setting_id"].astype(str)
    )
    for role in SELECTION_ROLES[1:]:
        common_settings &= set(
            ranked_by_role[role]["physical_setting_id"].astype(str)
        )

    batteries: list[dict[str, object]] = []
    for setting_id in sorted(common_settings):
        rows = _select_distinct_rows_in_one_setting(
            ranked_by_role, setting_id
        )
        if rows is None:
            continue
        score = int(sum(int(row["role_rank"]) for row in rows))
        batteries.append(
            {
                "physical_setting_id": str(setting_id),
                "triplet_score": score,
                "rows": rows,
            }
        )

    batteries.sort(
        key=lambda item: (
            int(item["triplet_score"]),
            str(item["physical_setting_id"]),
        )
    )
    if len(batteries) < shortlist_size:
        raise ValueError(
            f"requested shortlist_size={shortlist_size}, found only "
            f"{len(batteries)} matched batteries"
        )

    output: list[dict[str, object]] = []
    for shortlist_rank, item in enumerate(
        batteries[:shortlist_size], start=1
    ):
        whiteboxes: list[dict[str, object]] = []
        for role, row in zip(SELECTION_ROLES, item["rows"]):
            whiteboxes.append(
                {
                    "case_id": f"S{shortlist_rank}_{role}",
                    "selection_role": role,
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
                    "n10_role_rank": int(row["role_rank"]),
                    "n10_normalized_sla_compliance_area": float(
                        row["normalized_sla_compliance_area"]
                    ),
                    "n10_sigma_120": float(row["sigma_120_reporting"]),
                    "n10_sigma_240": float(row["sigma_240_reporting"]),
                    "n10_latency_failure_count": int(
                        row["latency_failure_count"]
                    ),
                    "n10_cost_failure_count": int(
                        row["cost_failure_count"]
                    ),
                }
            )
        output.append(
            {
                "shortlist_rank": shortlist_rank,
                "triplet_score": int(item["triplet_score"]),
                "physical_setting_id": str(item["physical_setting_id"]),
                "whiteboxes": whiteboxes,
            }
        )
    return output


def execute_freeze(
    results_directory: Path,
    discovery_config_path: Path,
    shortlist_config_path: Path,
    output_path: Path,
) -> dict[str, object]:
    discovery = json.loads(
        discovery_config_path.read_text(encoding="utf-8")
    )
    shortlist_config = json.loads(
        shortlist_config_path.read_text(encoding="utf-8")
    )
    if shortlist_config.get("status") != (
        "FROZEN_PHASE1_N100_SHORTLIST_CALIBRATION_V1"
    ):
        raise ValueError("unexpected shortlist calibration configuration status")

    metrics_path = (
        results_directory
        / "whitebox_selection"
        / "sla_candidate_metrics.csv"
    )
    metrics = pd.read_csv(metrics_path)
    policy = load_sla_compliance_area_selection_policy(discovery)
    candidates = build_whitebox_candidate_table(metrics, policy)
    shortlist = build_ranked_matched_shortlist(
        candidates,
        policy,
        int(shortlist_config["shortlist_size"]),
    )

    manifest = {
        "status": "FROZEN_N10_MATCHED_SHORTLIST_FOR_N100_CALIBRATION",
        "source_results_directory": str(results_directory.resolve()),
        "discovery_configuration": str(discovery_config_path.resolve()),
        "shortlist_configuration": str(shortlist_config_path.resolve()),
        "search_rho": float(policy.sla_definition.rho),
        "accounting_origin": float(
            policy.sla_definition.accounting_origin
        ),
        "accounting_window": "cumulative_[0,H]_from_t0",
        "area_gate": {
            "minimum": float(policy.area_min),
            "maximum": float(policy.area_max),
            "optimize_to_midpoint": False,
        },
        "selection_semantics": (
            "Five matched latency/cost/mixed batteries frozen solely from the "
            "pre-existing N=10 ranking. N=100 calibration may only apply the "
            "predeclared stability gates and may not reorder passing batteries."
        ),
        "batteries": shortlist,
    }
    output_path.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    rows = []
    for battery in shortlist:
        for whitebox in battery["whiteboxes"]:
            rows.append(
                {
                    "shortlist_rank": battery["shortlist_rank"],
                    "triplet_score": battery["triplet_score"],
                    "physical_setting_id": battery["physical_setting_id"],
                    "role": whitebox["selection_role"],
                    "region_id": whitebox["source_region_id"],
                    "role_rank": whitebox["n10_role_rank"],
                    "n10_area": whitebox[
                        "n10_normalized_sla_compliance_area"
                    ],
                }
            )
    table = pd.DataFrame(rows)
    print("PHASE1_N10_MATCHED_SHORTLIST_FREEZE_PASS")
    print(table.to_string(index=False))
    print(f"shortlist_manifest={output_path.resolve()}")
    return manifest


def main() -> None:
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
        "--discovery-config",
        type=Path,
        default=module_directory / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--shortlist-config",
        type=Path,
        default=module_directory
        / "config_phase1_n100_shortlist_calibration_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=module_directory / "shortlist_n10_matched_v1.json",
    )
    args = parser.parse_args()
    execute_freeze(
        args.results.resolve(),
        args.discovery_config.resolve(),
        args.shortlist_config.resolve(),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
