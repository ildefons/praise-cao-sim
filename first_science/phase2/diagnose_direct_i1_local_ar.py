"""Diagnose provider-local A_i candidates directly from frozen Phase-2 traces.

Scientific purpose
------------------
The direct-I1 design requires each provider-local admissibility region A_i to
come from that provider's own acquisition evidence. This diagnostic therefore
reuses the already established Phase-1 *style* of AR calibration locally:
empirical L/C candidate thresholds are generated from the provider trace, then
candidate sigma surfaces are inspected for a healthy rho=0.95 contour and an
informative rho=0.99 contour.

There is deliberately no A_G input, no global budget decomposition, and no
M0/M1. This file is diagnostic only: it does not select or freeze A_i.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1"
if str(PHASE1) not in sys.path:
    sys.path.insert(0, str(PHASE1))

from sla_compliance_analysis import (  # noqa: E402
    SlaComplianceDefinition,
    build_request_sla_decision_table,
    calculate_empirical_sla_sigma_from_decision_tables,
    calculate_exact_empirical_sla_compliance_area,
)

ACQUISITION = HERE / "results" / "i1_acquisition_v1"
EVIDENCE_MANIFEST = HERE / "phase2_i1_freeze_manifest_v1.json"
PHASE1_AR_GENERATOR = PHASE1 / "config_phase1_sla_ar_generator_v1.json"
PHASE1_V2_FREEZE = PHASE1 / "phase1_v2_ar_freeze_manifest_v1.json"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
REPORT_HORIZONS = (120.0, 240.0)
EVENT_TOLERANCE = 1e-12


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def empirical_higher_quantile(values: pd.Series, level: float) -> float:
    """Return one observed upper order statistic, matching Phase-1 AR generation."""
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric[np.isfinite(numeric.to_numpy(dtype=float))]
    if numeric.empty:
        raise ValueError("cannot derive a local threshold from no finite values")
    return float(numeric.quantile(float(level), interpolation="higher"))


def build_local_mixed_candidates(
    ledger: pd.DataFrame,
    provider: str,
    levels: list[float],
) -> list[dict[str, object]]:
    """Build only joint L/C provider-local candidates from provider evidence."""
    finite_q = pd.to_numeric(ledger["Q"], errors="coerce")
    finite_q = finite_q[np.isfinite(finite_q.to_numpy(dtype=float))]
    if finite_q.empty:
        raise ValueError(f"{provider} has no finite quality observations")

    q_min = float(finite_q.min())
    latency_thresholds = {
        level: empirical_higher_quantile(ledger["L"], level) for level in levels
    }
    cost_thresholds = {
        level: empirical_higher_quantile(ledger["C"], level) for level in levels
    }

    candidates: list[dict[str, object]] = []
    for latency_level in levels:
        for cost_level in levels:
            candidates.append(
                {
                    "provider": provider,
                    "candidate_id": (
                        f"{provider}_LQ{latency_level:.3f}_CQ{cost_level:.3f}"
                    ),
                    "latency_quantile": float(latency_level),
                    "cost_quantile": float(cost_level),
                    "l_max": float(latency_thresholds[latency_level]),
                    "c_max": float(cost_thresholds[cost_level]),
                    "q_min": q_min,
                }
            )
    return candidates


def evaluate_candidate(
    ledger: pd.DataFrame,
    candidate: dict[str, object],
    rho_values: tuple[float, ...],
    stop_time: float,
) -> dict[str, object]:
    """Evaluate one local A_i on the frozen provider trajectories."""
    decision_tables = []
    for _, trajectory_ledger in ledger.groupby("trajectory", sort=True):
        decision_tables.append(
            build_request_sla_decision_table(
                trajectory_ledger,
                latency_threshold=float(candidate["l_max"]),
                cost_threshold=float(candidate["c_max"]),
                quality_threshold=float(candidate["q_min"]),
                stop_time=float(stop_time),
            )
        )

    result = dict(candidate)
    for rho in rho_values:
        definition = SlaComplianceDefinition(
            rho=float(rho), accounting_origin=0.0, zero_decision_compliance=1.0
        )
        _, normalized_area = calculate_exact_empirical_sla_compliance_area(
            decision_tables,
            definition,
            horizon_min=0.0,
            horizon_max=float(stop_time),
        )
        sigma, _ = calculate_empirical_sla_sigma_from_decision_tables(
            decision_tables, REPORT_HORIZONS, definition
        )
        tag = str(rho).replace(".", "p")
        result[f"R_{tag}"] = float(normalized_area)
        by_h = sigma.set_index("horizon")["sigma"]
        result[f"sigma120_{tag}"] = float(by_h.loc[120.0])
        result[f"sigma240_{tag}"] = float(by_h.loc[240.0])
    return result


def main() -> None:
    evidence_manifest = _load_json(EVIDENCE_MANIFEST)
    ar_generator = _load_json(PHASE1_AR_GENERATOR)
    phase1_freeze = _load_json(PHASE1_V2_FREEZE)

    levels = [float(value) for value in ar_generator["quantile_levels"]]
    if levels != [0.90, 0.925, 0.95, 0.975, 0.99]:
        raise RuntimeError("unexpected Phase-1 AR quantile battery")

    nominal_gate = phase1_freeze["selection_policy"]["nominal_health_gate"]
    stress_gate = phase1_freeze["selection_policy"]["stress_informativeness_gate"]
    nominal_rho = float(nominal_gate["rho"])
    stress_rho = float(stress_gate["rho"])
    rho_values = (nominal_rho, 0.975, stress_rho)
    stop_time = float(evidence_manifest["workload_contract"]["horizon_max"])

    print("PHASE2_DIRECT_LOCAL_AR_DIAGNOSTIC")
    print("selection_performed=false")
    print("A_G_used=false")
    print("global_budget_split=false")
    print("M0_M1_used=false")
    print(f"candidate_quantiles={levels}")
    print(
        "local_diagnostic_gate="
        f"R_{nominal_rho}>={float(nominal_gate['minimum'])},"
        f" {float(stress_gate['minimum'])}<=R_{stress_rho}<="
        f"{float(stress_gate['maximum'])}"
    )

    for provider in PROVIDERS:
        ledger_path = (
            ACQUISITION / "private" / provider / "provider_request_ledgers.csv"
        )
        expected_hash = evidence_manifest["provider_corpus_sha256"][provider]
        if _sha256(ledger_path) != expected_hash:
            raise RuntimeError(f"{provider} frozen provider-corpus SHA-256 mismatch")
        ledger = pd.read_csv(ledger_path)

        rows = [
            evaluate_candidate(ledger, candidate, rho_values, stop_time)
            for candidate in build_local_mixed_candidates(ledger, provider, levels)
        ]
        frame = pd.DataFrame(rows)
        nominal_column = f"R_{str(nominal_rho).replace('.', 'p')}"
        stress_column = f"R_{str(stress_rho).replace('.', 'p')}"
        eligible = frame[
            (frame[nominal_column] + EVENT_TOLERANCE >= float(nominal_gate["minimum"]))
            & (frame[stress_column] + EVENT_TOLERANCE >= float(stress_gate["minimum"]))
            & (frame[stress_column] <= float(stress_gate["maximum"]) + EVENT_TOLERANCE)
        ].copy()
        eligible = eligible.sort_values(
            [nominal_column, stress_column, "latency_quantile", "cost_quantile"],
            ascending=[False, True, True, True],
        ).reset_index(drop=True)

        print(f"\n{provider}_LOCAL_CANDIDATES")
        print(f"n_candidates={len(frame)} n_gate_passing={len(eligible)}")
        if eligible.empty:
            closest = frame.sort_values(
                [nominal_column, stress_column], ascending=[False, True]
            ).head(5)
            print("NO_GATE_PASSING_CANDIDATE; TOP_DIAGNOSTIC_ROWS")
            with pd.option_context("display.max_columns", None, "display.width", 260):
                print(closest.to_string(index=False))
        else:
            with pd.option_context("display.max_columns", None, "display.width", 260):
                print(eligible.to_string(index=False))

    print("\nPHASE2_DIRECT_LOCAL_AR_DIAGNOSTIC_PASS")
    print("selection_performed=false")


if __name__ == "__main__":
    main()
