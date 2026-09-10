"""Inspect the frozen provider-local evidence used to construct I1 directly.

Scientific role
---------------
This is a read-only Phase-2 audit. It verifies that the retained ProviderA/B/C
request ledgers are exactly the frozen acquisition corpus and summarizes their
native provider-local L/C/Q observations before any new A_i rule is frozen.

There is deliberately no A_G input, no global budget decomposition, no M0/M1,
and no I1 sigma selection in this script.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ACQUISITION = HERE / "results" / "i1_acquisition_v1"
EVIDENCE_MANIFEST = HERE / "phase2_i1_freeze_manifest_v1.json"
DIRECT_CONTRACT = HERE / "config_phase2_i1_direct_trace_v2.json"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values[np.isfinite(values.to_numpy(dtype=float))]


def _summary_row(provider: str, ledger: pd.DataFrame) -> dict[str, object]:
    required = {"trajectory", "request_id", "emission", "completion", "L", "C", "Q"}
    missing = required.difference(ledger.columns)
    if missing:
        raise ValueError(f"{provider} ledger missing columns: {sorted(missing)}")

    if ledger[["trajectory", "request_id"]].duplicated().any():
        raise ValueError(f"{provider} has duplicate trajectory/request rows")

    latency = _finite(ledger["L"])
    cost = _finite(ledger["C"])
    quality = _finite(ledger["Q"])
    completed = pd.to_numeric(ledger["completion"], errors="coerce").notna()

    if latency.empty or cost.empty or quality.empty:
        raise ValueError(f"{provider} must contain finite completed L/C/Q observations")

    # These quantiles are descriptive only. This audit does not select A_i.
    def q(values: pd.Series, level: float) -> float:
        return float(values.quantile(level, interpolation="higher"))

    quality_unique = sorted(set(float(x) for x in quality.unique()))

    return {
        "provider": provider,
        "rows": int(len(ledger)),
        "trajectories": int(ledger["trajectory"].nunique()),
        "completed": int(completed.sum()),
        "unresolved": int((~completed).sum()),
        "L_mean": float(latency.mean()),
        "L_p50": q(latency, 0.50),
        "L_p95": q(latency, 0.95),
        "L_p99": q(latency, 0.99),
        "L_max": float(latency.max()),
        "C_mean": float(cost.mean()),
        "C_p50": q(cost, 0.50),
        "C_p95": q(cost, 0.95),
        "C_p99": q(cost, 0.99),
        "C_max": float(cost.max()),
        "Q_min": float(quality.min()),
        "Q_max": float(quality.max()),
        "Q_unique": ",".join(f"{x:.12g}" for x in quality_unique),
    }


def main() -> None:
    evidence_manifest = _load_json(EVIDENCE_MANIFEST)
    direct_contract = _load_json(DIRECT_CONTRACT)

    if direct_contract.get("status") != "PHASE2_DIRECT_I1_CONSTRUCTION_V2_AI_SELECTION_OPEN":
        raise ValueError("unexpected direct-I1 contract status")
    if direct_contract["A_i_ownership"].get("A_G_is_input") is not False:
        raise ValueError("direct I1 construction must not use A_G to create A_i")
    if direct_contract["A_i_ownership"].get("global_budget_split_allowed") is not False:
        raise ValueError("direct I1 construction must not split global budgets into A_i")

    expected_hashes = evidence_manifest.get("provider_corpus_sha256", {})
    expected_rows = evidence_manifest.get("provider_rows", {})
    expected_trajectories = evidence_manifest.get("provider_trajectories", {})

    rows: list[dict[str, object]] = []
    hashes: list[dict[str, str]] = []

    for provider in PROVIDERS:
        path = ACQUISITION / "private" / provider / "provider_request_ledgers.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing frozen provider ledger: {path}")

        actual_hash = _sha256(path)
        if actual_hash != str(expected_hashes.get(provider, "")):
            raise RuntimeError(f"{provider} frozen provider-corpus SHA-256 mismatch")

        ledger = pd.read_csv(path)
        if len(ledger) != int(expected_rows[provider]):
            raise RuntimeError(f"{provider} row count differs from frozen evidence manifest")
        if ledger["trajectory"].nunique() != int(expected_trajectories[provider]):
            raise RuntimeError(f"{provider} trajectory count differs from frozen evidence manifest")

        rows.append(_summary_row(provider, ledger))
        hashes.append({"provider": provider, "sha256": actual_hash})

    frame = pd.DataFrame(rows)
    print("PHASE2_DIRECT_PROVIDER_EVIDENCE_AUDIT_PASS")
    print("A_G_used=false")
    print("global_budget_split=false")
    print("M0_M1_used=false")
    print("\nPROVIDER_LOCAL_EVIDENCE_SUMMARY")
    with pd.option_context("display.max_columns", None, "display.width", 240):
        print(frame.to_string(index=False))
    print("\nFROZEN_PROVIDER_CORPUS_SHA256")
    print(pd.DataFrame(hashes).to_string(index=False))


if __name__ == "__main__":
    main()
