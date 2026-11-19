#!/usr/bin/env python3
"""Read-only scientific re-aggregation of the B0001 13-budget terminal episodes.

The original five budgets and eight added budgets are read from their separate
immutable ZIP archives. No policy, predictor or physical reference is executed.
The original family-specific bootstrap implementations are reused unchanged,
apart from replacing the budget-list constant and its aggregate row label.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

import b1_budget_comparison_v1 as baseline
import b1_condition_selection_controlled_v1 as controlled
import extend_b1_original_nine_policy_budgets_v1 as extension


BUDGETS = (10, 15, 20, 25, 30, 35, 40, 45, 55, 65, 70, 75, 80)
OLD_BUDGETS = (10, 15, 20, 30, 40)
NEW_BUDGETS = (25, 35, 45, 55, 65, 70, 75, 80)
TERMINALS = {
    "baseline": "terminal_episodes.csv",
    "kg": "kg_terminal_episodes.csv",
    "controlled": "controlled_terminal_episodes.csv",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_terminal(archive: Path, family: str, budget_set: tuple[int, ...]) -> list[dict]:
    """Select the one family terminal table without extracting the archive."""
    with zipfile.ZipFile(archive) as zf:
        matches = [name for name in zf.namelist() if name.endswith("/" + TERMINALS[family])]
        if len(matches) != 1:
            raise ValueError(f"Expected one {family} terminal in {archive}, found {matches}")
        with zf.open(matches[0]) as source:
            records = list(csv.DictReader(io.TextIOWrapper(source, encoding="utf-8", newline="")))
    for record in records:
        for field in ("budget", "start_index", "replicate", "correct"):
            record[field] = int(record[field])
        record["simple_regret"] = float(record["simple_regret"])
    expected_policies = 1 if family == "kg" else 4
    if len(records) != len(budget_set) * 12 * 20 * expected_policies:
        raise ValueError(f"Invalid {family} episode count in {archive}")
    if {r["budget"] for r in records} != set(budget_set):
        raise ValueError(f"Invalid {family} budget set in {archive}")
    policies = {r["policy"] for r in records}
    allowed = {"kg_one_step"} if family == "kg" else (
        set(baseline.POLICIES) if family == "baseline" else set(controlled.POLICIES)
    )
    if policies != allowed:
        raise ValueError(f"Invalid {family} policies in {archive}: {policies}")
    keys = {(r["budget"], r["start_index"], r["replicate"], r["policy"]) for r in records}
    if len(keys) != len(records):
        raise ValueError(f"Duplicate {family} terminal keys in {archive}")
    return records


def derive(old: Path, new: Path) -> tuple[list[dict], dict]:
    all_rows = {}
    for family in TERMINALS:
        old_rows = read_terminal(old, family, OLD_BUDGETS)
        new_rows = read_terminal(new, family, NEW_BUDGETS)
        all_rows[family] = old_rows + new_rows

    _, b_contrasts = baseline.summarize(
        all_rows["baseline"], BUDGETS, extension.REPEATS,
        extension.BOOTSTRAPS, extension.SEED,
    )
    _, kg_contrasts = extension.kg_statistics(
        all_rows["kg"], all_rows["baseline"], BUDGETS,
    )
    old_controlled_budgets = controlled.BUDGETS
    try:
        controlled.BUDGETS = BUDGETS
        _, c_contrasts = controlled.statistics(all_rows["controlled"])
    finally:
        controlled.BUDGETS = old_controlled_budgets

    output = []
    for family, rows in (("baseline", b_contrasts), ("kg", kg_contrasts), ("controlled", c_contrasts)):
        for row in rows:
            budget = row["budget"]
            if isinstance(budget, str) and budget.startswith("MEAN_OVER_"):
                budget = "MEAN_OVER_13_BUDGETS"
            output.append(dict(
                family=family, budget=budget,
                contrast=(row["family"] + " " if family == "controlled" else "") + row["contrast"],
                mean_regret_diff=f"{row['mean_regret_diff']:.17g}",
                low=f"{row['low']:.17g}", high=f"{row['high']:.17g}",
                bootstrap_draws=extension.BOOTSTRAPS,
                episodes_per_policy_per_budget=12 * extension.REPEATS,
            ))

    aggregates = [r for r in output if r["budget"] == "MEAN_OVER_13_BUDGETS"]
    if len(aggregates) != 9 or len(output) != 9 * (len(BUDGETS) + 1):
        raise AssertionError("Expected nine aggregate and 117 budget-specific contrasts")
    manifest = {
        "status": "B0001_THIRTEEN_BUDGET_PAIRED_CONTRAST_REAGGREGATION_PASS",
        "scope": "Episode-bootstrap contrasts conditional on frozen MAEs; no reference resampling",
        "budgets": BUDGETS,
        "old_budgets_reused": OLD_BUDGETS,
        "new_budgets_added": NEW_BUDGETS,
        "episodes_by_policy_and_budget": 240,
        "episodes_total": sum(len(records) for records in all_rows.values()),
        "bootstrap_draws": extension.BOOTSTRAPS,
        "base_seed": extension.SEED,
        "old_five_budget_archive_sha256": sha256(old),
        "new_eight_budget_archive_sha256": sha256(new),
        "recomputed_with_original_family_bootstraps": [
            "b1_budget_comparison_v1.summarize",
            "extend_b1_original_nine_policy_budgets_v1.kg_statistics",
            "b1_condition_selection_controlled_v1.statistics",
        ],
        "aggregate_contrasts": aggregates,
    }
    return output, manifest


def main() -> None:
    repo = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, default=repo / "results/b0001_original_policies_v1/b0001_original_policy_replay_v1_complete.zip")
    parser.add_argument("--new", type=Path, default=repo / "results/b1_nine_policy_13_budget_extension_v1/b0001_eight_added_budgets_full_replay.zip")
    parser.add_argument("--out", type=Path, default=repo / "results/b1_nine_policy_13_budget_extension_v1")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true", help="Write new result files only; never overwrite")
    mode.add_argument("--verify", action="store_true", help="Compare against pre-existing archive without writing")
    args = parser.parse_args()
    rows, manifest = derive(args.old.expanduser().resolve(), args.new.expanduser().resolve())
    output = args.out.expanduser().resolve()
    csv_path = output / "tables/b0001_13_budget_paired_contrasts.csv"
    json_path = output / "b0001_13_budget_contrast_manifest.json"

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    csv_bytes = buffer.getvalue().encode("utf-8")
    manifest["contrast_csv_sha256"] = hashlib.sha256(csv_bytes).hexdigest()
    json_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")

    if args.run:
        if csv_path.exists() or json_path.exists():
            raise FileExistsError("Refusing to overwrite existing thirteen-budget contrast evidence")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_bytes(csv_bytes)
        json_path.write_bytes(json_bytes)
        print("B0001_THIRTEEN_BUDGET_PAIRED_CONTRASTS_PASS")
    else:
        if csv_path.read_bytes() != csv_bytes or json_path.read_bytes() != json_bytes:
            raise AssertionError("Archived paired contrasts differ from read-only recomputation")
        print("B0001_THIRTEEN_BUDGET_PAIRED_CONTRASTS_VERIFY_PASS")
    for r in manifest["aggregate_contrasts"]:
        print(r["contrast"], r["mean_regret_diff"], f"[{r['low']}, {r['high']}]")


if __name__ == "__main__":
    main()
