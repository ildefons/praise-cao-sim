#!/usr/bin/env python3
"""Read-only independent B0001 four-arm post-run audit.

This script does not import the simulator, write files, execute trajectories,
or access any white-box/reference data. It checks a locally completed science
directory against its frozen plan and SHA-256 manifests. It is not a formal
authorization to open the reference: that remains a separate gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


METHODS = {
    "ORIGINAL_TOP14_B1400", "ORIGINAL_TOP1_B1400",
    "FIXED_CV_TOP14", "FIXED_CV_TOP1",
}
WORLDS = {"P1", "P3", "P4"}
GRAPHS = {"G_PAR", "G_PARSEQ", "G_SEQ", "G_SEQPAR"}
PLAN_STATUS = "B0001_FOUR_ARM_48_CELL_SCIENCE_PLAN_FROZEN_EXECUTION_BLOCKED"
METHOD_STATUS = "B0001_FOUR_ARM_METHOD_GRAPH_CELL_FROZEN"
GLOBAL_STATUS = "B0001_FOUR_ARM_48_METHOD_CELLS_GRAPH_PREDICTIONS_FROZEN"
KEYS = ["query_id", "provider_world_id", "graph_id", "rho_label", "rho", "regime", "H"]
EPS = 1e-10


def check(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError("B0001 INDEPENDENT POSTRUN AUDIT FAIL: " + message)


def read(path: Path) -> dict:
    check(path.is_file(), "missing " + str(path))
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def sha(path: Path) -> str:
    check(path.is_file(), "missing " + str(path))
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def expected_rows(plan: dict) -> dict:
    check(plan.get("status") == PLAN_STATUS, "plan status")
    check(plan.get("method_cell_count") == 48, "plan cell count")
    check(plan.get("nominal_graph_trajectories") == 67200, "planned trajectory count")
    check(plan.get("whitebox_reference_read") is False, "plan WB firewall")
    rows = plan["method_cells"]
    check(len(rows) == 48, "plan row count")
    result = {}
    n_total = 0
    for row in rows:
        method, cell = row["method"], row["cell"]
        check(method in METHODS, "unexpected method " + str(method))
        check(row["world"] in WORLDS and row["graph"] in GRAPHS, "world/graph")
        check(cell == f'{row["world"]}__{row["graph"]}', "cell identity")
        key = method + "/" + cell
        check(key not in result, "duplicate plan row " + key)
        variants = row["variants"]
        check(len(variants) == (14 if row["kind"] == "top14" else 1), "member count " + key)
        n = sum(int(v["n"]) for v in variants)
        check(n == 1400, "per-cell trajectories " + key)
        check(np.isclose(sum(float(v["alpha"]) for v in variants), 1.0), "weights " + key)
        check(all(int(v["seed_end"]) - int(v["seed_start"]) + 1 == int(v["n"])
                  for v in variants), "seed ranges " + key)
        check([int(v["rank"]) for v in variants] == list(range(1, len(variants) + 1)),
              "member ranks " + key)
        result[key] = row
        n_total += n
    check(n_total == 67200, "total planned trajectories")
    check({r["method"] for r in rows} == METHODS, "not all four algorithms present")
    check({r["cell"] for r in rows} == {w + "__" + g for w in WORLDS for g in GRAPHS},
          "not all 12 conditions present")
    return result


def audit_method(root: Path, row: dict) -> tuple[int, int]:
    key = row["method"] + "/" + row["cell"]
    cell = root / "scientific" / row["method"] / row["cell"]
    manifest = read(cell / "prediction_manifest.json")
    for field, expected in {
        "status": METHOD_STATUS,
        "method": row["method"],
        "cell": row["cell"],
        "graph_trajectories": 1400,
        "member_count": len(row["variants"]),
        "prediction_points": 735,
        "query_sha256": row["query_sha256"],
        "support_sha256": row["support_sha256"],
        "whitebox_reference_read": False,
    }.items():
        check(manifest.get(field) == expected, f"{key}: manifest {field}")

    expected_ledger_names = {f'R{int(v["rank"]):02d}.csv' for v in row["variants"]}
    check(set(manifest["ledger_sha256"]) == expected_ledger_names,
          f"{key}: rank-ledger inventory")
    for v in row["variants"]:
        name = f'R{int(v["rank"]):02d}.csv'
        path = cell / "ledgers" / name
        check(sha(path) == manifest["ledger_sha256"][name], f"{key}/{name}: SHA-256")
        ledger = pd.read_csv(path, usecols=["trajectory_seed", "trajectory", "request_id"])
        observed = sorted(ledger.trajectory_seed.astype(int).unique().tolist())
        expected = list(range(int(v["seed_start"]), int(v["seed_end"]) + 1))
        check(observed == expected, f"{key}/{name}: trajectory seeds")
        check(ledger.trajectory.nunique() == int(v["n"]), f"{key}/{name}: trajectory count")
        check(not ledger[["trajectory", "request_id"]].duplicated().any(),
              f"{key}/{name}: duplicate trajectory/request")

    for field, filename in (("member_curves_sha256", "member_curves.csv"),
                            ("predictions_sha256", "predictions.csv")):
        check(sha(cell / filename) == manifest[field], f"{key}: {filename} SHA-256")

    pred = pd.read_csv(cell / "predictions.csv")
    members = pd.read_csv(cell / "member_curves.csv")
    m = len(row["variants"])
    check(len(pred) == 735 and len(members) == m * 735, f"{key}: curve lengths")
    check(not pred[KEYS].duplicated().any(), f"{key}: duplicate prediction keys")
    check(pred.query_id.nunique() == 15 and pred.H.nunique() == 49,
          f"{key}: 15-query x 49-horizon grid")
    check(pred.sigma_hat.between(0, 1).all() and members.sigma_member.between(0, 1).all(),
          f"{key}: sigma outside [0,1]")
    check(set(pred.method_id.astype(str)) == {row["method"]}, f"{key}: method label")
    check((pred.support_size == m).all() and (pred.graph_budget == 1400).all(),
          f"{key}: prediction metadata")
    check(not members[KEYS + ["joint_rank"]].duplicated().any(),
          f"{key}: duplicate member keys")
    check(members.groupby(KEYS, dropna=False).size().eq(m).all(),
          f"{key}: missing member observations")

    allocations = {int(v["rank"]): v for v in row["variants"]}
    for rank, group in members.groupby("joint_rank"):
        v = allocations.get(int(rank))
        check(v is not None, f"{key}: unexpected rank {rank}")
        check(np.allclose(group.alpha.to_numpy(float), float(v["alpha"]), atol=EPS),
              f"{key}: rank weights")
        check((group.graph_n.astype(int) == int(v["n"])).all(), f"{key}: rank allocation")

    # Independent aggregation verification, not merely trusting the file hashes.
    working = members.assign(weighted=members.alpha * members.sigma_member,
                             variance_term=members.alpha**2 / members.graph_n)
    reconstruction = working.groupby(KEYS, dropna=False, as_index=False).agg(
        sigma_rebuilt=("weighted", "sum"),
        variance_bound=("variance_term", "sum"),
        total_n=("graph_n", "sum"),
        total_alpha=("alpha", "sum"))
    merged = pred.merge(reconstruction, on=KEYS, validate="one_to_one")
    check(len(merged) == 735, f"{key}: member/prediction grid mismatch")
    check(np.allclose(merged.sigma_hat, merged.sigma_rebuilt, atol=EPS),
          f"{key}: independent aggregation discrepancy")
    check(np.allclose(merged.mc_var_worstcase_bound,
                      0.25 * merged.variance_bound, atol=EPS),
          f"{key}: Monte Carlo variance bound discrepancy")
    check((merged.total_n == 1400).all() and
          np.allclose(merged.total_alpha, 1.0, atol=EPS),
          f"{key}: per-point allocation or weight sum")
    check(np.allclose(merged.retained_mass,
                      sum(float(v["joint_weight"]) for v in row["variants"]), atol=EPS),
          f"{key}: retained mass")
    return 1400, 735


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--science-out", type=Path, help="Frozen B0001 four-arm output root")
    p.add_argument("--plan", type=Path, help="Frozen execution plan JSON")
    p.add_argument("--plan-only", action="store_true", help="Check plan cardinality only")
    a = p.parse_args()
    check(a.science_out is not None or a.plan is not None, "provide --science-out or --plan")
    root = a.science_out.expanduser().resolve() if a.science_out else None
    plan_path = (a.plan.expanduser().resolve() if a.plan else
                 root / "b0001_four_arm_science_execution_plan.json")
    plan = read(plan_path)
    rows = expected_rows(plan)
    print(f"B0001_PLAN_STRUCTURE_PASS methods=4 conditions=12 cells=48 trajectories=67200")
    print("B0001_PLAN_SHA256", sha(plan_path))
    if a.plan_only:
        print("PLAN_ONLY / NO_SCIENTIFIC_OUTPUTS_TESTED / NO_WHITEBOX_READ")
        return
    check(root is not None and root.is_dir(), "missing --science-out directory")
    global_path = root / "scientific" / "b0001_four_arm_global_prediction_freeze.json"
    global_doc = read(global_path)
    check(global_doc.get("status") == GLOBAL_STATUS, "global completion freeze")
    check(global_doc.get("n_method_cells") == 48 and
          global_doc.get("graph_trajectories") == 67200, "global counts")
    check(global_doc.get("whitebox_reference_read") is False and
          global_doc.get("seven_arm_independent_confirmation_complete") is False,
          "global blind/reference status")
    check(global_doc.get("execution_plan_sha256") == sha(plan_path),
          "global plan hash drift")
    attest = global_doc.get("method_cell_manifest_sha256", {})
    check(set(attest) == set(rows), "global 48-manifest inventory")
    trajectories, points = 0, 0
    for key, row in rows.items():
        manifest_path = root / "scientific" / row["method"] / row["cell"] / "prediction_manifest.json"
        check(sha(manifest_path) == attest[key], key + ": global manifest SHA")
        n, p_count = audit_method(root, row)
        trajectories += n
        points += p_count
        print("B0001_INDEPENDENT_METHOD_CELL_AUDIT_PASS", key, flush=True)
    check(trajectories == 67200 and points == 48 * 735, "audited totals")
    print("B0001_48_CELL_INDEPENDENT_POSTRUN_AUDIT_PASS")
    print("METHOD_CELLS=48 TRAJECTORIES=67200 PREDICTION_POINTS=35280")
    print("NO_WRITES / NO_SIMULATIONS / NO_WHITEBOX_READ / REFERENCE_NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
