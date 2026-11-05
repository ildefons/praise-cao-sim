#!/usr/bin/env python3
"""PRAISE B1 V0.1: deterministic, SIMULATION-FREE prospective world preview.

Reads the unchanged Phase-5 world template and a separately versioned DRAFT
proposal. Draws physical provider parameters only; it does NOT call Step-0,
I1, reconstruction, graph simulation, WB, or the frozen B1 selection policy.
Never place outputs under the existing PRAISE results directory.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random

REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DRAFT = HERE / "B1_WORLD_GENERATOR_DRAFT_V0_1.json"
CONTRACT = Path("first_science/phase5/config_phase5_recoverability_battery_v2.json")
STEP0 = Path("first_science/phase5/run_phase5_step0_v2.py")
POLICY = Path("first_science/b1/planb_validation/b1_budget_comparison_v1.py")
GRAPHS = ("G_PAR", "G_PARSEQ", "G_SEQ", "G_SEQPAR")
ROLES = ("P1", "P3", "P4")
PASS = "FROZEN_PHASE5_STEP0_PASS_V2"
FAIL = "GATE_FAILED_STEP0"
FAIL_CAL = "GATE_FAILED_STEP0_CALIBRATION"
ROWS = (
    "battery_id", "role", "attempt", "candidate_id", "D_instructions", "delta",
    "ProviderA_instructions", "ProviderB_instructions", "ProviderC_instructions",
    "max_approx_utilization", "step0_status",
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_proposal(proposal: dict, historical: dict) -> None:
    if proposal.get("status") != "DRAFT_ONLY_NOT_FROZEN_NOT_AUTHORIZED_FOR_SIMULATION":
        raise ValueError("This script only supports the non-executable V0.1 draft")
    if proposal.get("execution_authorized") is not False:
        raise ValueError("Execution must be explicitly forbidden in this preview")
    sampling = proposal["sampling"]
    if tuple(sampling["role_order"]) != ROLES:
        raise ValueError("The frozen B1 policy requires P1, P3, P4 roles")
    if not 1 <= sampling["preview_batteries"] <= 100 or not 1 <= sampling["max_attempts_per_role"] <= 30:
        raise ValueError("Preview battery count or attempt cap invalid")
    if type(sampling["preview_seed"]) is not int or sampling["preview_seed"] < 0:
        raise ValueError("Preview seed must be a nonnegative integer")
    worlds = {w["id"]: w for w in historical["provider_worlds"]}
    if set(worlds) != {"P1", "P2", "P3", "P4"}:
        raise ValueError("Historical physical world catalogue changed")
    if tuple(sorted(g["id"] for g in historical["graphs"])) != tuple(sorted(GRAPHS)):
        raise ValueError("Four frozen graph ASTs changed")
    if abs(float(historical["workload"]["period_seconds"]) - 0.2) > 1e-12:
        raise ValueError("Workload period differs from historical W0")
    f = historical["provider_family"]
    if f["n_providers"] != 3 or f["instruction_distribution_family"] != "gamma":
        raise ValueError("Historical provider family changed")
    if f["instruction_cv"] != 0.3 or f["effective_IPT"] != 1_000_000_000:
        raise ValueError("Historical provider service assumptions changed")
    if f["execution_fraction_x"] != 0.5:
        raise ValueError("Historical execution fraction changed")
    rule = proposal["eligibility"]
    if tuple(rule["all_four_graphs_required"]) != GRAPHS:
        raise ValueError("All four graphs must pass Step-0")
    frozen = historical["step0"]
    if (rule["calibration_n_per_cell"], rule["confirmation_n_per_cell"]) != (
        frozen["calibration_n"], frozen["confirmation_n"]
    ):
        raise ValueError("Historical Step-0 N=200+200 changed")
    if rule["minimum_adjacent_mean_sigma_gap"] != frozen["minimum_adjacent_mean_sigma_gap"]:
        raise ValueError("Historical Step-0 minimum gap changed")
    scale = frozen["scale_grid"]
    if [scale["minimum"], scale["maximum"], scale["step"]] != rule["frozen_scale_grid"]:
        raise ValueError("Historical Step-0 scale grid changed")
    historical_regimes = {
        r["id"]: [r["mean_sigma_lower"], r["mean_sigma_upper"]] for r in frozen["regimes"]
    }
    if historical_regimes != rule["regions"]:
        raise ValueError("Historical Step-0 band definitions changed")
    if historical["public_I1"]["rho_query_values"] != rule["rho_query_values"]:
        raise ValueError("Historical rho query grid changed")
    for role in ROLES:
        rs = sampling["role_distributions"][role]
        lo, hi = rs["D_million_uniform"]
        if not (math.isfinite(lo) and math.isfinite(hi) and 0 < lo < hi):
            raise ValueError(f"{role}: invalid D range")
        if (rs["delta_fixed"] is None) == (rs["delta_uniform"] is None):
            raise ValueError(f"{role}: exactly one delta source required")
        if rs["delta_uniform"] is not None:
            dl, dh = rs["delta_uniform"]
            if not (0 <= dl < dh < 1):
                raise ValueError(f"{role}: invalid delta interval")
            max_delta = dh
        else:
            max_delta = rs["delta_fixed"]
            if not 0 <= max_delta < 1:
                raise ValueError(f"{role}: invalid fixed delta")
        max_util = 1e6 * hi * (1 + max_delta) * f["execution_fraction_x"] / (
            f["effective_IPT"] * historical["workload"]["period_seconds"]
        )
        if max_util > sampling["physical_preconditions"]["max_approx_utilization"]:
            raise ValueError(f"{role}: maximum design utilization exceeds predeclared cap")
    if (sampling["role_distributions"]["P1"]["delta_fixed"] != 0
            or sampling["role_distributions"]["P3"]["delta_fixed"] != 0):
        raise ValueError("P1/P3 must remain homogeneous in this local-transfer design")


def make_candidate(proposal: dict, historical: dict, battery: int, role: str, attempt: int) -> dict:
    sampling = proposal["sampling"]
    seed_key = f"{sampling['preview_seed']}|B{battery:04d}|{role}|A{attempt:02d}"
    seed = int.from_bytes(hashlib.sha256(seed_key.encode("utf-8")).digest(), "big")
    generator = random.Random(seed)
    spec = sampling["role_distributions"][role]
    d_lo, d_hi = spec["D_million_uniform"]
    d = round(1e6 * (d_lo + (d_hi - d_lo) * generator.random()))
    if spec["delta_uniform"] is None:
        delta = float(spec["delta_fixed"])
    else:
        lo, hi = spec["delta_uniform"]
        delta = round(lo + (hi - lo) * generator.random(), 6)
    means = {"ProviderA": round(d * (1.0 - delta)),
             "ProviderB": d,
             "ProviderC": round(d * (1.0 + delta))}
    family = historical["provider_family"]
    period = historical["workload"]["period_seconds"]
    denom = family["effective_IPT"] * period
    utils = {name: value * family["execution_fraction_x"] / denom
             for name, value in means.items()}
    cap = sampling["physical_preconditions"]["max_approx_utilization"]
    if any(value <= 0 for value in means.values()) or max(utils.values()) > cap:
        raise ValueError("Sample outside frozen physical validity bounds; not silently repaired")
    if sampling["disallow_exact_original_world_coordinates"]:
        for old in historical["provider_worlds"]:
            if d == int(old["D_instructions"]) and delta == float(old["delta"]):
                raise ValueError("Draft repeated an exact historical physical world; stop, do not resample")
    uid = f"B{battery:04d}_{role}_A{attempt:02d}"
    return {
        "battery_id":f"B{battery:04d}","role":role,"attempt":attempt,"candidate_id":uid,
        "D_instructions":d,"delta":delta,
        "provider_means":means,"approx_utilization":utils,
        "max_approx_utilization":max(utils.values()),
        "step0_status":"NOT_RUN",
        "security":"PRIVATE_GENERATING_PARAMETERS_NOT_FOR_POLICY",
    }


def make_preview(proposal: dict, historical: dict) -> list[dict]:
    validate_proposal(proposal, historical)
    sampling = proposal["sampling"]
    world_list = []
    for i in range(1, sampling["preview_batteries"] + 1):
        for role in ROLES:
            for attempt in range(1, sampling["max_attempts_per_role"] + 1):
                world_list.append(make_candidate(proposal, historical, i, role, attempt))
    if len({(c["role"],c["D_instructions"],c["delta"]) for c in world_list}) != len(world_list):
        raise ValueError("Duplicate physical configurations in preview; stop without replacement")
    return world_list


def classify_four_graphs(graph_statuses: dict) -> str:
    """Pure Step-0 outcome classification, for future adapter testing only."""
    if set(graph_statuses) != set(GRAPHS):
        raise ValueError("Four exact graph statuses required; incomplete world cannot pass")
    statuses = set(graph_statuses.values())
    if not statuses.issubset({PASS, FAIL, FAIL_CAL}):
        raise ValueError(f"Unknown or incomplete Step-0 evidence status {statuses}")
    return "ELIGIBLE_ALL4" if statuses == {PASS} else "INELIGIBLE_ALL4"


def first_eligible_attempts(candidates: list[dict], evidence: dict, battery_id: str) -> dict:
    """Pure, battery-scoped recruitment rule; no simulator or file access.

    evidence maps candidate_id to exact four-graph Step-0 status dictionaries.
    An earlier unexamined candidate blocks a later success; no outcome-guided
    or selective skipping. This is NOT called by the dry-run sampler.
    """
    chosen = {}
    for role in ROLES:
        options = sorted((c for c in candidates if c["role"] == role
                          and c["battery_id"] == battery_id),
                         key=lambda c: c["attempt"])
        if not options or [c["attempt"] for c in options] != list(range(1,len(options)+1)):
            raise ValueError(f"{battery_id}/{role}: missing/nonsequential candidate attempts")
        for c in options:
            uid = c["candidate_id"]
            if uid not in evidence:
                chosen[role] = None  # PENDING, not a pass/failure
                break
            if classify_four_graphs(evidence[uid]) == "ELIGIBLE_ALL4":
                chosen[role] = uid
                break
        else:
            chosen[role] = "EXHAUSTED_WITHOUT_ELIGIBLE_WORLD"
    return chosen


def write_preview(out: Path, proposal: dict, historical: dict, candidates: list[dict],
                  input_hashes: dict) -> None:
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite any existing preview directory: {out}")
    out.mkdir(parents=True)
    document = {
        "status":"B1_NEW_WORLD_DRY_RUN_ONLY_NOT_STEP0_ELIGIBILITY",
        "execution_authorized":False,"scientific_predictions_generated":0,
        "provider_simulations_generated":0,"candidate_status":"NOT_RUN",
        "input_sha256":input_hashes,
        "graph_ids":GRAPHS,"world_roles":ROLES,
        "generator":"Python random.Random with SHA-256 candidate-specific seeds",
        "scope":"local Gamma one-server FCFS service family only",
        "candidates":candidates,
    }
    (out/"PRIVATE_world_candidates.json").write_text(
        json.dumps(document,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    with (out/"PRIVATE_world_candidates.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=ROWS)
        writer.writeheader()
        for c in candidates:
            writer.writerow({
                "battery_id":c["battery_id"],"role":c["role"],
                "attempt":c["attempt"],"candidate_id":c["candidate_id"],
                "D_instructions":c["D_instructions"],"delta":c["delta"],
                **{f"{p}_instructions":c["provider_means"][p]
                   for p in ("ProviderA","ProviderB","ProviderC")},
                "max_approx_utilization":f"{c['max_approx_utilization']:.8f}",
                "step0_status":c["step0_status"],
            })
    (out/"PREVIEW_ONLY.md").write_text(
        "# B1 proposed new-world generator preview\n\n"
        f"Generated {len(candidates)} *unassessed* physical parameter candidates "
        f"for {proposal['sampling']['preview_batteries']} proposed complete batteries, "
        f"at most {proposal['sampling']['max_attempts_per_role']} attempts per role.\n\n"
        "**None has undergone Step-0, and none is eligible yet.**\n\n"
        "The generator's physical parameters are private to the simulation "
        "orchestrator. Never feed them to the B1 acquisition policy. "
        "No fresh-provider simulation is authorized by this preview.\n",
        encoding="utf-8")
    outputs = {p.name:digest(p) for p in out.iterdir() if p.is_file()}
    (out/"dry_run_manifest.json").write_text(json.dumps({
        "status":"B1_WORLD_GENERATOR_DRY_RUN_V0_1",
        "execution_authorized":False,
        "fresh_simulations":0,
        "input_sha256":input_hashes,"output_sha256":outputs,
        "n_candidates":len(candidates),
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo",type=Path,default=REPO)
    ap.add_argument("--config",type=Path,default=DRAFT)
    ap.add_argument("--out",type=Path,default=Path.home()/"praise/planb_b1_newworld_preview_v0_1")
    args=ap.parse_args()
    repo=args.repo.expanduser().resolve()
    out=args.out.expanduser().resolve()
    if out == repo or repo in out.parents:
        ap.error("Output must be outside the source repository")
    proposal_path=args.config.expanduser().resolve()
    paths=(proposal_path,repo/CONTRACT,repo/STEP0,repo/POLICY)
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(p)
    proposal, historical=load_json(proposal_path), load_json(repo/CONTRACT)
    candidates=make_preview(proposal,historical)
    write_preview(out,proposal,historical,candidates,
                  {str(p):digest(p) for p in paths})
    print("B1_NEW_WORLD_SAMPLING_DRY_RUN_PASS",len(candidates),"UNASSESSED candidates")
    print("ALL_STEP0_STATUSES",set(c["step0_status"] for c in candidates))
    print("NO_SIMULATIONS_NO_B1_POLICY_CHANGES")
    print("OUTPUT",out)


if __name__ == "__main__":
    main()
