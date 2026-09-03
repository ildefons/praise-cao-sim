"""Run the frozen top-five N=10 matched batteries through fresh N=100 screening.

This is a calibration/stability stage, not final confirmation. The five-battery
ordering is frozen before these simulations. N=100 results are used only as a
pass/fail stability gate. Among passing batteries, the first battery in the
pre-frozen N=10 ordering is selected; N=100 values never reorder batteries.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from run_n100_matched_confirmation import analyze_and_plot_n100_confirmation

REQUIRED_ROLES = {"latency", "cost", "mixed"}


def _seed_set(container: dict, *keys: str) -> set[int]:
    current = container
    for key in keys:
        if key not in current:
            return set()
        current = current[key]
    return set(map(int, current))


def load_and_validate_protocol(
    discovery_config_path: Path,
    shortlist_config_path: Path,
    shortlist_manifest_path: Path,
) -> tuple[dict, dict, dict]:
    discovery = json.loads(
        discovery_config_path.read_text(encoding="utf-8")
    )
    protocol = json.loads(
        shortlist_config_path.read_text(encoding="utf-8")
    )
    shortlist = json.loads(
        shortlist_manifest_path.read_text(encoding="utf-8")
    )
    if protocol.get("status") != (
        "FROZEN_PHASE1_N100_SHORTLIST_CALIBRATION_V1"
    ):
        raise ValueError("unexpected N100 shortlist protocol status")
    if shortlist.get("status") != (
        "FROZEN_N10_MATCHED_SHORTLIST_FOR_N100_CALIBRATION"
    ):
        raise ValueError("shortlist must be frozen before N100 calibration")

    batteries = shortlist.get("batteries", [])
    expected_size = int(protocol["shortlist_size"])
    if len(batteries) != expected_size:
        raise ValueError(
            f"expected {expected_size} frozen batteries, found {len(batteries)}"
        )
    ranks = [int(item["shortlist_rank"]) for item in batteries]
    if ranks != list(range(1, expected_size + 1)):
        raise ValueError("shortlist ranks must be contiguous and pre-ordered")
    for battery in batteries:
        whiteboxes = battery.get("whiteboxes", [])
        if len(whiteboxes) != 3:
            raise ValueError("every shortlisted battery must contain 3 cases")
        if {str(w["selection_role"]) for w in whiteboxes} != REQUIRED_ROLES:
            raise ValueError("each battery must contain latency/cost/mixed")
        setting_ids = {str(w["physical_setting_id"]) for w in whiteboxes}
        if setting_ids != {str(battery["physical_setting_id"])}:
            raise ValueError("whiteboxes in one battery must share one setting")

    calibration_seeds = set(
        map(int, protocol["calibration"]["seed_bank"])
    )
    final_seeds = set(
        map(int, protocol["final_confirmation"]["seed_bank"])
    )
    if len(calibration_seeds) != 100 or len(final_seeds) != 100:
        raise ValueError("calibration and final banks must each contain 100 seeds")
    old_seed_sets = [
        _seed_set(discovery, "development_smoke", "seed_bank"),
        _seed_set(discovery, "discovery_search", "calibration_seed_bank"),
        _seed_set(discovery, "confirmation_round_1_exploratory", "seed_bank"),
        _seed_set(discovery, "confirmation", "confirmation_seed_bank"),
    ]
    if any(calibration_seeds & old for old in old_seed_sets):
        raise ValueError("N100 calibration seed bank overlaps prior Phase-1 seeds")
    if final_seeds & calibration_seeds:
        raise ValueError("final confirmation seeds overlap N100 calibration seeds")
    if any(final_seeds & old for old in old_seed_sets):
        raise ValueError("final confirmation seed bank overlaps prior Phase-1 seeds")
    return discovery, protocol, shortlist


def execute_one_shortlisted_physical_setting(
    discovery: dict,
    battery: dict,
    seeds: list[int],
    output_directory: Path,
) -> pd.DataFrame:
    """Run one common physical setting for 100 fresh trajectories."""
    from whitebox_atlas import execute_one_whitebox_trajectory

    reference = battery["whiteboxes"][0]
    center = float(reference["center_instruction_mean"])
    dispersion = float(reference["dispersion"])
    setting_id = str(reference["physical_setting_id"])
    ledgers: list[pd.DataFrame] = []
    for trajectory_index, seed in enumerate(seeds):
        trajectory_directory = (
            output_directory
            / "trajectories"
            / setting_id
            / f"trajectory_{trajectory_index:03d}_seed_{seed}"
        )
        ledger = execute_one_whitebox_trajectory(
            discovery,
            center_instruction_mean=center,
            dispersion=dispersion,
            trajectory_seed=int(seed),
            trajectory_output_directory=trajectory_directory,
        )
        ledger.insert(0, "trajectory", trajectory_index)
        ledger.insert(0, "dispersion", dispersion)
        ledger.insert(0, "center_instruction_mean", center)
        ledger.insert(0, "physical_setting_id", setting_id)
        ledgers.append(ledger)
    combined = pd.concat(ledgers, ignore_index=True)
    combined.to_csv(
        output_directory / "all_top_level_request_ledgers.csv",
        index=False,
    )
    return combined


def summarize_battery_passes(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (rank, setting_id), group in summary.groupby(
        ["shortlist_rank", "physical_setting_id"], sort=True
    ):
        roles = set(group["selection_role"].astype(str))
        if roles != REQUIRED_ROLES or len(group) != 3:
            raise ValueError("calibration summary does not contain one row per role")
        rows.append(
            {
                "shortlist_rank": int(rank),
                "physical_setting_id": str(setting_id),
                "triplet_score": int(group["triplet_score"].iloc[0]),
                "battery_pass": bool(
                    group["scientific_confirmation_pass"].astype(bool).all()
                ),
                "latency_pass": bool(
                    group.loc[
                        group["selection_role"] == "latency",
                        "scientific_confirmation_pass",
                    ].iloc[0]
                ),
                "cost_pass": bool(
                    group.loc[
                        group["selection_role"] == "cost",
                        "scientific_confirmation_pass",
                    ].iloc[0]
                ),
                "mixed_pass": bool(
                    group.loc[
                        group["selection_role"] == "mixed",
                        "scientific_confirmation_pass",
                    ].iloc[0]
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("shortlist_rank").reset_index(drop=True)


def select_first_stable_battery(
    shortlist: dict,
    battery_summary: pd.DataFrame,
) -> dict | None:
    """Apply the predeclared winner rule without N=100 re-ranking."""
    passing = battery_summary[
        battery_summary["battery_pass"].astype(bool)
    ].sort_values("shortlist_rank")
    if passing.empty:
        return None
    winner_rank = int(passing.iloc[0]["shortlist_rank"])
    for battery in shortlist["batteries"]:
        if int(battery["shortlist_rank"]) == winner_rank:
            return battery
    raise RuntimeError("passing shortlist rank missing from frozen manifest")


def execute_shortlist_calibration(
    discovery_config_path: Path,
    shortlist_config_path: Path,
    shortlist_manifest_path: Path,
    output_directory: Path,
    selected_output_path: Path,
    clean: bool,
) -> pd.DataFrame:
    discovery, protocol, shortlist = load_and_validate_protocol(
        discovery_config_path,
        shortlist_config_path,
        shortlist_manifest_path,
    )
    if output_directory.exists() and any(output_directory.iterdir()):
        if not clean:
            raise FileExistsError(
                f"{output_directory} already contains results; use --clean only "
                "for an explicit rerun of the same frozen protocol"
            )
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "effective_discovery_config.json").write_text(
        json.dumps(discovery, indent=2), encoding="utf-8"
    )
    (output_directory / "effective_shortlist_protocol.json").write_text(
        json.dumps(protocol, indent=2), encoding="utf-8"
    )
    (output_directory / "frozen_n10_shortlist.json").write_text(
        json.dumps(shortlist, indent=2), encoding="utf-8"
    )

    seeds = list(map(int, protocol["calibration"]["seed_bank"]))
    all_summaries: list[pd.DataFrame] = []
    for battery in shortlist["batteries"]:
        rank = int(battery["shortlist_rank"])
        setting_id = str(battery["physical_setting_id"])
        battery_directory = (
            output_directory / f"battery_{rank:02d}_{setting_id}"
        )
        battery_directory.mkdir(parents=True, exist_ok=True)
        print(
            "PHASE1_N100_SHORTLIST_BATTERY_START",
            f"rank={rank}",
            f"setting={setting_id}",
            "n=100",
        )
        ledgers = execute_one_shortlisted_physical_setting(
            discovery,
            battery,
            seeds,
            battery_directory,
        )
        battery_manifest = {
            "whiteboxes": battery["whiteboxes"],
        }
        summary = analyze_and_plot_n100_confirmation(
            discovery,
            battery_manifest,
            ledgers,
            battery_directory,
        )
        summary.insert(0, "triplet_score", int(battery["triplet_score"]))
        summary.insert(0, "shortlist_rank", rank)
        all_summaries.append(summary)

    full_summary = pd.concat(all_summaries, ignore_index=True)
    full_summary.to_csv(
        output_directory / "n100_shortlist_case_summary.csv",
        index=False,
    )
    battery_summary = summarize_battery_passes(full_summary)
    battery_summary.to_csv(
        output_directory / "n100_shortlist_battery_summary.csv",
        index=False,
    )

    winner = select_first_stable_battery(shortlist, battery_summary)
    if winner is None:
        selected_manifest = {
            "status": "NO_STABLE_BATTERY_AFTER_N100_SHORTLIST_CALIBRATION",
            "selection_rule": protocol["post_calibration_selection"][
                "winner_rule"
            ],
            "calibration_seed_bank": seeds,
            "whiteboxes": [],
        }
    else:
        selected_manifest = {
            "status": (
                "SELECTED_AFTER_N100_STABILITY_CALIBRATION_"
                "REQUIRES_FRESH_FINAL_CONFIRMATION"
            ),
            "selection_rule": protocol["post_calibration_selection"][
                "winner_rule"
            ],
            "selected_shortlist_rank": int(winner["shortlist_rank"]),
            "selected_triplet_score": int(winner["triplet_score"]),
            "physical_setting_id": str(winner["physical_setting_id"]),
            "calibration_seed_bank": seeds,
            "final_confirmation_seed_bank": list(
                map(int, protocol["final_confirmation"]["seed_bank"])
            ),
            "rho": float(shortlist["search_rho"]),
            "accounting_window": "cumulative_[0,H]_from_t0",
            "whiteboxes": winner["whiteboxes"],
        }
    selected_output_path.write_text(
        json.dumps(selected_manifest, indent=2), encoding="utf-8"
    )

    print("PHASE1_N100_SHORTLIST_CALIBRATION_RUN_PASS")
    print(battery_summary.to_string(index=False))
    if winner is None:
        print("selected_shortlist_rank=NONE")
    else:
        print(
            f"selected_shortlist_rank={winner['shortlist_rank']} "
            f"physical_setting_id={winner['physical_setting_id']}"
        )
    print(f"selected_manifest={selected_output_path.resolve()}")
    return full_summary


def main() -> None:
    module_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
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
        "--shortlist",
        type=Path,
        default=module_directory / "shortlist_n10_matched_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=module_directory
        / "results"
        / "n100_shortlist_calibration_v1",
    )
    parser.add_argument(
        "--selected-output",
        type=Path,
        default=module_directory
        / "selected_whiteboxes_after_n100_calibration.json",
    )
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    execute_shortlist_calibration(
        args.discovery_config.resolve(),
        args.shortlist_config.resolve(),
        args.shortlist.resolve(),
        args.output.resolve(),
        args.selected_output.resolve(),
        clean=bool(args.clean),
    )


if __name__ == "__main__":
    main()
