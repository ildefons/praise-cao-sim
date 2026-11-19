"""Read-only B0001 diagnostics; never reruns or changes a selection policy.

Two deliberately limited counterfactuals are scored against recommendations
already made by the exact historical B1 replay:
  (1) the existing 10,000 joint white-box reference-trajectory bootstrap means;
  (2) leave one of the twelve physical evaluation conditions out of the target.

Both hold original episode recommendations fixed. Neither is a replacement for
the primary original-script policy replay, nor a full reference-aware policy
bootstrap: the latter would also have to update observations and action paths.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


METHODS = (
    "M1", "M2", "M3_FULL343", "ORIGINAL_TOP14_B1400",
    "ORIGINAL_TOP1_B1400", "FIXED_CV_TOP14", "FIXED_CV_TOP1",
)
EXPECTED_POLICIES = (
    "random", "balanced", "informed", "budgeted_top2", "kg_one_step",
    "kg_two_stage_adaptive", "kg_two_stage_uniform",
    "top2_two_stage_adaptive", "top2_two_stage_uniform",
)
CONTRASTS = (
    ("Top2_minus_Balanced", "budgeted_top2", "balanced"),
    ("KG_minus_Balanced", "kg_one_step", "balanced"),
    ("KG_minus_Top2", "kg_one_step", "budgeted_top2"),
    ("Informed_minus_Balanced", "informed", "balanced"),
    ("KG_uniform_minus_adaptive", "kg_two_stage_uniform", "kg_two_stage_adaptive"),
    ("Top2_uniform_minus_adaptive", "top2_two_stage_uniform", "top2_two_stage_adaptive"),
)
EXPECTED_MATRIX_SHA256 = "0354739d64038da538485b5364b37ad8a69181ca5957dbff92aaec349be2523b"
EXPECTED_BOOTSTRAP_SHA256 = "c73404ffb6eda83f48d57812caccb02ae68ecd3a61631a16e5eb6463ddce1418"
EXPECTED_TERMINAL_SHA256 = {
    "baseline": "29d284636dce74cfdec96f61f6056f7d919da76b3746bd3753170973082d357a",
    "kg": "e0228e0ac3cb51029d97f3d13c45875381ae8924c044f9b30843629f67e04bb4",
    "controlled": "f45ae653612bc9d69080e3659d3455385514c951c6a47492724346a0698e9af9",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def checked(path: Path, expected: str) -> None:
    actual = sha(path)
    if actual != expected:
        raise ValueError(f"Frozen SHA mismatch for {path}: {actual} != {expected}")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Empty output: {path}")
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix", type=Path, required=True)
    p.add_argument("--reference-bootstrap", type=Path, required=True)
    p.add_argument("--baseline-terminal", type=Path, required=True)
    p.add_argument("--kg-terminal", type=Path, required=True)
    p.add_argument("--controlled-terminal", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()

    sources = {
        "matrix": a.matrix,
        "reference_bootstrap": a.reference_bootstrap,
        "baseline": a.baseline_terminal,
        "kg": a.kg_terminal,
        "controlled": a.controlled_terminal,
    }
    checked(a.matrix, EXPECTED_MATRIX_SHA256)
    checked(a.reference_bootstrap, EXPECTED_BOOTSTRAP_SHA256)
    for name in EXPECTED_TERMINAL_SHA256:
        checked(sources[name], EXPECTED_TERMINAL_SHA256[name])

    matrix = load_rows(a.matrix)
    cells = sorted({(x["world"], x["graph"]) for x in matrix})
    lookup = {(x["method"], x["world"], x["graph"]): float(x["mae"]) for x in matrix}
    if len(cells) != 12 or len(lookup) != 84 or len(matrix) != 84:
        raise ValueError("Expected unique 7-method by 12-condition B0001 matrix")
    if set(x[0] for x in lookup) != set(METHODS):
        raise ValueError("Unexpected B0001 method IDs")
    means = np.array([
        np.mean([lookup[(m, w, g)] for w, g in cells])
        for m in METHODS
    ])

    boot_rows = load_rows(a.reference_bootstrap)
    if len(boot_rows) != 10000:
        raise ValueError("Expected original 10,000 joint reference bootstrap draws")
    ref_bootstrap = np.array([
        [float(row[f"MAE_{method}"]) for method in METHODS]
        for row in boot_rows
    ])

    episodes = defaultdict(list)
    for source in (a.baseline_terminal, a.kg_terminal, a.controlled_terminal):
        for row in load_rows(source):
            episodes[row["policy"]].append(row)
    if set(episodes) != set(EXPECTED_POLICIES):
        raise ValueError("Policy IDs do not match the nine original replay policies")
    if any(len(rows) != 1200 for rows in episodes.values()):
        raise ValueError("Expected 1,200 terminal episodes per policy")
    winner = float(means.min())
    weights = {}
    for policy, rows in episodes.items():
        counts = Counter((int(x["budget"]) for x in rows))
        if counts != Counter({10: 240, 15: 240, 20: 240, 30: 240, 40: 240}):
            raise ValueError(f"Unexpected budgets/episode count for {policy}")
        for row in rows:
            if row["recommended"] not in METHODS:
                raise ValueError(f"Invalid method in {policy} terminal recommendation")
            recomputed = float(means[METHODS.index(row["recommended"])] - winner)
            if not np.isclose(float(row["simple_regret"]), recomputed, atol=1e-12, rtol=0):
                raise ValueError(f"Terminal regret mismatch for {policy}")
        counts = Counter(x["recommended"] for x in rows)
        weights[policy] = np.array([counts[m] / 1200 for m in METHODS])

    reference_contrasts = []
    for label, first, second in CONTRASTS:
        difference = weights[first] - weights[second]
        bootstrap_scores = ref_bootstrap @ difference
        reference_contrasts.append({
            "contrast": label,
            "observed_frozen_recommendations_difference": float(means @ difference),
            "reference_bootstrap_p025": float(np.quantile(bootstrap_scores, 0.025)),
            "reference_bootstrap_p975": float(np.quantile(bootstrap_scores, 0.975)),
            "fraction_negative": float(np.mean(bootstrap_scores < 0)),
            "fraction_positive": float(np.mean(bootstrap_scores > 0)),
        })

    leave_one_out = []
    for world, graph in cells:
        subset = [key for key in cells if key != (world, graph)]
        shifted_means = np.array([
            np.mean([lookup[(m, w, g)] for w, g in subset])
            for m in METHODS
        ])
        row = {
            "excluded_cell": f"{world}__{graph}",
            "reference_best_under_11_cell_target": METHODS[int(np.argmin(shifted_means))],
            "M3_minus_M1_mean_MAE_under_11_cell_target": float(
                shifted_means[METHODS.index("M3_FULL343")] - shifted_means[METHODS.index("M1")]
            ),
        }
        for label, first, second in CONTRASTS:
            row[label] = float(shifted_means @ (weights[first] - weights[second]))
        leave_one_out.append(row)

    if a.out.exists():
        raise FileExistsError(f"Refuse to overwrite existing diagnostic output: {a.out}")
    a.out.mkdir(parents=True)
    contrast_csv = a.out / "fixed_decision_reference_bootstrap_contrasts.csv"
    influence_csv = a.out / "leave_one_cell_out_fixed_decision_contrasts.csv"
    write_csv(contrast_csv, reference_contrasts)
    write_csv(influence_csv, leave_one_out)
    manifest = {
        "status": "B0001_FIXED_DECISION_REFERENCE_AND_CELL_INFLUENCE_DIAGNOSTIC_V1_PASS",
        "not_primary_policy_replay": True,
        "all_nine_original_policy_recommendations_held_fixed": True,
        "no_policy_reexecution": True,
        "no_simulations": True,
        "no_prediction_or_reference_changes": True,
        "not_full_reference_aware_policy_bootstrap": True,
        "original_policy_terminal_episodes_verified": 10800,
        "bootstrap_existing_trajectory_replicates": len(boot_rows),
        "original_B0001_12_cell_winner": METHODS[int(np.argmin(means))],
        "original_B0001_M3_minus_M1_mean_MAE": float(means[2] - means[0]),
        "P1_G_PAR_M3_minus_M1_cell_MAE": float(
            lookup[("M3_FULL343", "P1", "G_PAR")] - lookup[("M1", "P1", "G_PAR")]
        ),
        "P1_G_PAR_contribution_to_12_cell_M3_minus_M1": float(
            (lookup[("M3_FULL343", "P1", "G_PAR")] - lookup[("M1", "P1", "G_PAR")]) / 12
        ),
        "sources_sha256": {key: sha(path) for key, path in sources.items()},
        "outputs_sha256": {
            contrast_csv.name: sha(contrast_csv),
            influence_csv.name: sha(influence_csv),
        },
        "interpretation": (
            "The reference bootstrap varies full-domain MAE scores only, and the "
            "leave-one-cell-out check varies the evaluation target only. Both rescore "
            "the same frozen final recommendations. Neither recomputes acquisitions "
            "or estimates independent-world generalization."
        ),
    }
    manifest_path = a.out / "diagnostic_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(manifest["status"])
    print("FROZEN_TERMINAL_RECOMMENDATIONS_VERIFIED 10800/10800")
    print("EXISTING_REFERENCE_BOOTSTRAP_DRAWS 10000")
    print("P1_G_PAR_CELL_M3_MINUS_M1", manifest["P1_G_PAR_M3_minus_M1_cell_MAE"])
    for row in reference_contrasts:
        print(
            row["contrast"], "observed=", row["observed_frozen_recommendations_difference"],
            "WB_ref95=", (row["reference_bootstrap_p025"], row["reference_bootstrap_p975"])
        )
    print("OUTPUT", a.out)


if __name__ == "__main__":
    main()
