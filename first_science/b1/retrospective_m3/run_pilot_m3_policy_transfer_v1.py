#!/usr/bin/env python3
"""Transfer the ORIGINAL pilot M3 selection procedure to the 12-case Phase-II battery.

Exploratory/post-result research only. This is not a new holdout and does not
alter the archived pilot, Phase-II FULL343, or Phase-III fixed-K14 predictions.

Public-only steps: construct candidate domains by the original pilot rule,
score 48 LHS candidates/provider, choose lambda by the original 5-fold I1 CV,
choose the smallest joint-weight prefix with >= 99.9% mass, then run B=1400
graph trajectories with the original minimax integer allocation.

The isolated underlying engine supplies validated local and graph simulation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST = HERE.parent.parent
P3 = FIRST / "phase3"
P4 = FIRST / "phase4"
for folder in (P3, P4):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import _pilot_m3_policy_transfer_core_v1 as core
from m1_joint_lift_v2 import build_search_bounds
from m3_lambda_cv_v3 import _fold_assignments, _cv_scores, _summarize_cv, _select_lambda

CONFIG = HERE / "config_pilot_m3_policy_transfer_v1.json"
OUT = core.OUT
PILOT_BASE = P3 / "config_phase3_m1_contract_v2.json"
PILOT_EXPANDED = P3 / "config_phase3_m1_contract_v2_providerC_expanded_v1.json"
PILOT_CV = P4 / "config_phase4_m3_lambda_cv_v3.json"
PROVIDERS = core.PROVIDERS
TARGET_COLUMNS = ["region_rho", "rho", "horizon"]


def pilot_bounds(world, provider):
    """The actual Phase-4 LHS domain rule, evaluated on new PUBLIC I1 cards."""
    metadata, _, _ = core._load_public_card(world, provider)
    contract_file = PILOT_EXPANDED if provider == "ProviderC" else PILOT_BASE
    return build_search_bounds(metadata, core.read_json(contract_file))


def candidate_design(cfg, world, provider):
    bounds = pilot_bounds(world, provider)
    unit = core._latin_hypercube(
        48, 3, cfg["lhs_seed"] + PROVIDERS.index(provider) * 100003
    )
    data = core._map_unit_to_parameters(unit, bounds)
    data.insert(0, "candidate_id", [
        f"{world}_{provider}_LHS_{i:03d}" for i in range(48)
    ])
    return data


# Only this new, isolated engine instance uses the original pilot domain rule.
core.candidate_design = candidate_design


def configuration():
    cfg = core.read_json(CONFIG)
    if cfg.get("status") != "B1_PILOT_M3_POLICY_TRANSFER_V1_FROZEN":
        raise RuntimeError("Unexpected pilot-transfer contract")
    contracts = core.load_phase5_contracts(core.P5)
    m2 = contracts.methods["M2"]["nonadaptive_LHS"]
    if cfg["lhs_seed"] != int(m2["seed"]) or cfg["n_candidates_per_provider"] != 48:
        raise RuntimeError("Pilot 48-point LHS design differs")
    if cfg["lambda"] != 30 or cfg["top_k"] != 14:
        raise RuntimeError("Internal local-score placeholders must remain 30/14")
    if cfg["local_rescore_start"] != 35000 or cfg["local_rescore_n"] != 100:
        raise RuntimeError("Pilot 100-trajectory local seed bank changed")
    if cfg["graph_budget"] != 1400 or cfg["target_mass"] != 0.999:
        raise RuntimeError("Pilot adaptive support target or graph budget changed")
    if cfg["eligible_worlds"] != ["P1", "P3", "P4"]:
        raise RuntimeError("Provider-world eligibility changed")
    if cfg["graphs"] != ["G_PAR", "G_SEQ", "G_SEQPAR", "G_PARSEQ"]:
        raise RuntimeError("Graph battery changed")
    if cfg["seed_stride"] < cfg["graph_budget"]:
        raise RuntimeError("Rank-specific graph seed stride too small")
    if cfg["top14_seed_base"] < 9000000 or cfg["top1_seed_base"] < 9000000:
        raise RuntimeError("Graph seed banks must be new, disjoint banks")
    # Even if the adaptive support fills the entire B1400 allocation, its
    # rank-specific seed prefixes cannot intersect the separately sampled Top1.
    if cfg["top1_seed_base"] <= cfg["top14_seed_base"] + cfg["graph_budget"] * cfg["seed_stride"]:
        raise RuntimeError("TopK and Top1 graph seed namespaces could overlap")
    expected_grid = core.read_json(PILOT_CV)["lambda_grid"]
    if list(map(float, cfg["lambda_grid"])) != list(map(float, expected_grid)):
        raise RuntimeError("Pilot lambda CV grid has changed")
    return cfg, contracts


def preflight(cfg):
    core.eligible_cells(cfg)
    for world in cfg["eligible_worlds"]:
        for provider in PROVIDERS:
            frame = candidate_design(cfg, world, provider)
            if len(frame) != 48 or not np.isfinite(
                frame[["mean_service_time", "cost_rate", "service_cv"]].to_numpy()
            ).all():
                raise RuntimeError(f"Invalid public candidate design {world}/{provider}")
        for graph in cfg["graphs"]:
            core._query_definitions(core.physical_cell_id(world, graph))
    print("B1_PILOT_M3_POLICY_TRANSFER_PREFLIGHT_PASS")
    print("Public pilot domain-construction rule, original lambda-CV grid and adaptive 99.9% support.")
    print("No hidden provider truth or graph white-box reference opened.")


def public_cv_surfaces(world):
    """Build the exact Phase-4 CV inputs from 48 saved candidate I1 curves/provider."""
    surfaces = {}
    for provider in PROVIDERS:
        root = OUT / "candidates" / world / provider
        metadata, public, _record = core._load_public_card(world, provider)
        ref = public.loc[public["horizon"].astype(float) > 0].sort_values(
            TARGET_COLUMNS, kind="mergesort"
        ).reset_index(drop=True)
        if len(ref) != 1200:
            raise RuntimeError(f"{world}/{provider}: expected 1200 public I1 points")
        p = ref["sigma_hat"].to_numpy(float)
        if not np.isfinite(p).all():
            raise RuntimeError("Nonfinite public I1")
        surfaces[provider] = {}
        for cid in candidate_design(core.read_json(CONFIG), world, provider)["candidate_id"]:
            curve = pd.read_csv(root / "surfaces" / (str(cid) + ".csv"))
            if len(curve) != len(ref) or curve["point_index"].astype(int).tolist() != list(range(1200)):
                raise RuntimeError(f"Candidate point indexing mismatch: {cid}")
            q_public = curve["sigma_i1"].to_numpy(float)
            q_model = curve["sigma_m1_local"].to_numpy(float)
            if not np.allclose(p, q_public, atol=1e-12, rtol=0):
                raise RuntimeError(f"Candidate public I1 alignment changed: {cid}")
            if not np.isfinite(q_model).all():
                raise RuntimeError(f"Nonfinite candidate curve: {cid}")
            pp = (100 * p + 0.5) / 101.
            qq = (100 * q_model + 0.5) / 101.
            frame = ref[TARGET_COLUMNS].copy()
            frame["p_i1_jeffreys"] = pp
            frame["p_candidate_jeffreys"] = qq
            frame["bernoulli_kl_i1_to_candidate"] = (
                pp * np.log(pp / qq) + (1 - pp) * np.log((1 - pp) / (1 - qq))
            )
            surfaces[provider][str(cid)] = frame
    return surfaces


def freeze_csv(path, data, *, overwrite_interim=False):
    """Keep selected/validated scientific output immutable on resumption."""
    import io
    buf = io.StringIO()
    data.to_csv(buf, index=False)
    content = buf.getvalue()
    if path.exists():
        if not overwrite_interim and path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"Already frozen CSV differs: {path}")
        if path.read_text(encoding="utf-8") == content:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def freeze_json(path, obj):
    if path.exists():
        if core.read_json(path) != obj:
            raise RuntimeError(f"Already frozen JSON differs: {path}")
    else:
        core.write_json(path, obj)


def cv_select_and_freeze(cfg, world):
    root = OUT / "candidate_support" / world
    if (root / "support_manifest.json").exists():
        manifest = core.read_json(root / "support_manifest.json")
        if manifest.get("config_sha256") != core.sha256_file(CONFIG):
            raise RuntimeError("Existing policy-transfer support uses different contract")
        if core.sha256_file(root / "adaptive_support.csv") != manifest["support_sha256"]:
            raise RuntimeError("Existing adaptive support hash mismatch")
        print(f"REUSED FROZEN WORLD {world}: K={manifest['top_k']}")
        return
    surfaces = public_cv_surfaces(world)
    assignments = _fold_assignments(next(iter(surfaces["ProviderA"].values())))
    scores = _cv_scores(
        surfaces=surfaces, assignments=assignments,
        lambda_grid=list(map(float, cfg["lambda_grid"]))
    )
    summary = _summarize_cv(scores)
    winner = _select_lambda(summary)
    selected_lambda = float(winner["lambda"])
    root.mkdir(parents=True, exist_ok=True)
    freeze_csv(root / "cv_assignments.csv", assignments)
    freeze_csv(root / "cv_scores.csv", scores)
    freeze_csv(root / "cv_summary.csv", summary)
    cv_record = {
        "status": "B1_PILOT_POLICY_I1_CV_FROZEN",
        "world": world, "selected_lambda": selected_lambda,
        "selected_mean_heldout_kl": float(winner["mean_validation_bernoulli_kl"]),
        "pilot_cv_contract_sha256": core.sha256_file(PILOT_CV),
        "cv_scores_sha256": core.sha256_file(root / "cv_scores.csv"),
        "cv_summary_sha256": core.sha256_file(root / "cv_summary.csv"),
        "no_graph_whitebox_read": True,
    }
    freeze_json(root / "cv_selection.json", cv_record)

    for provider in PROVIDERS:
        base = OUT / "candidates" / world / provider
        original_manifest_path = base / "provider_manifest.json"
        old = core.read_json(original_manifest_path)
        if old.get("status") not in (
            "B1_PILOT_POLICY_PROVIDER_FROZEN", "B1_PILOT_POLICY_CV_PROVIDER_FROZEN"
        ):
            raise RuntimeError(f"Unexpected candidate-preparation provenance: {provider}")
        design = candidate_design(cfg, world, provider)
        ids = design["candidate_id"].astype(str)
        frames = [pd.read_csv(base / "surfaces" / (cid + ".csv")) for cid in ids]
        public = frames[0]["sigma_i1"].to_numpy(float)
        simulated = np.stack([t["sigma_m1_local"].to_numpy(float) for t in frames])
        weights = core.gibbs_weights(
            ids, simulated, public, n_public=100, n_candidate=100, lam=selected_lambda
        )
        weights = design.merge(weights, on="candidate_id", validate="one_to_one")
        weights["local_mse"] = [float(np.mean((public - row) ** 2)) for row in simulated]
        weights["curve_sha256"] = [
            core.sha256_file(base / "surfaces" / (cid + ".csv")) for cid in ids
        ]
        weights = weights.sort_values("weight_rank", kind="mergesort")
        target = base / "provider_weights.csv"
        already_selected = old["status"] == "B1_PILOT_POLICY_CV_PROVIDER_FROZEN"
        freeze_csv(target, weights, overwrite_interim=not already_selected)
        meta, _, record = core._load_public_card(world, provider)
        data = {
            "status": "B1_PILOT_POLICY_CV_PROVIDER_FROZEN",
            "world": world, "provider": provider, "candidates": 48,
            "design_sha256": core.sha256_file(base / "lhs_design.csv"),
            "weights_sha256": core.sha256_file(target),
            "public_card_json_sha256": record["card_json_sha256"],
            "public_sigma_surface_sha256": record["sigma_surface_sha256"],
            "pilot_domain_contract_sha256": core.sha256_file(
                PILOT_EXPANDED if provider == "ProviderC" else PILOT_BASE
            ),
            "cv_selection_sha256": core.sha256_file(root / "cv_selection.json"),
            "selected_lambda": selected_lambda, "config_sha256": core.sha256_file(CONFIG),
            "no_graph_whitebox_read": True,
        }
        if already_selected:
            if old != data:
                raise RuntimeError(f"Existing frozen provider CV weights changed: {provider}")
        else:
            core.write_json(original_manifest_path, data)
    print(f"I1-only pilot CV: {world}, selected lambda={selected_lambda:g}")
    freeze_adaptive_support(cfg, world)


def freeze_adaptive_support(cfg, world):
    root = OUT / "candidate_support" / world
    providers = {}
    for provider in PROVIDERS:
        target = OUT / "candidates" / world / provider / "provider_weights.csv"
        pm = core.read_json(target.parent / "provider_manifest.json")
        if pm["weights_sha256"] != core.sha256_file(target):
            raise RuntimeError(f"{world}/{provider} weight hash mismatch")
        providers[provider] = pd.read_csv(target)
    joint = core.joint_product_support(providers)
    if len(joint) != 48**3:
        raise RuntimeError("Joint product does not have 48^3 members")
    cumulative = joint["joint_weight"].astype(float).cumsum().to_numpy()
    k = int(np.searchsorted(cumulative, cfg["target_mass"], side="left") + 1)
    retained = float(cumulative[k - 1])
    freeze_json(root / "support_feasibility.json", {
        "status": "B1_PILOT_POLICY_SUPPORT_FEASIBILITY",
        "world": world, "selected_lambda": core.read_json(root / "cv_selection.json")["selected_lambda"],
        "top_k": k, "target_mass": cfg["target_mass"],
        "retained_mass": retained, "graph_budget": cfg["graph_budget"],
        "feasible": k <= cfg["graph_budget"],
        "no_graph_whitebox_read": True,
    })
    if k > cfg["graph_budget"]:
        raise RuntimeError(
            f"{world}: original 99.9%-mass selection requires K={k} models, "
            f"but frozen graph budget B={cfg['graph_budget']} permits fewer than one "
            "trajectory per model. Feasibility saved; stop without changing either rule."
        )
    top = joint.iloc[:k].copy()
    top["alpha"] = top["joint_weight"] / retained
    top["n_trajectories"] = core.allocation(top["alpha"].to_numpy(float), cfg["graph_budget"])
    top["seed_start"] = [
        cfg["top14_seed_base"] + i * cfg["seed_stride"] for i in range(k)
    ]
    top["seed_end_inclusive"] = top["seed_start"] + top["n_trajectories"] - 1
    top["retained_mass"] = retained
    top["omitted_mass"] = 1 - retained
    dest = root / "adaptive_support.csv"
    freeze_csv(dest, top)
    freeze_json(root / "support_manifest.json", {
        "status": "B1_PILOT_POLICY_SUPPORT_FROZEN",
        "world": world, "top_k": k, "full_support_size": 48**3,
        "retained_mass": retained, "omitted_mass": 1 - retained,
        "graph_budget": cfg["graph_budget"],
        "support_sha256": core.sha256_file(dest),
        "provider_weights_sha256": {
            p: core.sha256_file(OUT / "candidates" / world / p / "provider_weights.csv")
            for p in PROVIDERS
        },
        "cv_selection_sha256": core.sha256_file(root / "cv_selection.json"),
        "config_sha256": core.sha256_file(CONFIG),
        "no_graph_whitebox_read": True,
    })
    print(f"FROZEN {world}: CV lambda={core.read_json(root/'cv_selection.json')['selected_lambda']:g}, "
          f"adaptive TopK={k}, mass={retained:.6f}, B={cfg['graph_budget']}")


def prepare_world(cfg, world, *, workers, benchmark_candidates=0):
    base = OUT / "candidate_support" / world
    if (base / "support_manifest.json").exists():
        cv_select_and_freeze(cfg, world)
        return
    with core._world_prepare_lock(world):
        for provider in PROVIDERS:
            meta = OUT / "candidates" / world / provider / "provider_manifest.json"
            cv_started = (base / "cv_selection.json").is_file()
            if cv_started:
                design = candidate_design(cfg, world, provider)
                curve_root = meta.parent / "surfaces"
                if all((curve_root / (cid + ".csv")).is_file()
                       for cid in design["candidate_id"].astype(str)):
                    print(f"CV checkpoint found for {world}/{provider}: "
                          "all 48 local curves preserved; skip provisional reweighting")
                    continue
                raise RuntimeError(
                    f"{world}/{provider}: CV was already selected but candidate "
                    "surfaces are incomplete; do not silently repair the frozen bank"
                )
            if meta.exists() and core.read_json(meta).get("status") == "B1_PILOT_POLICY_CV_PROVIDER_FROZEN":
                raise RuntimeError(
                    f"{world}/{provider}: final provider weights exist without a "
                    "matching world CV selection manifest"
                )
            ok = core.prepare_provider(
                cfg, world, provider, workers=workers,
                limit_candidates=benchmark_candidates
            )
            if benchmark_candidates and not ok:
                continue
        if benchmark_candidates:
            print(f"BENCHMARK {world}: candidate checkpoints only; resume full prepare")
            return
        cv_select_and_freeze(cfg, world)


def require_reproduced_pilot_gate():
    """Fail closed: no battery simulations before exact pilot reproduction."""
    import hashlib

    def sha(path):
        h = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    root = FIRST / "b1" / "local_audit" / "pilot_m3_reproduction_gate_v1"
    gate = root / "gate.json"
    if not gate.is_file():
        raise RuntimeError(
            "Original pilot reproduction gate is not passed. "
            "First run run_pilot_m3_reproduction_gate_v1.py on PILOT cases only, "
            "through deterministic, archived-scoring, graph-smoke, full-graph and seal."
        )
    record = core.read_json(gate)
    if record.get("status") != "B1_PILOT_REPRODUCTION_GATE_PASS" or record.get("decision") != "PASS":
        raise RuntimeError("Pilot reproduction gate did not pass")
    for key, path in (
        ("transfer_contract_sha256", CONFIG),
        ("transfer_code_sha256", HERE / "run_pilot_m3_policy_transfer_v1.py"),
        ("transfer_core_sha256", HERE / "_pilot_m3_policy_transfer_core_v1.py"),
        ("pilot_graph_contract_sha256", P4 / "config_phase4_m3_v4_dominant_mass_graph_v1.json"),
        ("pilot_cv_contract_sha256", PILOT_CV),
    ):
        if record.get(key) != sha(path):
            raise RuntimeError(f"Stale pilot reproduction gate: {key}")
    for stage, expected_sha in record.get("pilot_stages_sha256", {}).items():
        stagefile = root / (stage + ".json")
        if not stagefile.is_file() or sha(stagefile) != expected_sha:
            raise RuntimeError(f"Pilot reproduction stage checkpoint differs: {stage}")
    if set(record.get("pilot_stages_sha256", {})) != {
        "deterministic", "archived_scoring", "graph_smoke", "full_graph"
    }:
        raise RuntimeError("Incomplete pilot reproduction checks")
    print("B1_PILOT_M3_REPRODUCTION_GATE_CONFIRMED")


def main():
    parser = argparse.ArgumentParser(description="Faithful pilot M3 selection-policy transfer")
    parser.add_argument("--stage", required=True, choices=[
        "preflight", "benchmark", "prepare", "graph-benchmark",
        "predict", "freeze", "evaluate"
    ])
    parser.add_argument("--world", choices=["P1", "P3", "P4"])
    parser.add_argument("--cell", help="e.g. P1__G_PAR")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--benchmark-candidates", type=int, default=3)
    args = parser.parse_args()
    cfg, contracts = configuration()
    if args.stage != "preflight":
        require_reproduced_pilot_gate()
    if args.workers < 1:
        raise ValueError("workers must be >=1")
    if args.stage == "preflight":
        preflight(cfg)
    elif args.stage in ("prepare", "benchmark"):
        if args.stage == "benchmark" and (
            args.world is None or not 1 <= args.benchmark_candidates < 48
        ):
            raise ValueError("Bounded benchmark needs --world and 1..47 candidates")
        for world in ([args.world] if args.world else cfg["eligible_worlds"]):
            prepare_world(
                cfg, world, workers=args.workers,
                benchmark_candidates=(
                    args.benchmark_candidates if args.stage == "benchmark" else 0
                )
            )
    elif args.stage == "graph-benchmark":
        if not args.cell:
            raise ValueError("Specify --cell")
        core.benchmark_graph(cfg, contracts, args.cell, args.workers)
    elif args.stage == "predict":
        allowed = {core.physical_cell_id(w, g) for w in cfg["eligible_worlds"]
                   for g in cfg["graphs"]}
        if args.cell and args.cell not in allowed:
            raise ValueError("Cell not in the Phase-II eligible battery")
        for cell in ([args.cell] if args.cell else sorted(allowed)):
            core.predict_cell(cfg, contracts, cell, args.workers)
        if not args.cell:
            core.freeze_all(cfg)
    elif args.stage == "freeze":
        core.freeze_all(cfg)
    elif args.stage == "evaluate":
        # This is the ONLY stage that reads the archived Phase-II white-box results.
        core.evaluate(cfg)


if __name__ == "__main__":
    main()
