#!/usr/bin/env python3
"""Blind M0/M1/M2 prediction for the frozen fixed-graph sigma-regime battery.

This runner never reads or generates final white-box evidence. It validates the
passed Step-0 v2 freeze, reuses the unchanged frozen M1/M2 method definitions,
simulates BASE_M1 plus all 27 frozen M2 joint members on seeds 33000..33099,
and evaluates all 15 frozen A_G queries from the same per-variant graph ledger.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
for directory in (PHASE2, PHASE3, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (
    build_same_rho_conditioned_m0_curve,
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from m0_analytic_composition import (
    AdmissibilityBoundary,
    boundary_is_sufficient_for_query,
)
from run_m1_graph_prediction_v2 import (
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
    build_public_induced_global_boundary,
)
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json
from m2_b5_joint_ensemble_graph import (
    _ledger,
    _validate_and_build_variants,
)

EXPECTED_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_BLIND_PREDICTION_V1"
EXPECTED_STEP0_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_CALIBRATION_PASS_V2"
COMPLETE_STATUS = "FROZEN_PHASE4_SIGMA_REGIME_BLIND_PREDICTIONS_V1"
TOL = 1e-12


def _seed_bank(contract: dict[str, Any]) -> tuple[int, ...]:
    cfg = dict(contract["prediction_simulation"])
    seeds = tuple(
        range(int(cfg["seed_start"]), int(cfg["seed_end_inclusive"]) + 1)
    )
    if len(seeds) != int(cfg["n_trajectories_per_variant"]):
        raise RuntimeError("prediction seed-bank length mismatch")
    if seeds != tuple(range(33000, 33100)):
        raise RuntimeError("blind prediction seeds changed from 33000..33099")
    return seeds


def _validate_step0(
    *,
    contract: dict[str, Any],
    step0_manifest_path: Path,
    selected_regions_path: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    manifest = _read_json(step0_manifest_path)
    required = dict(contract["step0"])
    if manifest.get("status") != str(required["required_manifest_status"]):
        raise RuntimeError("Step-0 v2 did not freeze PASS")
    if manifest.get("status") != EXPECTED_STEP0_STATUS:
        raise RuntimeError("unexpected Step-0 status")
    if str(manifest["selected_regions_frozen_sha256"]) != _sha256(
        selected_regions_path
    ):
        raise RuntimeError("Step-0 frozen regions hash mismatch")

    selected = pd.read_csv(selected_regions_path)
    required_cols = {
        "rho_global", "regime", "scale",
        "A_G_l_max", "A_G_c_max", "A_G_q_min",
    }
    missing = sorted(required_cols.difference(selected.columns))
    if missing:
        raise RuntimeError("frozen Step-0 query file missing: " + ", ".join(missing))
    if len(selected) != int(required["required_n_queries"]):
        raise RuntimeError("expected exactly 15 frozen Step-0 queries")
    if selected[["rho_global", "regime"]].duplicated().any():
        raise RuntimeError("duplicate rho/regime query in Step-0 freeze")
    if set(selected["regime"].astype(str)) != {"G0", "G1", "G2"}:
        raise RuntimeError("Step-0 freeze does not contain G0/G1/G2")
    counts = selected.groupby("rho_global")["regime"].nunique()
    if len(counts) != 5 or not (counts == 3).all():
        raise RuntimeError("Step-0 freeze must contain three regimes at each of five rhos")
    return manifest, selected.sort_values(["rho_global", "regime"]).reset_index(drop=True)


def _validate_variants(args, contract):
    b5_contract = _read_json(args.b5_contract.resolve())
    semantic = _read_json(args.semantic_contract.resolve())
    anchors, portfolio, variants, design = _validate_and_build_variants(
        contract=b5_contract,
        semantic_contract=semantic,
        a4_manifest_path=args.a4_confirmation_manifest.resolve(),
        a4_portfolio_path=args.a4_final_portfolio.resolve(),
        a4_replay_path=args.a4_replay_results.resolve(),
        m1_manifest_path=args.m1_confirmation_manifest.resolve(),
        m1_candidates_path=args.m1_anchor_candidates.resolve(),
    )
    cfg = dict(contract["prediction_simulation"])
    if len(variants) != int(cfg["n_total_variants"]):
        raise RuntimeError("frozen variant count differs from prediction contract")
    if "BASE_M1" not in variants:
        raise RuntimeError("BASE_M1 missing")
    if int(design["ensemble_member"].astype(bool).sum()) != int(cfg["n_M2_variants"]):
        raise RuntimeError("M2 design is not exactly 27 members")
    return anchors, portfolio, variants, design


def _query_boundary(rec: pd.Series) -> AdmissibilityBoundary:
    return AdmissibilityBoundary(
        l_max=float(rec["A_G_l_max"]),
        c_max=float(rec["A_G_c_max"]),
        q_min=float(rec["A_G_q_min"]),
    )


def _simulate_variant_worker(payload: tuple) -> tuple[str, bool, int]:
    (
        variant_id,
        surrogate_map,
        seeds,
        graph_spec,
        workload,
        canonical_ipt,
        execution_fraction,
        path_string,
    ) = payload
    frame, reused = _ledger(
        variant_id=variant_id,
        surrogates=surrogate_map,
        seeds=tuple(seeds),
        graph_spec=graph_spec,
        workload=workload,
        canonical_ipt=float(canonical_ipt),
        execution_fraction=float(execution_fraction),
        path=Path(path_string),
    )
    return str(variant_id), bool(reused), int(len(frame))


def _simulate_all(
    *,
    variants: dict[str, Any],
    seeds: tuple[int, ...],
    graph_spec: dict[str, Any],
    workload: dict[str, Any],
    canonical_ipt: float,
    execution_fraction: float,
    ledger_dir: Path,
    workers: int,
) -> tuple[int, int]:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    tasks = [
        (
            variant_id,
            surrogate_map,
            seeds,
            graph_spec,
            workload,
            canonical_ipt,
            execution_fraction,
            str(ledger_dir / f"{variant_id}.csv"),
        )
        for variant_id, surrogate_map in variants.items()
    ]
    reused = 0
    total_rows = 0
    if workers <= 1:
        results = [_simulate_variant_worker(task) for task in tasks]
    else:
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            future_map = {
                pool.submit(_simulate_variant_worker, task): task[0] for task in tasks
            }
            for future in concurrent.futures.as_completed(future_map):
                variant_id = future_map[future]
                result = future.result()
                print(
                    f"Sigma-regime blind prediction variant complete: {variant_id}",
                    flush=True,
                )
                results.append(result)
    for _, was_reused, nrows in results:
        reused += int(was_reused)
        total_rows += int(nrows)
    return reused, total_rows


def _materialize_member_curves(
    *,
    design: pd.DataFrame,
    selected: pd.DataFrame,
    ledger_dir: Path,
    horizons: list[float],
    workload: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    for variant_id in design["variant_id"].astype(str).tolist():
        path = ledger_dir / f"{variant_id}.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing prediction ledger: {path}")
        ledger = pd.read_csv(path)
        for _, query in selected.iterrows():
            boundary = _query_boundary(query)
            curve = build_empirical_graph_sigma_curve(
                ledger,
                boundary=boundary,
                rho_global=float(query["rho_global"]),
                horizons=horizons,
                stop_time=float(workload["horizon_max"]),
                accounting_origin=float(workload["accounting_origin"]),
                output_column="sigma",
            )
            curve.insert(0, "regime", str(query["regime"]))
            curve.insert(0, "rho_global", float(query["rho_global"]))
            curve.insert(0, "variant_id", variant_id)
            curve["scale"] = float(query["scale"])
            curve["A_G_l_max"] = float(boundary.l_max)
            curve["A_G_c_max"] = float(boundary.c_max)
            curve["A_G_q_min"] = float(boundary.q_min)
            rows.append(curve)
    frame = pd.concat(rows, ignore_index=True).sort_values(
        ["variant_id", "rho_global", "regime", "horizon"]
    ).reset_index(drop=True)
    expected = int(len(design) * len(selected) * len(horizons))
    if len(frame) != expected:
        raise RuntimeError(
            f"member curve bank has {len(frame)} rows; expected {expected}"
        )
    return frame


def _aggregate_m1_m2(
    member_curves: pd.DataFrame,
    design: pd.DataFrame,
) -> pd.DataFrame:
    m2_ids = set(
        design.loc[design["ensemble_member"].astype(bool), "variant_id"].astype(str)
    )
    rows = []
    for (rho, regime, horizon), group in member_curves.groupby(
        ["rho_global", "regime", "horizon"], sort=True
    ):
        m2 = group[group["variant_id"].astype(str).isin(m2_ids)]
        m1 = group[group["variant_id"].astype(str) == "BASE_M1"]
        if int(m2["variant_id"].nunique()) != 27 or len(m1) != 1:
            raise RuntimeError(
                f"incomplete prediction ensemble at rho={rho}, {regime}, H={horizon}"
            )
        triples = group[
            ["scale", "A_G_l_max", "A_G_c_max", "A_G_q_min"]
        ].drop_duplicates()
        if len(triples) != 1:
            raise RuntimeError("A_G differs across prediction variants")
        rec = triples.iloc[0]
        values = m2["sigma"].astype(float).to_numpy()
        ids = m2["variant_id"].astype(str).to_numpy()
        i_min = int(np.argmin(values))
        i_max = int(np.argmax(values))
        rows.append({
            "rho_global": float(rho),
            "regime": str(regime),
            "horizon": float(horizon),
            "scale": float(rec["scale"]),
            "A_G_l_max": float(rec["A_G_l_max"]),
            "A_G_c_max": float(rec["A_G_c_max"]),
            "A_G_q_min": float(rec["A_G_q_min"]),
            "sigma_m1": float(m1.iloc[0]["sigma"]),
            "sigma_m2_mean": float(np.mean(values)),
            "sigma_m2_min": float(values[i_min]),
            "sigma_m2_max": float(values[i_max]),
            "sigma_m2_std_population": float(np.std(values, ddof=0)),
            "sigma_m2_median": float(np.median(values)),
            "sigma_m2_q25": float(np.quantile(values, 0.25)),
            "sigma_m2_q75": float(np.quantile(values, 0.75)),
            "m2_argmin_variant_id": str(ids[i_min]),
            "m2_argmax_variant_id": str(ids[i_max]),
        })
    return pd.DataFrame(rows).sort_values(
        ["rho_global", "regime", "horizon"]
    ).reset_index(drop=True)


def _add_m0(
    *,
    predictions: pd.DataFrame,
    selected: pd.DataFrame,
    metadata: dict[str, dict[str, object]],
    provider_surfaces: dict[str, pd.DataFrame],
    m0_contract: dict[str, Any],
    horizons: list[float],
) -> pd.DataFrame:
    pieces = []
    for _, query in selected.iterrows():
        rho = float(query["rho_global"])
        regime = str(query["regime"])
        requested = _query_boundary(query)
        provider_boundaries = provider_boundaries_at_region_rho(metadata, rho)
        induced = build_public_induced_global_boundary(
            provider_boundaries, m0_contract
        )
        applicable = boundary_is_sufficient_for_query(induced, requested)
        raw = build_same_rho_conditioned_m0_curve(
            provider_surfaces, rho=rho, horizons=horizons
        )[["horizon", "sigma_i1_m0"]].rename(
            columns={"sigma_i1_m0": "sigma_m0_raw_product"}
        )
        raw.insert(0, "regime", regime)
        raw.insert(0, "rho_global", rho)
        raw["m0_status"] = "PREDICTED" if applicable else "NOT_APPLICABLE"
        raw["sigma_m0"] = (
            raw["sigma_m0_raw_product"].astype(float)
            if applicable
            else np.nan
        )
        raw["m0_induced_l_max"] = float(induced.l_max)
        raw["m0_induced_c_max"] = float(induced.c_max)
        raw["m0_induced_q_min"] = float(induced.q_min)
        pieces.append(raw)
    m0 = pd.concat(pieces, ignore_index=True)
    merged = predictions.merge(
        m0,
        on=["rho_global", "regime", "horizon"],
        how="left",
        validate="one_to_one",
    )
    if merged["m0_status"].isna().any():
        raise RuntimeError("M0 merge lost query points")
    return merged


def _ledger_hash_table(ledger_dir: Path, design: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant_id in design["variant_id"].astype(str):
        path = ledger_dir / f"{variant_id}.csv"
        rows.append({
            "variant_id": variant_id,
            "sha256": _sha256(path),
            "bytes": int(path.stat().st_size),
        })
    return pd.DataFrame(rows)


def _prepare(args, contract, selected, design, metadata, m0_contract) -> None:
    seeds = _seed_bank(contract)
    applicability = []
    for _, query in selected.iterrows():
        rho = float(query["rho_global"])
        local = provider_boundaries_at_region_rho(metadata, rho)
        induced = build_public_induced_global_boundary(local, m0_contract)
        applicable = boundary_is_sufficient_for_query(
            induced, _query_boundary(query)
        )
        applicability.append({
            "rho_global": rho,
            "regime": str(query["regime"]),
            "scale": float(query["scale"]),
            "m0_status": "PREDICTED" if applicable else "NOT_APPLICABLE",
        })
    print("SIGMA_REGIME_BLIND_PREDICTION_PREPARE_PASS_NO_FINAL_WHITEBOX")
    print(f"queries={len(selected)} variants={len(design)}")
    print(f"prediction_seeds={seeds[0]}..{seeds[-1]} n={len(seeds)}")
    print(f"planned_graph_trajectories={len(design)*len(seeds)}")
    print("\nM0_APPLICABILITY")
    print(pd.DataFrame(applicability).to_string(index=False))
    print(f"prediction_contract_sha256={_sha256(args.contract.resolve())}")
    print(f"step0_manifest_sha256={_sha256(args.step0_manifest.resolve())}")
    print(f"selected_regions_sha256={_sha256(args.selected_regions.resolve())}")


def run(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    contract = _read_json(args.contract.resolve())
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected sigma-regime prediction contract status")

    step0_manifest, selected = _validate_step0(
        contract=contract,
        step0_manifest_path=args.step0_manifest.resolve(),
        selected_regions_path=args.selected_regions.resolve(),
    )

    metadata, provider_surfaces, _ = load_rho_conditioned_i1_cards(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    rho_support = sorted(float(v) for v in common_same_rho_support(metadata))
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)
    selected_rhos = sorted(float(v) for v in selected["rho_global"].unique())
    if not np.allclose(rho_support, selected_rhos, atol=TOL, rtol=0.0):
        raise RuntimeError("Step-0 rho support differs from frozen public I1")

    m1_contract = _read_json(args.m1_contract.resolve())
    m0_contract = _read_json(args.m0_contract.resolve())
    graph_spec = dict(m0_contract["phase1_benchmark_adapter"])
    canonical_ipt = float(m1_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(m1_contract["pilot_scope"]["execution_fraction"])

    anchors, portfolio, variants, design = _validate_variants(args, contract)
    seeds = _seed_bank(contract)

    if args.prepare_only:
        _prepare(args, contract, selected, design, metadata, m0_contract)
        print(f"python_wall_seconds={time.perf_counter()-started:.3f}")
        return

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    design_path = output / "sigma_regime_variant_design.csv"
    design.to_csv(design_path, index=False)
    candidates_path = output / "sigma_regime_frozen_candidate_set.csv"
    pd.concat(
        [
            anchors.assign(candidate_source="M1_anchor"),
            portfolio.assign(candidate_source="A4_final_portfolio"),
        ],
        ignore_index=True,
        sort=False,
    ).to_csv(candidates_path, index=False)

    ledger_dir = output / "ledgers"
    reused, total_rows = _simulate_all(
        variants=variants,
        seeds=seeds,
        graph_spec=graph_spec,
        workload=workload,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
        ledger_dir=ledger_dir,
        workers=max(1, int(args.workers)),
    )

    member_curves = _materialize_member_curves(
        design=design,
        selected=selected,
        ledger_dir=ledger_dir,
        horizons=horizons,
        workload=workload,
    )
    member_path = output / "sigma_regime_member_curves.csv"
    member_curves.to_csv(member_path, index=False)

    aggregated = _aggregate_m1_m2(member_curves, design)
    predictions = _add_m0(
        predictions=aggregated,
        selected=selected,
        metadata=metadata,
        provider_surfaces=provider_surfaces,
        m0_contract=m0_contract,
        horizons=horizons,
    )
    prediction_path = output / "sigma_regime_blind_predictions.csv"
    predictions.to_csv(prediction_path, index=False)

    ledger_hashes = _ledger_hash_table(ledger_dir, design)
    ledger_hash_path = output / "sigma_regime_ledger_hashes.csv"
    ledger_hashes.to_csv(ledger_hash_path, index=False)

    manifest_path = output / "sigma_regime_prediction_manifest_v1.json"
    _write_json(manifest_path, {
        "status": COMPLETE_STATUS,
        "prediction_contract_sha256": _sha256(args.contract.resolve()),
        "step0_manifest_sha256": _sha256(args.step0_manifest.resolve()),
        "step0_selected_regions_sha256": _sha256(args.selected_regions.resolve()),
        "semantic_contract_sha256": _sha256(args.semantic_contract.resolve()),
        "b5_contract_sha256": _sha256(args.b5_contract.resolve()),
        "a4_confirmation_manifest_sha256": _sha256(args.a4_confirmation_manifest.resolve()),
        "a4_final_portfolio_sha256": _sha256(args.a4_final_portfolio.resolve()),
        "a4_replay_results_sha256": _sha256(args.a4_replay_results.resolve()),
        "m1_confirmation_manifest_sha256": _sha256(args.m1_confirmation_manifest.resolve()),
        "m1_anchor_candidates_sha256": _sha256(args.m1_anchor_candidates.resolve()),
        "m1_contract_sha256": _sha256(args.m1_contract.resolve()),
        "m0_contract_sha256": _sha256(args.m0_contract.resolve()),
        "public_i1_manifest_sha256": _sha256(args.i1_manifest.resolve()),
        "variant_design_sha256": _sha256(design_path),
        "candidate_set_sha256": _sha256(candidates_path),
        "member_curves_sha256": _sha256(member_path),
        "blind_predictions_sha256": _sha256(prediction_path),
        "ledger_hash_table_sha256": _sha256(ledger_hash_path),
        "prediction_seed_start": int(seeds[0]),
        "prediction_seed_end_inclusive": int(seeds[-1]),
        "n_trajectories_per_variant": len(seeds),
        "n_total_variants": len(design),
        "n_m2_variants": int(design["ensemble_member"].astype(bool).sum()),
        "n_queries": len(selected),
        "common_random_numbers": True,
        "checkpoint_reused_variants": int(reused),
        "total_request_rows": int(total_rows),
        "final_whitebox_read_or_generated": False,
        "M1_parameters_changed": False,
        "M2_members_changed": False,
        "M2_weights_changed": False,
        "posthoc_member_selection": False,
        "M2_range_is_confidence_interval": False,
        "workers": int(max(1,args.workers)),
        "python_wall_seconds": float(time.perf_counter()-started),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    })
    print("SIGMA_REGIME_BLIND_PREDICTIONS_FROZEN_BEFORE_FINAL_WHITEBOX_PASS")
    print(f"prediction_manifest={manifest_path}")
    print(f"predictions={prediction_path}")
    print(f"checkpoint_reused_variants={reused}/{len(design)}")
    print(f"python_wall_seconds={time.perf_counter()-started:.3f}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Blind prediction over frozen G0/G1/G2 sigma-regime battery"
    )
    p.add_argument("--contract",type=Path,default=HERE/"config_phase4_sigma_regime_blind_prediction_v1.json")
    p.add_argument("--step0-manifest",type=Path,default=HERE/"results"/"sigma_regime_step0_calibration_v2"/"sigma_regime_v2_calibration_manifest.json")
    p.add_argument("--selected-regions",type=Path,default=HERE/"results"/"sigma_regime_step0_calibration_v2"/"sigma_regime_v2_selected_regions_frozen.csv")
    p.add_argument("--semantic-contract",type=Path,default=HERE/"config_phase4_m2_joint_ensemble_semantics_v1.json")
    p.add_argument("--b5-contract",type=Path,default=HERE/"config_phase4_m2_b5_joint_ensemble_graph_v1.json")
    p.add_argument("--a4-confirmation-manifest",type=Path,default=HERE/"results"/"m2_a4_portfolio_confirmation_v1"/"m2_a4_portfolio_confirmation_manifest_v1.json")
    p.add_argument("--a4-final-portfolio",type=Path,default=HERE/"results"/"m2_a4_portfolio_confirmation_v1"/"m2_a4_final_confirmed_portfolio.csv")
    p.add_argument("--a4-replay-results",type=Path,default=HERE/"results"/"m2_a4_portfolio_confirmation_v1"/"m2_a4_replay_results.csv")
    p.add_argument("--m1-confirmation-manifest",type=Path,default=HERE/"results"/"m2_a_confirmation_v1"/"m2_a_confirmation_manifest_v1.json")
    p.add_argument("--m1-anchor-candidates",type=Path,default=HERE/"results"/"m2_a_confirmation_v1"/"m2_a_confirmed_compatible_candidates.csv")
    p.add_argument("--m1-contract",type=Path,default=PHASE3/"config_phase3_m1_contract_v2.json")
    p.add_argument("--m0-contract",type=Path,default=PHASE3/"config_phase3_m0_contract_v1.json")
    p.add_argument("--i1-card-root",type=Path,default=PHASE2/"results"/"i1_cards_v2_rho_conditioned"/"public")
    p.add_argument("--i1-manifest",type=Path,default=PHASE2/"results"/"i1_cards_v2_rho_conditioned"/"public"/"i1_rho_conditioned_manifest_v1.json")
    p.add_argument("--output",type=Path,default=HERE/"results"/"sigma_regime_blind_prediction_v1")
    p.add_argument("--workers",type=int,default=1)
    p.add_argument("--prepare-only",action="store_true")
    args=p.parse_args()
    run(args)

if __name__=="__main__":
    main()
