"""Freeze exact matched Phase-1 whiteboxes from retained N=10 discovery rows.

This utility prevents rounded terminal output from becoming the scientific
specification. It reads the exact source rows selected in
``matched_whitebox_sources.json`` from the augmented N=10 discovery table and
writes ``selected_whiteboxes.json`` with status ``FROZEN_FOR_CONFIRMATION``.
No simulator is run and no admissibility threshold is recalibrated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def freeze_exact_matched_whiteboxes(
    results_directory: Path,
    source_specification_path: Path,
    output_manifest_path: Path,
) -> dict:
    """Write the exact three-case matched-whitebox confirmation manifest.

    Args:
        results_directory: Augmented N=10 discovery result directory.
        source_specification_path: JSON naming the three exact source region IDs.
        output_manifest_path: Canonical ``selected_whiteboxes.json`` destination.

    Returns:
        Frozen manifest dictionary.

    Side effects:
        Replaces ``output_manifest_path`` with the exact source-row values.

    Called by:
        - ``main`` in this module.
    """
    specification = json.loads(source_specification_path.read_text(encoding="utf-8"))
    representatives = pd.read_csv(results_directory / "representative_regions_by_sigma.csv")
    physical = specification["physical_regime"]

    frozen_cases: list[dict[str, object]] = []
    for case in specification["cases"]:
        matches = representatives[
            (representatives["physical_setting_id"].astype(str) == str(physical["physical_setting_id"]))
            & (representatives["region_id"].astype(str) == str(case["source_region_id"]))
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected exactly one source row for {case['source_region_id']}, got {len(matches)}"
            )
        row = matches.iloc[0]
        if abs(float(row["center_instruction_mean"]) - float(physical["center_instruction_mean"])) > 1e-9:
            raise ValueError("source row center_instruction_mean differs from matched physical regime")
        if abs(float(row["dispersion"]) - float(physical["dispersion"])) > 1e-12:
            raise ValueError("source row dispersion differs from matched physical regime")

        frozen_cases.append(
            {
                "case_id": str(case["case_id"]),
                "selection_role": str(case["selection_role"]),
                "physical_setting_id": str(row["physical_setting_id"]),
                "source_region_id": str(row["region_id"]),
                "center_instruction_mean": float(row["center_instruction_mean"]),
                "dispersion": float(row["dispersion"]),
                "l_max": float(row["l_max"]),
                "c_max": float(row["c_max"]),
                "q_min": float(row["q_min"]),
                "discovery_sigma_anchor": float(row["sigma_anchor"]),
                "discovery_latency_first_count": int(row["latency_first_count"]),
                "discovery_cost_first_count": int(row["cost_first_count"]),
                "source_results_directory": str(results_directory),
            }
        )

    roles = {case["selection_role"] for case in frozen_cases}
    if roles != {"latency", "mixed", "cost"}:
        raise ValueError(f"matched battery must contain latency, mixed, and cost roles; got {sorted(roles)}")
    physical_keys = {
        (
            case["physical_setting_id"],
            case["center_instruction_mean"],
            case["dispersion"],
        )
        for case in frozen_cases
    }
    if len(physical_keys) != 1:
        raise ValueError("all matched whiteboxes must share one physical regime")

    manifest = {
        "status": "FROZEN_FOR_CONFIRMATION",
        "selection_semantics": (
            "Exact N=10 discovery source rows frozen before N=100 confirmation. "
            "All three A regions share one physical regime. N=100 must use fresh "
            "seeds and must not recalibrate A."
        ),
        "paired_matched_physical_regime": True,
        "whiteboxes": frozen_cases,
    }
    output_manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("PHASE1_MATCHED_WHITEBOX_FREEZE_PASS")
    for frozen in frozen_cases:
        print(
            frozen["case_id"],
            frozen["selection_role"],
            f"L<={frozen['l_max']:.12g}",
            f"C<={frozen['c_max']:.12g}",
            f"Q>={frozen['q_min']:.12g}",
        )
    print(f"manifest={output_manifest_path}")
    return manifest


def main() -> None:
    """Command-line entry point for exact source-row freezing."""
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=module_directory / "results" / "scientific_discovery_v1_full_domain_ar",
    )
    parser.add_argument(
        "--source-spec",
        type=Path,
        default=module_directory / "matched_whitebox_sources.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=module_directory / "selected_whiteboxes.json",
    )
    args = parser.parse_args()
    freeze_exact_matched_whiteboxes(
        args.results.resolve(),
        args.source_spec.resolve(),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
