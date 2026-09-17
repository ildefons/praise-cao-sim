"""Run M2-B2: graph diagnostic for independently discovered remote I1-compatible surrogates.

This stage is intentionally prediction-only. Candidate selection was completed
locally in M2-A2/A3. This script does not read graph white-box outcomes, does
not run Optuna, and does not use private provider traces.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
for module_directory in (PHASE2, PHASE3):
    if str(module_directory) not in sys.path:
        sys.path.insert(0, str(module_directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    PROVIDERS,
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from m1_graph_simulator_v2 import (  # noqa: E402
    GraphProviderSurrogate,
    execute_one_m1_graph_trajectory,
)
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
    build_public_induced_global_boundary,
)
from m2_b_one_at_a_time_graph import _request_summary, _surface_metrics  # noqa: E402

EXPECTED_STATUS = "PHASE4_M2_B2_REMOTE_GRAPH_DIAGNOSTIC_V1"
EXPECTED_M1_CONFIRM_STATUS = "PHASE4_M2_A_CONFIRMATION_PASS"
EXPECTED_REMOTE_CONFIRM_STATUS = "PHASE4_M2_A3_REMOTE_LHS_CONFIRMATION_COMPLETE_V1"
EXPECTED_M1_CONTRACT_STATUS = "IMPLEMENTATION_CANDIDATE_PHASE3_M1_LIFT_V2_NOT_FROZEN"
EXPECTED_M0_CONTRACT_STATUS = "FROZEN_PHASE3_M0_BASELINE_V2_SAME_RHO"
TOLERANCE = 1e-12


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(repository_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
        ).strip()
    except Exception:
        return None


def _surrogate(row: pd.Series) -> GraphProviderSurrogate:
    return GraphProviderSurrogate(
        mean_service_time=float(row["mean_service_time"]),
        cost_rate=float(row["cost_rate"]),
        service_cv=float(row["service_cv"]),
    )


def _load_candidates(
    *,
    contract: dict[str, Any],
    m1_manifest_path: Path,
    m1_candidates_path: Path,
    remote_manifest_path: Path,
    remote_candidates_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    m1_manifest = _read_json(m1_manifest_path)
    if m1_manifest.get("status") != EXPECTED_M1_CONFIRM_STATUS:
        raise RuntimeError("unexpected M2-A confirmation status")
    if bool(m1_manifest.get("graph_whitebox_read")):
        raise RuntimeError("M2-A input unexpectedly read graph white-box")

    remote_manifest = _read_json(remote_manifest_path)
    if remote_manifest.get("status") != EXPECTED_REMOTE_CONFIRM_STATUS:
        raise RuntimeError("unexpected M2-A3 remote confirmation status")
    if bool(remote_manifest.get("graph_whitebox_read")) or bool(remote_manifest.get("graph_simulation")):
        raise RuntimeError("M2-A3 input violates local-only provenance")

    m1 = pd.read_csv(m1_candidates_path)
    remote = pd.read_csv(remote_candidates_path)

    anchors = m1[
        (m1["selection_role"].astype(str) == "M1")
        & (m1["confirmation_compatible"].astype(bool))
    ].copy()
    if set(anchors["provider"].astype(str)) != set(PROVIDERS) or len(anchors) != len(PROVIDERS):
        raise RuntimeError("expected exactly one confirmed M1 anchor for every provider")

    required_remote = {
        "provider",
        "candidate_id",
        "selection_role",
        "mean_service_time",
        "cost_rate",
        "service_cv",
        "confirmation_mse",
        "confirmation_compatible",
    }
    missing = sorted(required_remote.difference(remote.columns))
    if missing:
        raise ValueError("remote candidate file missing fields: " + ", ".join(missing))
    remote = remote[remote["confirmation_compatible"].astype(bool)].copy()
    if remote.empty:
        raise RuntimeError("no confirmed remote candidates available")
    if remote["candidate_id"].duplicated().any():
        raise RuntimeError("duplicate remote candidate ids")

    expected = set(contract["variant_design"].get("expected_current_variants", []))
    actual = {"BASE_M1", *remote["candidate_id"].astype(str).tolist()}
    if expected and actual != expected:
        raise RuntimeError(
            f"confirmed remote candidate set changed: expected={sorted(expected)} actual={sorted(actual)}"
        )
    return anchors.reset_index(drop=True), remote.reset_index(drop=True)


def _build_variants(
    anchors: pd.DataFrame,
    remote: pd.DataFrame,
) -> tuple[dict[str, dict[str, GraphProviderSurrogate]], pd.DataFrame]:
    anchor_rows = {str(row.provider): row for row in anchors.itertuples(index=False)}
    base = {
        provider: GraphProviderSurrogate(
            mean_service_time=float(anchor_rows[provider].mean_service_time),
            cost_rate=float(anchor_rows[provider].cost_rate),
            service_cv=float(anchor_rows[provider].service_cv),
        )
        for provider in PROVIDERS
    }
    variants: dict[str, dict[str, GraphProviderSurrogate]] = {"BASE_M1": base}
    rows: list[dict[str, object]] = [
        {
            "variant_id": "BASE_M1",
            "changed_provider": "",
            "changed_candidate_id": "",
            "changed_selection_role": "M1",
            "confirmation_mse": np.nan,
            "distance_from_frozen_m1": 0.0,
            "nearest_existing_compatible_distance": 0.0,
        }
    ]

    order = remote.sort_values(["provider", "selection_role", "candidate_id"], kind="mergesort")
    for rec in order.itertuples(index=False):
        provider = str(rec.provider)
        variant_id = str(rec.candidate_id)
        surrogate_map = dict(base)
        surrogate_map[provider] = GraphProviderSurrogate(
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
        )
        variants[variant_id] = surrogate_map
        rows.append(
            {
                "variant_id": variant_id,
                "changed_provider": provider,
                "changed_candidate_id": variant_id,
                "changed_selection_role": str(rec.selection_role),
                "confirmation_mse": float(rec.confirmation_mse),
                "distance_from_frozen_m1": float(getattr(rec, "distance_from_frozen_m1", np.nan)),
                "nearest_existing_compatible_distance": float(
                    getattr(rec, "nearest_existing_compatible_distance", np.nan)
                ),
            }
        )
    return variants, pd.DataFrame(rows)


def run(
    *,
    contract_path: Path,
    m1_manifest_path: Path,
    m1_candidates_path: Path,
    remote_manifest_path: Path,
    remote_candidates_path: Path,
    m1_contract_path: Path,
    m0_contract_path: Path,
    i1_card_root: Path,
    i1_manifest_path: Path,
    output_directory: Path,
    smoke: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    contract = _read_json(contract_path)
    if contract.get("status") != EXPECTED_STATUS:
        raise RuntimeError("unexpected M2-B2 contract status")
    firewall = dict(contract["firewall"])
    if bool(firewall.get("graph_whitebox_may_be_read")) or bool(firewall.get("optuna_may_run")):
        raise RuntimeError("M2-B2 firewall is not closed")

    anchors, remote = _load_candidates(
        contract=contract,
        m1_manifest_path=m1_manifest_path,
        m1_candidates_path=m1_candidates_path,
        remote_manifest_path=remote_manifest_path,
        remote_candidates_path=remote_candidates_path,
    )
    variants, variant_design = _build_variants(anchors, remote)

    m1_contract = _read_json(m1_contract_path)
    m0_contract = _read_json(m0_contract_path)
    if m1_contract.get("status") != EXPECTED_M1_CONTRACT_STATUS:
        raise RuntimeError("unexpected M1-v2 contract status")
    if m0_contract.get("status") != EXPECTED_M0_CONTRACT_STATUS:
        raise RuntimeError("unexpected M0 contract status")

    metadata, _, _ = load_rho_conditioned_i1_cards(i1_card_root, i1_manifest_path)
    rho_support = common_same_rho_support(metadata)
    horizons = common_horizon_support(metadata)
    workload = _common_workload_contract(metadata)
    graph_spec = dict(m0_contract["phase1_benchmark_adapter"])
    canonical_ipt = float(m1_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(m1_contract["pilot_scope"]["execution_fraction"])

    graph_cfg = dict(contract["graph_simulation"])
    seeds = tuple(
        range(
            int(graph_cfg["trajectory_seed_start"]),
            int(graph_cfg["trajectory_seed_end_inclusive"]) + 1,
        )
    )
    if len(seeds) != int(graph_cfg["n_trajectories_per_variant"]):
        raise RuntimeError("declared graph seed bank length mismatch")
    if smoke:
        seeds = seeds[: int(graph_cfg["smoke_n_trajectories_per_variant"])]

    output_directory.mkdir(parents=True, exist_ok=True)
    ledger_directory = output_directory / "ledgers"
    ledger_directory.mkdir(parents=True, exist_ok=True)
    variant_design.to_csv(output_directory / "m2_b2_variant_design.csv", index=False)
    pd.concat([anchors.assign(candidate_source="M1_anchor"), remote.assign(candidate_source="remote")], ignore_index=True, sort=False).to_csv(
        output_directory / "m2_b2_frozen_candidate_set.csv", index=False
    )

    curves_by_variant: dict[str, pd.DataFrame] = {}
    request_rows: list[dict[str, object]] = []
    total_request_rows = 0

    for variant_index, (variant_id, surrogates) in enumerate(variants.items(), start=1):
        print(
            f"M2-B2 variant {variant_index}/{len(variants)} {variant_id} trajectories={len(seeds)}",
            flush=True,
        )
        ledgers: list[pd.DataFrame] = []
        for trajectory_index, seed in enumerate(seeds):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                ledger = execute_one_m1_graph_trajectory(
                    provider_surrogates=surrogates,
                    graph_spec=graph_spec,
                    workload_period=float(workload["period"]),
                    stop_time=float(workload["horizon_max"]),
                    trajectory_seed=int(seed),
                    canonical_ipt=canonical_ipt,
                    execution_fraction=execution_fraction,
                )
            ledger.insert(0, "trajectory", int(trajectory_index))
            ledger.insert(1, "trajectory_seed", int(seed))
            ledgers.append(ledger)
            if trajectory_index == 0 or (trajectory_index + 1) % 25 == 0 or trajectory_index + 1 == len(seeds):
                print(f"  {variant_id}: {trajectory_index + 1}/{len(seeds)}", flush=True)

        combined = pd.concat(ledgers, ignore_index=True)
        if int(combined["trajectory"].nunique()) != len(seeds):
            raise RuntimeError(f"{variant_id}: trajectory count mismatch")
        if combined[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"{variant_id}: duplicate trajectory/request rows")
        combined.insert(0, "variant_id", variant_id)
        combined.to_csv(ledger_directory / f"{variant_id}.csv", index=False)
        total_request_rows += len(combined)
        request_rows.append(_request_summary(variant_id, combined))

        per_variant: list[pd.DataFrame] = []
        for rho in rho_support:
            provider_boundaries = provider_boundaries_at_region_rho(metadata, float(rho))
            induced = build_public_induced_global_boundary(provider_boundaries, m0_contract)
            curve = build_empirical_graph_sigma_curve(
                combined,
                boundary=induced,
                rho_global=float(rho),
                horizons=horizons,
                stop_time=float(workload["horizon_max"]),
                accounting_origin=float(workload["accounting_origin"]),
                output_column="sigma",
            )
            curve.insert(0, "rho_global", float(rho))
            curve.insert(0, "variant_id", variant_id)
            curve["A_G_l_max"] = float(induced.l_max)
            curve["A_G_c_max"] = float(induced.c_max)
            curve["A_G_q_min"] = float(induced.q_min)
            per_variant.append(curve)
        curves_by_variant[variant_id] = pd.concat(per_variant, ignore_index=True)

    all_curves = pd.concat(curves_by_variant.values(), ignore_index=True).sort_values(
        ["variant_id", "rho_global", "horizon"]
    ).reset_index(drop=True)
    all_curves.to_csv(output_directory / "m2_b2_graph_sigma_curves.csv", index=False)

    base = curves_by_variant["BASE_M1"]
    surface_rows: list[dict[str, object]] = []
    per_rho_rows: list[dict[str, object]] = []
    delta_frames: list[pd.DataFrame] = []

    for variant_id, curves in curves_by_variant.items():
        summary, merged = _surface_metrics(curves, base)
        surface_rows.append({"variant_id": variant_id, **summary})
        # _surface_metrics preserves variant_id from curves; do not insert it again.
        delta_frames.append(merged)
        for rho in rho_support:
            variant_rho = curves[np.isclose(curves["rho_global"].astype(float), float(rho), atol=TOLERANCE, rtol=0.0)].copy()
            base_rho = base[np.isclose(base["rho_global"].astype(float), float(rho), atol=TOLERANCE, rtol=0.0)].copy()
            rho_summary, _ = _surface_metrics(variant_rho, base_rho)
            per_rho_rows.append({"variant_id": variant_id, "rho_global": float(rho), **rho_summary})

    surface_summary = pd.DataFrame(surface_rows).merge(
        variant_design, on="variant_id", how="left", validate="one_to_one"
    )
    surface_summary = surface_summary[
        [
            "variant_id",
            "changed_provider",
            "changed_candidate_id",
            "changed_selection_role",
            "confirmation_mse",
            "distance_from_frozen_m1",
            "nearest_existing_compatible_distance",
            "mae_vs_base",
            "rmse_vs_base",
            "mean_delta_vs_base",
            "max_abs_delta_vs_base",
        ]
    ].sort_values(["mae_vs_base", "variant_id"], ascending=[False, True])
    surface_summary.to_csv(output_directory / "m2_b2_surface_spread_summary.csv", index=False)

    pd.DataFrame(per_rho_rows).merge(
        variant_design, on="variant_id", how="left", validate="many_to_one"
    ).to_csv(output_directory / "m2_b2_per_rho_spread_summary.csv", index=False)
    pd.concat(delta_frames, ignore_index=True).to_csv(
        output_directory / "m2_b2_graph_sigma_deltas_vs_base.csv", index=False
    )
    request_summary = pd.DataFrame(request_rows).merge(
        variant_design, on="variant_id", how="left", validate="one_to_one"
    )
    request_summary.to_csv(output_directory / "m2_b2_request_distribution_summary.csv", index=False)

    elapsed = time.perf_counter() - started
    manifest = {
        "status": "PHASE4_M2_B2_REMOTE_GRAPH_DIAGNOSTIC_COMPLETE_V1",
        "smoke_mode": bool(smoke),
        "graph_whitebox_read": False,
        "graph_prediction_used_for_candidate_selection": False,
        "optuna_rerun": False,
        "private_phase2_provider_traces_read": False,
        "candidate_set_frozen_before_graph": True,
        "n_variants": int(len(variants)),
        "variant_ids": list(variants),
        "n_trajectories_per_variant": int(len(seeds)),
        "graph_trajectory_seed_start": int(seeds[0]),
        "graph_trajectory_seed_end_inclusive": int(seeds[-1]),
        "common_random_numbers_across_variants": True,
        "total_graph_trajectories": int(len(variants) * len(seeds)),
        "total_request_rows": int(total_request_rows),
        "contract_sha256": _sha256(contract_path),
        "m1_confirmation_manifest_sha256": _sha256(m1_manifest_path),
        "m1_anchor_candidates_sha256": _sha256(m1_candidates_path),
        "remote_confirmation_manifest_sha256": _sha256(remote_manifest_path),
        "remote_candidates_sha256": _sha256(remote_candidates_path),
        "m1_contract_sha256": _sha256(m1_contract_path),
        "m0_contract_sha256": _sha256(m0_contract_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "python_wall_seconds": float(elapsed),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "variant_design": "m2_b2_variant_design.csv",
            "frozen_candidate_set": "m2_b2_frozen_candidate_set.csv",
            "graph_sigma_curves": "m2_b2_graph_sigma_curves.csv",
            "surface_spread_summary": "m2_b2_surface_spread_summary.csv",
            "per_rho_spread_summary": "m2_b2_per_rho_spread_summary.csv",
            "graph_sigma_deltas": "m2_b2_graph_sigma_deltas_vs_base.csv",
            "request_distribution_summary": "m2_b2_request_distribution_summary.csv",
            "ledgers": "ledgers/<variant_id>.csv"
        },
        "next_gate": contract["next_gate"],
    }
    _write_json(output_directory / "m2_b2_graph_diagnostic_manifest_v1.json", manifest)

    print("M2_B2_REMOTE_GRAPH_PREDICTIONS_MATERIALIZED_WITHOUT_WHITEBOX_PASS")
    print("\nWHOLE_SURFACE_SPREAD_VS_BASE_M1")
    print(surface_summary.to_string(index=False))
    print("\nREQUEST_DISTRIBUTION_SUMMARY")
    print(request_summary.to_string(index=False))
    print("M2_B2_REMOTE_GRAPH_DIAGNOSTIC_COMPLETE")
    print(f"output={output_directory.resolve()}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M2-B2 remote-compatible graph diagnostic")
    parser.add_argument("--contract", type=Path, default=HERE / "config_phase4_m2_b2_remote_graph_v1.json")
    parser.add_argument("--m1-confirmation-manifest", type=Path, default=HERE / "results" / "m2_a_confirmation_v1" / "m2_a_confirmation_manifest_v1.json")
    parser.add_argument("--m1-anchor-candidates", type=Path, default=HERE / "results" / "m2_a_confirmation_v1" / "m2_a_confirmed_compatible_candidates.csv")
    parser.add_argument("--remote-confirmation-manifest", type=Path, default=HERE / "results" / "m2_a3_remote_confirmation_v1" / "m2_a3_remote_confirmation_manifest_v1.json")
    parser.add_argument("--remote-candidates", type=Path, default=HERE / "results" / "m2_a3_remote_confirmation_v1" / "m2_a3_confirmed_remote_candidates.csv")
    parser.add_argument("--m1-contract", type=Path, default=PHASE3 / "config_phase3_m1_contract_v2.json")
    parser.add_argument("--m0-contract", type=Path, default=PHASE3 / "config_phase3_m0_contract_v1.json")
    parser.add_argument("--i1-card-root", type=Path, default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public")
    parser.add_argument("--i1-manifest", type=Path, default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public" / "i1_rho_conditioned_manifest_v1.json")
    parser.add_argument("--output", type=Path, default=HERE / "results" / "m2_b2_remote_graph_v1")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    run(
        contract_path=args.contract.resolve(),
        m1_manifest_path=args.m1_confirmation_manifest.resolve(),
        m1_candidates_path=args.m1_anchor_candidates.resolve(),
        remote_manifest_path=args.remote_confirmation_manifest.resolve(),
        remote_candidates_path=args.remote_candidates.resolve(),
        m1_contract_path=args.m1_contract.resolve(),
        m0_contract_path=args.m0_contract.resolve(),
        i1_card_root=args.i1_card_root.resolve(),
        i1_manifest_path=args.i1_manifest.resolve(),
        output_directory=args.output.resolve(),
        smoke=bool(args.smoke),
    )


if __name__ == "__main__":
    main()
