"""DD-3: graph-response due diligence for frozen M0/M1/M2.

Question
--------
Do the frozen integration methods capture the effect of changing only the
public graph from G0 to G1 when the hidden provider process is held fixed?

Design
------
* G0 hidden providers: final Phase-1 v2 D300/d0.20 WB, seeds 7000..7099.
* G1 hidden providers: the same D300/d0.20 process, same seeds 7000..7099,
  same provider gamma streams, changed public graph only.
* Frozen M0/M1/M2 predictions are not changed or retuned.
* The primary diagnostic is the graph response

      Delta sigma = sigma(G1) - sigma(G0)

  and response error

      e_M = Delta sigma_M - Delta sigma_WB.

Stages
------
1. --prepare-only
   Zero simulation. Validate graph/provenance contracts and structural facts.
2. --generate-paired-wb
   Generate only the paired G1 D300 WB on the exact G0 seed bank.
3. --evaluate
   Compare paired WB graph response with frozen M0/M1/M2 graph response and
   write absolute-sigma and Delta-sigma plots.

This is due-diligence evidence, not a new method-selection stage.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE1 = FIRST_SCIENCE / "phase1"
PHASE2 = FIRST_SCIENCE / "phase2"
PHASE3 = FIRST_SCIENCE / "phase3"
for directory in (PHASE1, PHASE2, PHASE3):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from diagnose_rho_conditioned_i1_m0 import (  # noqa: E402
    common_horizon_support,
    common_same_rho_support,
    load_rho_conditioned_i1_cards,
    provider_boundaries_at_region_rho,
)
from run_m1_graph_prediction_v2 import (  # noqa: E402
    _common_workload_contract,
    build_empirical_graph_sigma_curve,
    build_public_induced_global_boundary,
)
from m2_b2_remote_graph import _git_head, _read_json, _sha256, _write_json  # noqa: E402
from m2_b6_joint_ensemble_whitebox import _snap_frame_to_frozen_grid  # noqa: E402
from m2_g1_graph_simulator import execute_one_g1_prediction_trajectory  # noqa: E402
from m2_g1_public_adapter import (  # noqa: E402
    build_g1_induced_global_boundary,
    build_g1_public_graph_spec,
    validate_g1_public_graph_spec,
)
from m2_g1_whitebox_validation import _validate_hidden_model  # noqa: E402

TOL = 1e-12
EXPECTED_CONTRACT_STATUS = "FROZEN_PHASE4_DD3_GRAPH_RESPONSE_AUDIT_V1"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
EXPECTED_G0_SETTING = "D300000000_d0.200"
EXPECTED_G0_SEEDS = tuple(range(7000, 7100))


def _load_public_context(
    i1_root: Path,
    i1_manifest: Path,
) -> tuple[
    dict[str, dict[str, object]],
    list[float],
    list[float],
    dict[str, float],
]:
    metadata, _, _ = load_rho_conditioned_i1_cards(i1_root, i1_manifest)
    rhos = [float(v) for v in common_same_rho_support(metadata)]
    horizons = [float(v) for v in common_horizon_support(metadata)]
    workload = _common_workload_contract(metadata)
    return metadata, rhos, horizons, workload


def _paired_seed_bank(protocol_path: Path) -> tuple[int, ...]:
    protocol = _read_json(protocol_path)
    if str(protocol.get("physical_setting_id")) != EXPECTED_G0_SETTING:
        raise RuntimeError("final Phase-1 v2 protocol is not D300/d0.20")
    seeds = tuple(int(v) for v in protocol["seed_bank"])
    if seeds != EXPECTED_G0_SEEDS:
        raise RuntimeError(
            "DD-3 requires the exact final G0 seed bank 7000..7099"
        )
    return seeds


def _validate_graph_intervention(
    *,
    metadata: dict[str, dict[str, object]],
    rhos: list[float],
    m0_contract_path: Path,
) -> pd.DataFrame:
    m0_contract = _read_json(m0_contract_path)
    g0 = dict(m0_contract["phase1_benchmark_adapter"])
    g1 = build_g1_public_graph_spec()
    validate_g1_public_graph_spec(g1)

    if str(g0["graph"]) != str(g1["graph"]):
        raise RuntimeError("G0/G1 logical graph grammar differs unexpectedly")

    g0_net = dict(g0["network_model"])
    g1_net = dict(g1["network_model"])
    for key0, key1 in (
        ("request_bytes", "request_bytes"),
        ("branch_bytes", "branch_bytes"),
        ("join_bytes", "join_bytes"),
        ("BW_mbps", "BW_mbps"),
    ):
        if float(g0_net[key0]) != float(g1_net[key1]):
            raise RuntimeError(f"G0/G1 network field differs unexpectedly: {key0}")

    # G1 must preserve the root and join propagation terms; only provider
    # branch propagation delays are allowed to change.
    g0_pr = float(g0_net["PR"])
    g1_pr = dict(g1_net["PR_seconds"])
    if abs(float(g1_pr["Source_to_Fpre"]) - g0_pr) > TOL:
        raise RuntimeError("G1 changed Source->Fpre propagation unexpectedly")
    if abs(float(g1_pr["Fpre_to_Fpost_join"]) - g0_pr) > TOL:
        raise RuntimeError("G1 changed join propagation unexpectedly")
    expected_provider_pr = {
        "Fpre_to_ProviderA": 0.005,
        "Fpre_to_ProviderB": 0.015,
        "Fpre_to_ProviderC": 0.001,
    }
    for key, expected in expected_provider_pr.items():
        if abs(float(g1_pr[key]) - expected) > TOL:
            raise RuntimeError(f"unexpected G1 provider-branch propagation for {key}")

    g0_fixed = dict(g0["fixed_service_model"])
    g1_fixed = dict(g1["fixed_service_model"])
    for key in (
        "Fpre_instructions",
        "Fpost_instructions",
        "effective_IPT",
        "COST_rate",
    ):
        if float(g0_fixed[key]) != float(g1_fixed[key]):
            raise RuntimeError(f"G0/G1 fixed service field differs: {key}")

    rows: list[dict[str, float]] = []
    for rho in rhos:
        local = provider_boundaries_at_region_rho(metadata, float(rho))
        b0 = build_public_induced_global_boundary(local, m0_contract)
        b1 = build_g1_induced_global_boundary(local)
        rows.append(
            {
                "rho_global": float(rho),
                "G0_A_G_l_max": float(b0.l_max),
                "G1_A_G_l_max": float(b1.l_max),
                "delta_A_G_l_max": float(b1.l_max - b0.l_max),
                "G0_A_G_c_max": float(b0.c_max),
                "G1_A_G_c_max": float(b1.c_max),
                "delta_A_G_c_max": float(b1.c_max - b0.c_max),
                "G0_A_G_q_min": float(b0.q_min),
                "G1_A_G_q_min": float(b1.q_min),
                "delta_A_G_q_min": float(b1.q_min - b0.q_min),
            }
        )
    return pd.DataFrame(rows)


def _validate_hidden_provider_provenance(args: argparse.Namespace) -> dict[str, Any]:
    contract = _read_json(args.g1_wb_contract.resolve())
    _, _, hidden = _validate_hidden_model(
        contract=contract,
        phase1_config_path=args.phase1_config.resolve(),
        phase1_confirmation_protocol_path=args.phase1_confirmation_protocol.resolve(),
        phase1_confirmation_freeze_path=args.phase1_confirmation_freeze.resolve(),
        i1_region_acquisition_path=args.i1_region_acquisition.resolve(),
        i1_sigma_acquisition_path=args.i1_sigma_acquisition.resolve(),
    )
    if str(hidden["case_id"]) != EXPECTED_G0_SETTING:
        raise RuntimeError("paired graph-response WB must use D300/d0.20")
    if not bool(hidden["matched_i1_provider_process"]):
        raise RuntimeError("G1 hidden provider process is not matched to I1")
    return hidden


def _load_audit_contract(path: Path) -> dict[str, Any]:
    contract = _read_json(path)
    if contract.get("status") != EXPECTED_CONTRACT_STATUS:
        raise RuntimeError("unexpected DD-3 graph-response audit contract status")
    paired = dict(contract["paired_whitebox"])
    if int(paired["G0_seed_start"]) != EXPECTED_G0_SEEDS[0]:
        raise RuntimeError("DD-3 contract G0 seed start changed")
    if int(paired["G0_seed_end_inclusive"]) != EXPECTED_G0_SEEDS[-1]:
        raise RuntimeError("DD-3 contract G0 seed end changed")
    if int(paired["G1_seed_start"]) != EXPECTED_G0_SEEDS[0]:
        raise RuntimeError("DD-3 contract G1 seed start changed")
    if int(paired["G1_seed_end_inclusive"]) != EXPECTED_G0_SEEDS[-1]:
        raise RuntimeError("DD-3 contract G1 seed end changed")
    if not bool(paired["common_random_numbers"]):
        raise RuntimeError("DD-3 contract no longer requires paired common random numbers")
    return contract


def _prepare(args: argparse.Namespace) -> None:
    contract = _load_audit_contract(args.audit_contract.resolve())
    metadata, rhos, _, _ = _load_public_context(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    seeds = _paired_seed_bank(args.phase1_confirmation_protocol.resolve())
    hidden = _validate_hidden_provider_provenance(args)
    boundaries = _validate_graph_intervention(
        metadata=metadata,
        rhos=rhos,
        m0_contract_path=args.m0_contract.resolve(),
    )

    if str(contract["paired_whitebox"]["expected_provider_process_sha256"]) != str(
        hidden["provider_process_sha256"]
    ):
        raise RuntimeError("DD-3 contract provider-process hash differs from matched provenance")

    print("DD3_GRAPH_RESPONSE_PREPARE_PASS_NO_SIMULATION")
    print(f"provider_process={hidden['case_id']}")
    print(f"provider_process_sha256={hidden['provider_process_sha256']}")
    print(f"paired_wb_seeds={seeds[0]}..{seeds[-1]} n={len(seeds)}")
    print("only_intended_intervention=G0_to_G1_public_network_embedding")
    print(
        "M0_structural_note=sigma product uses the same local I1 sigma values; "
        "graph enters only through induced A_G/applicability"
    )
    print("\nINDUCED_BOUNDARY_SHIFT")
    print(boundaries.to_string(index=False))


def _generate_paired_g1_wb(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    audit_contract = _load_audit_contract(args.audit_contract.resolve())
    metadata, _, _, workload = _load_public_context(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    seeds = _paired_seed_bank(args.phase1_confirmation_protocol.resolve())

    contract = _read_json(args.g1_wb_contract.resolve())
    surrogates, execution_fraction, hidden = _validate_hidden_model(
        contract=contract,
        phase1_config_path=args.phase1_config.resolve(),
        phase1_confirmation_protocol_path=args.phase1_confirmation_protocol.resolve(),
        phase1_confirmation_freeze_path=args.phase1_confirmation_freeze.resolve(),
        i1_region_acquisition_path=args.i1_region_acquisition.resolve(),
        i1_sigma_acquisition_path=args.i1_sigma_acquisition.resolve(),
    )
    if str(hidden["case_id"]) != EXPECTED_G0_SETTING:
        raise RuntimeError("paired G1 WB hidden process is not D300/d0.20")
    if str(audit_contract["paired_whitebox"]["expected_provider_process_sha256"]) != str(
        hidden["provider_process_sha256"]
    ):
        raise RuntimeError("DD-3 contract provider-process hash mismatch")

    graph_spec = build_g1_public_graph_spec()
    validate_g1_public_graph_spec(graph_spec)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ledger_path = output / "dd3_g1_paired_whitebox_ledger.csv"

    if ledger_path.exists():
        ledger = pd.read_csv(ledger_path)
        actual = tuple(sorted(ledger["trajectory_seed"].astype(int).unique()))
        if actual != seeds:
            raise RuntimeError("existing DD-3 G1 ledger uses a different seed bank")
        if int(ledger["trajectory"].nunique()) != len(seeds):
            raise RuntimeError("existing DD-3 G1 ledger trajectory count mismatch")
        reused = True
        print("DD3 paired G1 WB: loaded completed checkpoint", flush=True)
    else:
        frames: list[pd.DataFrame] = []
        for trajectory, seed in enumerate(seeds):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                one = execute_one_g1_prediction_trajectory(
                    provider_surrogates=surrogates,
                    graph_spec=graph_spec,
                    workload_period=float(workload["period"]),
                    stop_time=float(workload["horizon_max"]),
                    trajectory_seed=int(seed),
                    canonical_ipt=float(hidden["effective_IPT"]),
                    execution_fraction=float(execution_fraction),
                )
            one.insert(0, "trajectory", int(trajectory))
            one.insert(1, "trajectory_seed", int(seed))
            frames.append(one)
            if trajectory == 0 or (trajectory + 1) % 25 == 0 or trajectory + 1 == len(seeds):
                print(f"  DD3-G1-WB {trajectory + 1}/{len(seeds)}", flush=True)
        ledger = pd.concat(frames, ignore_index=True)
        ledger.to_csv(ledger_path, index=False)
        reused = False

    manifest = {
        "status": "DD3_G1_PAIRED_WHITEBOX_COMPLETE_V1",
        "scientific_role": "paired graph-response due diligence only",
        "provider_process": hidden["case_id"],
        "provider_process_sha256": hidden["provider_process_sha256"],
        "matched_i1_provider_process": True,
        "G0_reference_seed_start": int(seeds[0]),
        "G0_reference_seed_end_inclusive": int(seeds[-1]),
        "G1_seed_start": int(seeds[0]),
        "G1_seed_end_inclusive": int(seeds[-1]),
        "common_random_numbers_with_G0": True,
        "n_trajectories": len(seeds),
        "graph_condition": "G1_ASYM_PARALL_V1",
        "ledger_sha256": _sha256(ledger_path),
        "n_request_rows": int(len(ledger)),
        "checkpoint_reused": bool(reused),
        "audit_contract_sha256": _sha256(args.audit_contract.resolve()),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    manifest_path = output / "dd3_g1_paired_whitebox_manifest_v1.json"
    _write_json(manifest_path, manifest)
    print("DD3_G1_PAIRED_WHITEBOX_COMPLETE")
    print(f"ledger={ledger_path}")
    print(f"manifest={manifest_path}")
    print(f"python_wall_seconds={time.perf_counter() - started:.3f}")


def _load_g0_comparison(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {
        "rho_global",
        "horizon",
        "sigma_whitebox",
        "sigma_m0",
        "sigma_m1",
        "sigma_m2_mean",
        "sigma_m2_min",
        "sigma_m2_max",
        "A_G_l_max",
        "A_G_c_max",
        "A_G_q_min",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise RuntimeError(f"G0 comparison missing columns: {missing}")
    return frame


def _load_g1_predictions(
    *,
    ensemble_path: Path,
    m0_path: Path,
    rhos: list[float],
    horizons: list[float],
) -> pd.DataFrame:
    ensemble = pd.read_csv(ensemble_path)
    m0 = pd.read_csv(m0_path)

    ensemble = _snap_frame_to_frozen_grid(
        ensemble,
        frozen_rhos=rhos,
        frozen_horizons=horizons,
        label="DD3 G1 ensemble",
    )
    m0 = _snap_frame_to_frozen_grid(
        m0,
        frozen_rhos=rhos,
        frozen_horizons=horizons,
        label="DD3 G1 M0",
    )
    out = ensemble.merge(
        m0[["rho_global", "horizon", "sigma_i1_m0"]],
        on=["rho_global", "horizon"],
        how="inner",
        validate="one_to_one",
    )
    return out.rename(
        columns={
            "sigma_i1_m0": "sigma_m0",
            "sigma_m1_same_seed_bank": "sigma_m1",
        }
    )


def _build_g1_paired_wb(
    *,
    g1_predictions: pd.DataFrame,
    ledger: pd.DataFrame,
    rhos: list[float],
    horizons: list[float],
    workload: dict[str, float],
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for rho in rhos:
        selected = g1_predictions[
            np.isclose(
                g1_predictions["rho_global"].astype(float),
                float(rho),
                atol=TOL,
                rtol=0.0,
            )
        ]
        triples = selected[["A_G_l_max", "A_G_c_max", "A_G_q_min"]].drop_duplicates()
        if len(triples) != 1:
            raise RuntimeError(f"G1 rho={rho}: prediction does not expose one A_G")
        rec = triples.iloc[0]

        from m0_analytic_composition import AdmissibilityBoundary

        boundary = AdmissibilityBoundary(
            l_max=float(rec["A_G_l_max"]),
            c_max=float(rec["A_G_c_max"]),
            q_min=float(rec["A_G_q_min"]),
        )
        curve = build_empirical_graph_sigma_curve(
            ledger,
            boundary=boundary,
            rho_global=float(rho),
            horizons=horizons,
            stop_time=float(workload["horizon_max"]),
            accounting_origin=float(workload["accounting_origin"]),
            output_column="sigma_whitebox",
        )
        curve.insert(0, "rho_global", float(rho))
        rows.append(curve)
    return pd.concat(rows, ignore_index=True)


def _paired_ledger_checks(
    *,
    g0_ledger_path: Path,
    g1_ledger: pd.DataFrame,
    protocol_path: Path,
) -> dict[str, float | int]:
    g0 = pd.read_csv(g0_ledger_path)
    seeds = _paired_seed_bank(protocol_path)
    seed_map = {idx: seed for idx, seed in enumerate(seeds)}
    if "trajectory_seed" not in g0.columns:
        g0["trajectory_seed"] = g0["trajectory"].astype(int).map(seed_map)
    if g0["trajectory_seed"].isna().any():
        raise RuntimeError("cannot map G0 trajectory indices to frozen seed bank")

    cols = ["trajectory_seed", "request_id", "emission", "completion", "L", "C", "Q"]
    merged = g0[cols].merge(
        g1_ledger[cols],
        on=["trajectory_seed", "request_id"],
        how="inner",
        suffixes=("_g0", "_g1"),
        validate="one_to_one",
    )
    if len(merged) != len(g0) or len(merged) != len(g1_ledger):
        raise RuntimeError("paired G0/G1 WB request identity does not align")

    both_complete = (
        np.isfinite(pd.to_numeric(merged["completion_g0"], errors="coerce"))
        & np.isfinite(pd.to_numeric(merged["completion_g1"], errors="coerce"))
    )
    common = merged[both_complete].copy()
    if common.empty:
        raise RuntimeError("paired WB has no jointly completed requests")

    c_diff = (
        pd.to_numeric(common["C_g1"], errors="coerce")
        - pd.to_numeric(common["C_g0"], errors="coerce")
    ).abs()
    q_diff = (
        pd.to_numeric(common["Q_g1"], errors="coerce")
        - pd.to_numeric(common["Q_g0"], errors="coerce")
    ).abs()
    emission_diff = (
        pd.to_numeric(merged["emission_g1"], errors="coerce")
        - pd.to_numeric(merged["emission_g0"], errors="coerce")
    ).abs()
    if float(c_diff.max()) > 1e-10:
        raise RuntimeError(
            f"paired WB cost mismatch suggests provider stochastic work changed: {c_diff.max()}"
        )
    if float(q_diff.max()) > TOL:
        raise RuntimeError("paired WB QoS changed across graph intervention")
    if float(emission_diff.max()) > TOL:
        raise RuntimeError("paired WB source emission schedule changed")

    l_shift = (
        pd.to_numeric(common["L_g1"], errors="coerce")
        - pd.to_numeric(common["L_g0"], errors="coerce")
    )
    return {
        "n_request_pairs": int(len(merged)),
        "n_jointly_completed": int(len(common)),
        "max_abs_cost_difference": float(c_diff.max()),
        "max_abs_quality_difference": float(q_diff.max()),
        "max_abs_emission_difference": float(emission_diff.max()),
        "mean_latency_shift_seconds": float(l_shift.mean()),
        "min_latency_shift_seconds": float(l_shift.min()),
        "max_latency_shift_seconds": float(l_shift.max()),
    }


def _response_metrics(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    methods = ("m0", "m1", "m2")
    rows: list[dict[str, Any]] = []
    per_rho_rows: list[dict[str, Any]] = []

    def summarize(group: pd.DataFrame, method: str) -> dict[str, float]:
        truth = group["delta_sigma_wb"].astype(float).to_numpy()
        pred = group[f"delta_sigma_{method}"].astype(float).to_numpy()
        error = pred - truth
        if np.std(truth) > 0.0 and np.std(pred) > 0.0:
            corr = float(np.corrcoef(truth, pred)[0, 1])
        else:
            corr = float("nan")
        denom = float(np.dot(truth, truth))
        slope = float(np.dot(pred, truth) / denom) if denom > 0.0 else float("nan")
        nonzero = np.abs(truth) > TOL
        sign_agreement = (
            float(np.mean(np.sign(pred[nonzero]) == np.sign(truth[nonzero])))
            if np.any(nonzero)
            else float("nan")
        )
        return {
            "response_mae": float(np.mean(np.abs(error))),
            "response_rmse": float(np.sqrt(np.mean(error * error))),
            "response_bias": float(np.mean(error)),
            "response_max_abs_error": float(np.max(np.abs(error))),
            "delta_correlation": corr,
            "through_origin_response_slope": slope,
            "sign_agreement_when_WB_nonzero": sign_agreement,
            "mean_abs_predicted_graph_shift": float(np.mean(np.abs(pred))),
            "mean_abs_WB_graph_shift": float(np.mean(np.abs(truth))),
        }

    for method in methods:
        rows.append({"method": method.upper(), **summarize(frame, method)})

    for rho, group in frame.groupby("rho_global", sort=True):
        for method in methods:
            per_rho_rows.append(
                {
                    "rho_global": float(rho),
                    "method": method.upper(),
                    **summarize(group, method),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(per_rho_rows)


def _plot_absolute(frame: pd.DataFrame, path: Path) -> None:
    rhos = sorted(frame["rho_global"].astype(float).unique())
    fig, axes = plt.subplots(
        len(rhos), 2, figsize=(13.0, 2.55 * len(rhos)),
        sharex=True, sharey=True, squeeze=False,
    )
    for row, rho in enumerate(rhos):
        group = frame[np.isclose(frame["rho_global"], rho, atol=TOL, rtol=0.0)].sort_values("horizon")
        x = group["horizon"].astype(float).to_numpy()
        for col, graph in enumerate(("g0", "g1")):
            ax = axes[row, col]
            ax.fill_between(
                x,
                group[f"sigma_m2_min_{graph}"].astype(float).to_numpy(),
                group[f"sigma_m2_max_{graph}"].astype(float).to_numpy(),
                alpha=0.15,
                label="M2 range",
            )
            ax.plot(x, group[f"sigma_wb_{graph}"], linewidth=2.5, label="WB")
            ax.plot(x, group[f"sigma_m0_{graph}"], linestyle="--", linewidth=1.6, label="M0")
            ax.plot(x, group[f"sigma_m1_{graph}"], linestyle=":", linewidth=1.8, label="M1")
            ax.plot(x, group[f"sigma_m2_{graph}"], linewidth=2.0, label="M2")
            ax.set_ylim(0.0, 1.02)
            ax.grid(True, alpha=0.2)
            ax.set_title(f"{graph.upper()} matched D300, rho={rho:g}")
    axes[0, 0].legend(frameon=False, fontsize=8, ncol=5, loc="lower left")
    fig.suptitle("Matched-provider sigma under G0 and G1")
    fig.supxlabel("Horizon H (s)")
    fig.supylabel("sigma")
    fig.tight_layout(rect=(0.035, 0.035, 1.0, 0.96))
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _plot_delta(frame: pd.DataFrame, path: Path) -> None:
    rhos = sorted(frame["rho_global"].astype(float).unique())
    fig, axes = plt.subplots(2, 3, figsize=(13.4, 7.6), sharex=True, sharey=True)
    flat = list(axes.flat)
    for ax, rho in zip(flat, rhos):
        group = frame[np.isclose(frame["rho_global"], rho, atol=TOL, rtol=0.0)].sort_values("horizon")
        x = group["horizon"].astype(float).to_numpy()
        ax.axhline(0.0, linewidth=0.8)
        ax.plot(x, group["delta_sigma_wb"], linewidth=2.5, label="WB")
        ax.plot(x, group["delta_sigma_m0"], linestyle="--", linewidth=1.6, label="M0")
        ax.plot(x, group["delta_sigma_m1"], linestyle=":", linewidth=1.8, label="M1")
        ax.plot(x, group["delta_sigma_m2"], linewidth=2.0, label="M2")
        ax.grid(True, alpha=0.2)
        ax.set_title(f"rho={rho:g}")
    for ax in flat[len(rhos):]:
        ax.axis("off")
    flat[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Graph response: Delta sigma = sigma(G1) - sigma(G0)")
    fig.supxlabel("Horizon H (s)")
    fig.supylabel("Delta sigma")
    fig.tight_layout(rect=(0.02, 0.02, 1.0, 0.95))
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _evaluate(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    audit_contract = _load_audit_contract(args.audit_contract.resolve())
    output = args.output.resolve()
    ledger_path = output / "dd3_g1_paired_whitebox_ledger.csv"
    manifest_path = output / "dd3_g1_paired_whitebox_manifest_v1.json"
    if not ledger_path.exists() or not manifest_path.exists():
        raise RuntimeError("run --generate-paired-wb before --evaluate")

    manifest = _read_json(manifest_path)
    if manifest.get("status") != "DD3_G1_PAIRED_WHITEBOX_COMPLETE_V1":
        raise RuntimeError("unexpected paired G1 WB manifest status")
    if str(manifest.get("ledger_sha256")) != _sha256(ledger_path):
        raise RuntimeError("paired G1 WB ledger changed after generation")

    metadata, rhos, horizons, workload = _load_public_context(
        args.i1_card_root.resolve(), args.i1_manifest.resolve()
    )
    hidden = _validate_hidden_provider_provenance(args)
    if str(manifest["provider_process_sha256"]) != str(hidden["provider_process_sha256"]):
        raise RuntimeError("paired G1 WB provider fingerprint changed")
    if str(manifest.get("audit_contract_sha256")) != _sha256(args.audit_contract.resolve()):
        raise RuntimeError("paired G1 WB is not tied to the current frozen DD-3 contract")
    if str(audit_contract["paired_whitebox"]["expected_provider_process_sha256"]) != str(
        hidden["provider_process_sha256"]
    ):
        raise RuntimeError("DD-3 contract provider-process hash changed")

    g0 = _load_g0_comparison(args.g0_comparison.resolve())
    g0 = _snap_frame_to_frozen_grid(
        g0,
        frozen_rhos=rhos,
        frozen_horizons=horizons,
        label="DD3 G0 comparison",
    )
    g1_pred = _load_g1_predictions(
        ensemble_path=args.g1_ensemble.resolve(),
        m0_path=args.g1_m0.resolve(),
        rhos=rhos,
        horizons=horizons,
    )
    g1_ledger = pd.read_csv(ledger_path)
    g1_wb = _build_g1_paired_wb(
        g1_predictions=g1_pred,
        ledger=g1_ledger,
        rhos=rhos,
        horizons=horizons,
        workload=workload,
    )
    g1_wb = _snap_frame_to_frozen_grid(
        g1_wb,
        frozen_rhos=rhos,
        frozen_horizons=horizons,
        label="DD3 paired G1 WB",
    )

    g0_small = g0[
        [
            "rho_global", "horizon",
            "sigma_whitebox", "sigma_m0", "sigma_m1", "sigma_m2_mean",
            "sigma_m2_min", "sigma_m2_max",
        ]
    ].rename(
        columns={
            "sigma_whitebox": "sigma_wb_g0",
            "sigma_m0": "sigma_m0_g0",
            "sigma_m1": "sigma_m1_g0",
            "sigma_m2_mean": "sigma_m2_g0",
            "sigma_m2_min": "sigma_m2_min_g0",
            "sigma_m2_max": "sigma_m2_max_g0",
        }
    )
    g1_small = g1_pred[
        [
            "rho_global", "horizon",
            "sigma_m0", "sigma_m1", "sigma_m2_mean",
            "sigma_m2_min", "sigma_m2_max",
        ]
    ].rename(
        columns={
            "sigma_m0": "sigma_m0_g1",
            "sigma_m1": "sigma_m1_g1",
            "sigma_m2_mean": "sigma_m2_g1",
            "sigma_m2_min": "sigma_m2_min_g1",
            "sigma_m2_max": "sigma_m2_max_g1",
        }
    ).merge(
        g1_wb[["rho_global", "horizon", "sigma_whitebox"]].rename(
            columns={"sigma_whitebox": "sigma_wb_g1"}
        ),
        on=["rho_global", "horizon"],
        how="inner",
        validate="one_to_one",
    )

    comparison = g0_small.merge(
        g1_small,
        on=["rho_global", "horizon"],
        how="inner",
        validate="one_to_one",
    )
    if len(comparison) != len(rhos) * len(horizons):
        raise RuntimeError("DD-3 comparison does not cover full frozen support")

    for label in ("wb", "m0", "m1", "m2"):
        comparison[f"delta_sigma_{label}"] = (
            comparison[f"sigma_{label}_g1"].astype(float)
            - comparison[f"sigma_{label}_g0"].astype(float)
        )

    m0_max_shift = float(np.max(np.abs(comparison["delta_sigma_m0"].astype(float))))
    if m0_max_shift > TOL:
        raise RuntimeError(
            f"M0 should be structurally graph-invariant in this protocol, observed {m0_max_shift}"
        )

    for method in ("m0", "m1", "m2"):
        comparison[f"graph_response_error_{method}"] = (
            comparison[f"delta_sigma_{method}"].astype(float)
            - comparison["delta_sigma_wb"].astype(float)
        )

    ledger_checks = _paired_ledger_checks(
        g0_ledger_path=args.g0_whitebox_ledger.resolve(),
        g1_ledger=g1_ledger,
        protocol_path=args.phase1_confirmation_protocol.resolve(),
    )
    overall, per_rho = _response_metrics(comparison)

    comparison_path = output / "dd3_graph_response_pointwise.csv"
    overall_path = output / "dd3_graph_response_summary.csv"
    per_rho_path = output / "dd3_graph_response_per_rho.csv"
    absolute_plot = output / "dd3_g0_g1_absolute_sigma.png"
    delta_plot = output / "dd3_g0_g1_delta_sigma.png"
    comparison.to_csv(comparison_path, index=False)
    overall.to_csv(overall_path, index=False)
    per_rho.to_csv(per_rho_path, index=False)
    _plot_absolute(comparison, absolute_plot)
    _plot_delta(comparison, delta_plot)

    wb_mean_abs_shift = float(np.mean(np.abs(comparison["delta_sigma_wb"])))
    result = {
        "status": "DD3_GRAPH_RESPONSE_AUDIT_COMPLETE_V1",
        "scientific_role": "due diligence, no method tuning or selection",
        "provider_process": hidden["case_id"],
        "provider_process_sha256": hidden["provider_process_sha256"],
        "paired_WB_common_random_numbers": True,
        "paired_WB_seed_start": EXPECTED_G0_SEEDS[0],
        "paired_WB_seed_end_inclusive": EXPECTED_G0_SEEDS[-1],
        "WB_mean_abs_graph_shift": wb_mean_abs_shift,
        "M0_max_abs_graph_shift": m0_max_shift,
        "M0_structurally_graph_invariant_under_current_protocol": True,
        "ledger_pair_checks": ledger_checks,
        "response_summary": overall.to_dict(orient="records"),
        "outputs": {
            "pointwise": comparison_path.name,
            "summary": overall_path.name,
            "per_rho": per_rho_path.name,
            "absolute_sigma_plot": absolute_plot.name,
            "delta_sigma_plot": delta_plot.name,
        },
        "audit_contract_sha256": _sha256(args.audit_contract.resolve()),
        "interpretation_rule": (
            "A method captures graph response to the extent that Delta sigma_method "
            "tracks paired Delta sigma_WB. M0 is expected to have Delta sigma=0 by "
            "construction; M1/M2 are empirical graph simulators and are evaluated "
            "by response error without retuning."
        ),
        "git_commit": _git_head(FIRST_SCIENCE.parent),
    }
    result_path = output / "dd3_graph_response_manifest_v1.json"
    _write_json(result_path, result)

    print("DD3_GRAPH_RESPONSE_AUDIT_COMPLETE")
    print("\nPAIRED_WB_LEDGER_CHECKS")
    print(json.dumps(ledger_checks, indent=2))
    print("\nGRAPH_RESPONSE_SUMMARY")
    print(overall.to_string(index=False))
    print("\nGRAPH_RESPONSE_PER_RHO")
    print(per_rho.to_string(index=False))
    print(f"\nWB_mean_abs_graph_shift={wb_mean_abs_shift:.6f}")
    print(f"M0_max_abs_graph_shift={m0_max_shift:.6g}")
    print(f"absolute_plot={absolute_plot}")
    print(f"delta_plot={delta_plot}")
    print(f"manifest={result_path}")
    print(f"python_wall_seconds={time.perf_counter() - started:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit whether frozen M0/M1/M2 capture the G0->G1 graph response"
    )
    parser.add_argument(
        "--audit-contract",
        type=Path,
        default=HERE / "config_phase4_dd3_graph_response_audit_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "dd3_graph_response_audit_v1",
    )
    parser.add_argument(
        "--g0-comparison",
        type=Path,
        default=HERE
        / "results"
        / "m2_b6_joint_ensemble_whitebox_v1"
        / "m2_b6_pointwise_comparison.csv",
    )
    parser.add_argument(
        "--g0-whitebox-ledger",
        type=Path,
        default=PHASE1
        / "results"
        / "phase1_v2_fresh_confirmation_v1"
        / "all_top_level_request_ledgers.csv",
    )
    parser.add_argument(
        "--g1-ensemble",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_blind_prediction_v1"
        / "m2_g1_ensemble_curve.csv",
    )
    parser.add_argument(
        "--g1-m0",
        type=Path,
        default=HERE
        / "results"
        / "m2_g1_blind_prediction_v1"
        / "m2_g1_m0_curve.csv",
    )
    parser.add_argument(
        "--g1-wb-contract",
        type=Path,
        default=HERE / "config_phase4_m2_g1_whitebox_validation_v2_matched_provider.json",
    )
    parser.add_argument(
        "--m0-contract",
        type=Path,
        default=PHASE3 / "config_phase3_m0_contract_v1.json",
    )
    parser.add_argument(
        "--phase1-config",
        type=Path,
        default=PHASE1 / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--phase1-confirmation-protocol",
        type=Path,
        default=PHASE1 / "config_phase1_v2_confirmation_v1.json",
    )
    parser.add_argument(
        "--phase1-confirmation-freeze",
        type=Path,
        default=PHASE1 / "phase1_v2_confirmation_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--i1-region-acquisition",
        type=Path,
        default=PHASE2 / "config_phase2_i1_acquisition_v1.json",
    )
    parser.add_argument(
        "--i1-sigma-acquisition",
        type=Path,
        default=PHASE2 / "config_phase2_i1_sigma_acquisition_v1.json",
    )
    parser.add_argument(
        "--i1-card-root",
        type=Path,
        default=PHASE2 / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    parser.add_argument(
        "--i1-manifest",
        type=Path,
        default=PHASE2
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public"
        / "i1_rho_conditioned_manifest_v1.json",
    )

    stages = parser.add_mutually_exclusive_group(required=True)
    stages.add_argument("--prepare-only", action="store_true")
    stages.add_argument("--generate-paired-wb", action="store_true")
    stages.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()

    if args.prepare_only:
        _prepare(args)
    elif args.generate_paired_wb:
        _generate_paired_g1_wb(args)
    else:
        _evaluate(args)


if __name__ == "__main__":
    main()
