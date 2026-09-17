"""Run the Phase-4 M2-B one-at-a-time graph identifiability diagnostic.

This stage consumes only the frozen M2-A public-I1-compatible candidate set and
public graph/I1 contracts. It does not read graph white-box outcomes, rerun
Optuna, or use private provider traces.

The design is deliberately controlled:
  * BASE_M1 uses the frozen M1 anchor candidate for every provider.
  * Each alternative variant changes exactly one provider to one confirmed
    non-M1 candidate.
  * All variants use the same graph trajectory seed bank (common random numbers).
  * Graph sigma spread is reported relative to BASE_M1 without a post-hoc
    binary materiality threshold.
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

EXPECTED_STATUS = "PHASE4_M2_B_ONE_AT_A_TIME_GRAPH_DIAGNOSTIC_V1"
EXPECTED_CONFIRMATION_STATUS = "PHASE4_M2_A_CONFIRMATION_PASS"
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


def _validate_confirmation_inputs(
    *,
    contract: dict[str, Any],
    confirmation_manifest_path: Path,
    candidates_path: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    manifest = _read_json(confirmation_manifest_path)
    if manifest.get("status") != EXPECTED_CONFIRMATION_STATUS:
        raise ValueError("unexpected M2-A confirmation manifest status")
    for forbidden_flag in (
        "graph_simulation_read_or_run",
        "graph_prediction_read",
        "graph_whitebox_read",
        "reran_optuna",
        "private_phase2_provider_traces_read",
    ):
        if bool(manifest.get(forbidden_flag)):
            raise RuntimeError(f"M2-A confirmation violates firewall: {forbidden_flag}")

    frame = pd.read_csv(candidates_path)
    required = {
        "provider",
        "candidate_id",
        "selection_role",
        "mean_service_time",
        "cost_rate",
        "service_cv",
        "confirmation_mse",
        "confirmation_compatible",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"confirmed candidate file lacks fields: {missing}")

    frame = frame[frame["confirmation_compatible"].astype(bool)].copy()
    if set(frame["provider"]) != set(PROVIDERS):
        raise RuntimeError("confirmed candidate set must contain ProviderA/B/C")

    source_cfg = dict(contract["candidate_source"])
    minimum = int(source_cfg["minimum_candidates_per_provider"])
    counts = frame.groupby("provider").size().to_dict()
    for provider in PROVIDERS:
        if int(counts.get(provider, 0)) < minimum:
            raise RuntimeError(
                f"{provider} has {counts.get(provider, 0)} confirmed candidates, "
                f"need at least {minimum}"
            )
        anchors = frame[
            (frame["provider"] == provider)
            & (frame["selection_role"].astype(str) == "M1")
        ]
        if bool(source_cfg["require_exactly_one_m1_anchor_per_provider"]) and len(anchors) != 1:
            raise RuntimeError(f"{provider} must have exactly one M1 anchor")

    if frame["candidate_id"].duplicated().any():
        raise RuntimeError("confirmed candidate ids are not unique")
    return manifest, frame.reset_index(drop=True)


def _surrogate_from_row(row: pd.Series) -> GraphProviderSurrogate:
    return GraphProviderSurrogate(
        mean_service_time=float(row["mean_service_time"]),
        cost_rate=float(row["cost_rate"]),
        service_cv=float(row["service_cv"]),
    )


def _build_variants(candidates: pd.DataFrame) -> tuple[dict[str, dict[str, GraphProviderSurrogate]], pd.DataFrame]:
    anchors: dict[str, pd.Series] = {}
    for provider in PROVIDERS:
        anchor = candidates[
            (candidates["provider"] == provider)
            & (candidates["selection_role"].astype(str) == "M1")
        ]
        if len(anchor) != 1:
            raise RuntimeError(f"{provider}: expected exactly one M1 anchor")
        anchors[provider] = anchor.iloc[0]

    variants: dict[str, dict[str, GraphProviderSurrogate]] = {}
    variant_rows: list[dict[str, object]] = []

    base_surrogates = {
        provider: _surrogate_from_row(anchors[provider]) for provider in PROVIDERS
    }
    variants["BASE_M1"] = base_surrogates
    variant_rows.append(
        {
            "variant_id": "BASE_M1",
            "changed_provider": "",
            "changed_candidate_id": "",
            "changed_selection_role": "M1",
        }
    )

    for provider in PROVIDERS:
        alternatives = candidates[
            (candidates["provider"] == provider)
            & (candidates["selection_role"].astype(str) != "M1")
        ].copy()
        alternatives = alternatives.sort_values(
            ["selection_role", "confirmation_mse", "candidate_id"]
        )
        for alt in alternatives.itertuples(index=False):
            role = str(alt.selection_role)
            variant_id = f"{provider}_{role}"
            if variant_id in variants:
                raise RuntimeError(f"duplicate graph variant id: {variant_id}")
            surrogate_map = dict(base_surrogates)
            surrogate_map[provider] = GraphProviderSurrogate(
                mean_service_time=float(alt.mean_service_time),
                cost_rate=float(alt.cost_rate),
                service_cv=float(alt.service_cv),
            )
            variants[variant_id] = surrogate_map
            variant_rows.append(
                {
                    "variant_id": variant_id,
                    "changed_provider": provider,
                    "changed_candidate_id": str(alt.candidate_id),
                    "changed_selection_role": role,
                }
            )

    if len(variants) < 4:
        raise RuntimeError("one-at-a-time diagnostic produced too few variants")
    return variants, pd.DataFrame(variant_rows)


def _request_summary(variant_id: str, ledgers: pd.DataFrame) -> dict[str, object]:
    completed = ledgers[ledgers["completed_by_stop"].astype(bool)].copy()
    total = len(ledgers)
    n_completed = len(completed)

    row: dict[str, object] = {
        "variant_id": variant_id,
        "n_request_rows": int(total),
        "n_completed": int(n_completed),
        "completed_fraction": float(n_completed / total) if total else np.nan,
    }

    def add_distribution(prefix: str, column: str) -> None:
        values = completed[column].dropna().astype(float).to_numpy()
        if len(values) == 0:
            for name in ("mean", "median", "p90", "p99", "p999"):
                row[f"{prefix}_{name}"] = np.nan
            return
        row[f"{prefix}_mean"] = float(np.mean(values))
        row[f"{prefix}_median"] = float(np.median(values))
        row[f"{prefix}_p90"] = float(np.quantile(values, 0.90))
        row[f"{prefix}_p99"] = float(np.quantile(values, 0.99))
        row[f"{prefix}_p999"] = float(np.quantile(values, 0.999))

    add_distribution("latency", "L")
    add_distribution("cost", "C")
    q_values = completed["Q"].dropna().astype(float).to_numpy()
    row["quality_mean"] = float(np.mean(q_values)) if len(q_values) else np.nan
    return row


def _surface_metrics(
    variant_curves: pd.DataFrame,
    base_curves: pd.DataFrame,
) -> tuple[dict[str, float], pd.DataFrame]:
    keys = ["rho_global", "horizon"]
    merged = variant_curves.merge(
        base_curves[keys + ["sigma"]].rename(columns={"sigma": "sigma_base"}),
        on=keys,
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(base_curves) or len(merged) != len(variant_curves):
        raise RuntimeError("variant/base graph sigma surfaces do not align")
    delta = merged["sigma"].astype(float) - merged["sigma_base"].astype(float)
    merged["delta_vs_base"] = delta
    summary = {
        "mae_vs_base": float(np.mean(np.abs(delta))),
        "rmse_vs_base": float(np.sqrt(np.mean(np.square(delta)))),
        "mean_delta_vs_base": float(np.mean(delta)),
        "max_abs_delta_vs_base": float(np.max(np.abs(delta))),
    }
    return summary, merged


def run_diagnostic(
    *,
    contract_path: Path,
    confirmation_manifest_path: Path,
    candidates_path: Path,
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
        raise ValueError("unexpected M2-B contract status")
    firewall = dict(contract["firewall"])
    if bool(firewall["graph_whitebox_may_be_read"]):
        raise RuntimeError("M2-B contract unexpectedly allows graph WB")
    if bool(firewall["optuna_may_run"]):
        raise RuntimeError("M2-B contract unexpectedly allows Optuna")

    confirmation_manifest, candidates = _validate_confirmation_inputs(
        contract=contract,
        confirmation_manifest_path=confirmation_manifest_path,
        candidates_path=candidates_path,
    )
    variants, variant_design = _build_variants(candidates)

    m1_contract = _read_json(m1_contract_path)
    m0_contract = _read_json(m0_contract_path)
    if m1_contract.get("status") != EXPECTED_M1_CONTRACT_STATUS:
        raise ValueError("unexpected M1-v2 contract status")
    if m0_contract.get("status") != EXPECTED_M0_CONTRACT_STATUS:
        raise ValueError("unexpected frozen M0 contract status")

    metadata, _, _ = load_rho_conditioned_i1_cards(i1_card_root, i1_manifest_path)
    rho_support = common_same_rho_support(metadata)
    horizons = common_horizon_support(metadata)
    workload = _common_workload_contract(metadata)
    graph_spec = dict(m0_contract["phase1_benchmark_adapter"])
    canonical_ipt = float(m1_contract["fixed_closure_conventions"]["canonical_IPT"])
    execution_fraction = float(m1_contract["pilot_scope"]["execution_fraction"])

    graph_cfg = dict(contract["graph_simulation"])
    seed_start = int(graph_cfg["trajectory_seed_start"])
    seed_end = int(graph_cfg["trajectory_seed_end_inclusive"])
    seeds = tuple(range(seed_start, seed_end + 1))
    if len(seeds) != int(graph_cfg["n_trajectories_per_variant"]):
        raise ValueError("M2-B graph seed range does not match declared trajectory count")
    if smoke:
        seeds = seeds[: int(graph_cfg["smoke_n_trajectories_per_variant"])]

    output_directory.mkdir(parents=True, exist_ok=True)
    ledger_directory = output_directory / "ledgers"
    ledger_directory.mkdir(parents=True, exist_ok=True)
    variant_design.to_csv(output_directory / "m2_b_variant_design.csv", index=False)
    candidates.to_csv(output_directory / "m2_b_frozen_candidate_set.csv", index=False)

    curves_by_variant: dict[str, pd.DataFrame] = {}
    request_summaries: list[dict[str, object]] = []
    total_request_rows = 0

    for variant_index, (variant_id, surrogates) in enumerate(variants.items(), start=1):
        print(
            f"M2-B variant {variant_index}/{len(variants)} {variant_id} "
            f"trajectories={len(seeds)}",
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
            if (
                trajectory_index == 0
                or (trajectory_index + 1) % 25 == 0
                or trajectory_index + 1 == len(seeds)
            ):
                print(
                    f"  {variant_id}: {trajectory_index + 1}/{len(seeds)}",
                    flush=True,
                )

        combined = pd.concat(ledgers, ignore_index=True)
        if int(combined["trajectory"].nunique()) != len(seeds):
            raise RuntimeError(f"{variant_id}: graph ledger lost trajectories")
        if combined[["trajectory", "request_id"]].duplicated().any():
            raise RuntimeError(f"{variant_id}: duplicate trajectory/request ids")
        combined.insert(0, "variant_id", variant_id)
        combined.to_csv(ledger_directory / f"{variant_id}.csv", index=False)
        total_request_rows += len(combined)
        request_summaries.append(_request_summary(variant_id, combined))

        curve_rows: list[pd.DataFrame] = []
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
            curve_rows.append(curve)
        curves_by_variant[variant_id] = pd.concat(curve_rows, ignore_index=True)

    all_curves = pd.concat(curves_by_variant.values(), ignore_index=True).sort_values(
        ["variant_id", "rho_global", "horizon"]
    ).reset_index(drop=True)
    all_curves.to_csv(output_directory / "m2_b_graph_sigma_curves.csv", index=False)

    base = curves_by_variant["BASE_M1"]
    surface_rows: list[dict[str, object]] = []
    per_rho_rows: list[dict[str, object]] = []
    delta_frames: list[pd.DataFrame] = []

    for variant_id, curves in curves_by_variant.items():
        summary, merged = _surface_metrics(curves, base)
        surface_rows.append({"variant_id": variant_id, **summary})
        merged.insert(0, "variant_id", variant_id)
        delta_frames.append(merged)

        for rho in rho_support:
            variant_rho = curves[
                np.isclose(
                    curves["rho_global"].astype(float),
                    float(rho),
                    atol=TOLERANCE,
                    rtol=0.0,
                )
            ].copy()
            base_rho = base[
                np.isclose(
                    base["rho_global"].astype(float),
                    float(rho),
                    atol=TOLERANCE,
                    rtol=0.0,
                )
            ].copy()
            rho_summary, _ = _surface_metrics(variant_rho, base_rho)
            per_rho_rows.append(
                {"variant_id": variant_id, "rho_global": float(rho), **rho_summary}
            )

    surface_summary = pd.DataFrame(surface_rows).merge(
        variant_design, on="variant_id", how="left", validate="one_to_one"
    )
    surface_summary = surface_summary[
        [
            "variant_id",
            "changed_provider",
            "changed_candidate_id",
            "changed_selection_role",
            "mae_vs_base",
            "rmse_vs_base",
            "mean_delta_vs_base",
            "max_abs_delta_vs_base",
        ]
    ].sort_values(["mae_vs_base", "variant_id"], ascending=[False, True])
    surface_summary.to_csv(
        output_directory / "m2_b_surface_spread_summary.csv", index=False
    )

    pd.DataFrame(per_rho_rows).merge(
        variant_design, on="variant_id", how="left", validate="many_to_one"
    ).to_csv(output_directory / "m2_b_per_rho_spread_summary.csv", index=False)

    pd.concat(delta_frames, ignore_index=True).to_csv(
        output_directory / "m2_b_graph_sigma_deltas_vs_base.csv", index=False
    )

    request_summary = pd.DataFrame(request_summaries).merge(
        variant_design, on="variant_id", how="left", validate="one_to_one"
    )
    request_summary.to_csv(
        output_directory / "m2_b_request_distribution_summary.csv", index=False
    )

    elapsed = time.perf_counter() - started
    manifest = {
        "status": "PHASE4_M2_B_ONE_AT_A_TIME_GRAPH_DIAGNOSTIC_COMPLETE_V1",
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
        "confirmation_manifest_sha256": _sha256(confirmation_manifest_path),
        "confirmed_candidate_file_sha256": _sha256(candidates_path),
        "m1_contract_sha256": _sha256(m1_contract_path),
        "m0_contract_sha256": _sha256(m0_contract_path),
        "public_i1_manifest_sha256": _sha256(i1_manifest_path),
        "python_wall_seconds": float(elapsed),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
        "outputs": {
            "variant_design": "m2_b_variant_design.csv",
            "frozen_candidate_set": "m2_b_frozen_candidate_set.csv",
            "graph_sigma_curves": "m2_b_graph_sigma_curves.csv",
            "surface_spread_summary": "m2_b_surface_spread_summary.csv",
            "per_rho_spread_summary": "m2_b_per_rho_spread_summary.csv",
            "graph_sigma_deltas": "m2_b_graph_sigma_deltas_vs_base.csv",
            "request_distribution_summary": "m2_b_request_distribution_summary.csv",
            "ledgers": "ledgers/<variant_id>.csv"
        },
        "next_gate": (
            "Interpret the predeclared graph-spread metrics. If locally compatible "
            "one-at-a-time substitutions materially change graph sigma, proceed to "
            "an ambiguity-preserving M2 ensemble/factorial design. If they do not, "
            "test current latent-family insufficiency before enlarging the ensemble."
        )
    }
    _write_json(output_directory / "m2_b_graph_diagnostic_manifest_v1.json", manifest)

    print("M2_B_GRAPH_PREDICTIONS_MATERIALIZED_WITHOUT_WHITEBOX_PASS", flush=True)
    print("\nWHOLE_SURFACE_SPREAD_VS_BASE_M1")
    print(surface_summary.to_string(index=False))
    print("\nREQUEST_DISTRIBUTION_SUMMARY")
    print(request_summary.to_string(index=False))
    print("M2_B_ONE_AT_A_TIME_GRAPH_DIAGNOSTIC_COMPLETE")
    print(f"output={output_directory.resolve()}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase-4 M2-B one-at-a-time graph ambiguity diagnostic"
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase4_m2_b_one_at_a_time_graph_v1.json"
    )
    parser.add_argument(
        "--confirmation-manifest",
        type=Path,
        default=HERE / "results" / "m2_a_confirmation_v1" / "m2_a_confirmation_manifest_v1.json"
    )
    parser.add_argument(
        "--confirmed-candidates",
        type=Path,
        default=HERE / "results" / "m2_a_confirmation_v1" / "m2_a_confirmed_compatible_candidates.csv"
    )
    parser.add_argument(
        "--m1-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m1_contract_v2.json"
    )
    parser.add_argument(
        "--m0-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m0_contract_v1.json"
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public"
    )
    parser.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public"
        / "i1_rho_conditioned_manifest_v1.json"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m2_b_one_at_a_time_graph_v1"
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="run only the first five graph trajectories per variant"
    )
    args = parser.parse_args()

    run_diagnostic(
        contract_path=args.contract.resolve(),
        confirmation_manifest_path=args.confirmation_manifest.resolve(),
        candidates_path=args.confirmed_candidates.resolve(),
        m1_contract_path=args.m1_contract.resolve(),
        m0_contract_path=args.m0_contract.resolve(),
        i1_card_root=args.i1_card_root.resolve(),
        i1_manifest_path=args.i1_manifest.resolve(),
        output_directory=args.output.resolve(),
        smoke=bool(args.smoke)
    )


if __name__ == "__main__":
    main()
