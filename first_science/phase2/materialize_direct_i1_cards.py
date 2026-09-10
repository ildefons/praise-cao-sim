"""Materialize the final direct-I1 provider cards from frozen local evidence.

Pipeline
--------
frozen provider ledger T_i
    -> frozen provider-local rule A_i = (p99 L_i, p99 C_i, min Q_i)
    -> sigma_i(A_i,H;rho) on the frozen H x R support
    -> public I1_i card files.

No A_G, global budget allocation, M0, or M1 result enters this module.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from i1_provider_card import (
    assert_public_i1_card_has_no_forbidden_information,
    build_i1_provider_card,
)

HERE = Path(__file__).resolve().parent
ACQUISITION = HERE / "results" / "i1_acquisition_v1"
OUTPUT = HERE / "results" / "i1_cards_direct_v2"
EVIDENCE_MANIFEST = HERE / "phase2_i1_freeze_manifest_v1.json"
DIRECT_CONTRACT = HERE / "config_phase2_i1_direct_trace_v2.json"
REGION_RULE = HERE / "config_phase2_i1_local_region_rule_v1.json"
CARD_CONTRACT = HERE / "config_phase2_i1_provider_card_v2.json"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values[np.isfinite(values.to_numpy(dtype=float))]


def empirical_higher_quantile(series: pd.Series, level: float) -> float:
    """Return the observed upper order statistic used by the frozen local rule."""
    finite = _finite(series)
    if finite.empty:
        raise ValueError("cannot derive provider-local threshold from no finite data")
    return float(finite.quantile(float(level), interpolation="higher"))


def derive_frozen_local_region(
    provider: str,
    ledger: pd.DataFrame,
    rule: dict,
) -> dict[str, object]:
    """Derive the one frozen A_i for a provider using only provider-local evidence."""
    latency_rule = rule["rule"]["latency_threshold"]
    cost_rule = rule["rule"]["cost_threshold"]
    quality_rule = rule["rule"]["quality_threshold"]

    if latency_rule != {
        "source": "provider_local_L",
        "operation": "empirical_quantile",
        "quantile": 0.99,
        "interpolation": "higher",
    }:
        raise ValueError("unexpected frozen latency rule")
    if cost_rule != {
        "source": "provider_local_C",
        "operation": "empirical_quantile",
        "quantile": 0.99,
        "interpolation": "higher",
    }:
        raise ValueError("unexpected frozen cost rule")
    if quality_rule != {
        "source": "provider_local_Q",
        "operation": "minimum_finite_observed_value",
    }:
        raise ValueError("unexpected frozen quality rule")

    quality = _finite(ledger["Q"])
    if quality.empty:
        raise ValueError(f"{provider} has no finite Q observations")

    return {
        "region_id": f"{provider}_DIRECT_P99_L_P99_C_MINQ_V1",
        "l_max": empirical_higher_quantile(ledger["L"], 0.99),
        "c_max": empirical_higher_quantile(ledger["C"], 0.99),
        "q_min": float(quality.min()),
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    evidence = _load_json(EVIDENCE_MANIFEST)
    direct = _load_json(DIRECT_CONTRACT)
    rule = _load_json(REGION_RULE)
    card_contract = _load_json(CARD_CONTRACT)

    if direct.get("status") != "PHASE2_DIRECT_I1_CONSTRUCTION_V2_LOCAL_RULE_FROZEN":
        raise ValueError("direct-I1 construction is not at the local-rule-frozen checkpoint")
    if rule.get("status") != "FROZEN_PHASE2_I1_LOCAL_REGION_RULE_V1":
        raise ValueError("provider-local A_i rule is not frozen")
    if rule.get("A_G_is_input") is not False:
        raise ValueError("A_G must not enter direct I1 construction")
    if rule.get("global_budget_split_allowed") is not False:
        raise ValueError("global budget splitting is forbidden in direct I1 construction")
    if card_contract.get("status") != "FROZEN_PHASE2_I1_CARD_CONTRACT_V2_DIRECT_LOCAL_REGION":
        raise ValueError("unexpected direct-I1 card contract")

    rho_values = [float(x) for x in card_contract["R"]["values"]]
    horizons = [float(x) for x in card_contract["H"]["values"]]
    workload = dict(card_contract["workload_contract"])
    workload.pop("semantics", None)
    stop_time = float(workload["horizon_max"])

    public_manifest: dict[str, object] = {
        "status": "MATERIALIZED_PHASE2_DIRECT_I1_CARD_SET_V2_NOT_YET_REPOSITORY_FROZEN",
        "phase": "phase2_i1",
        "local_region_rule": "FROZEN_PHASE2_I1_LOCAL_REGION_RULE_V1",
        "A_G_used": False,
        "M0_M1_used": False,
        "providers": {},
    }

    print("PHASE2_DIRECT_I1_MATERIALIZATION")
    print("A_G_used=false")
    print("global_budget_split=false")
    print("M0_M1_used=false")

    for provider in PROVIDERS:
        ledger_path = ACQUISITION / "private" / provider / "provider_request_ledgers.csv"
        if not ledger_path.exists():
            raise FileNotFoundError(f"missing frozen provider ledger: {ledger_path}")
        if _sha256(ledger_path) != evidence["provider_corpus_sha256"][provider]:
            raise RuntimeError(f"{provider} provider-corpus SHA-256 mismatch")

        ledger = pd.read_csv(ledger_path)
        region = derive_frozen_local_region(provider, ledger, rule)
        print(
            f"{provider}: A_i=(L<={region['l_max']:.15g}, "
            f"C<={region['c_max']:.15g}, Q>={region['q_min']:.15g})"
        )

        metadata, surface = build_i1_provider_card(
            provider_id=provider,
            private_provider_ledgers=ledger,
            local_regions=[region],
            rho_values=rho_values,
            horizons=horizons,
            stop_time=stop_time,
            workload_contract=workload,
        )
        metadata["local_regions"] = [region]
        metadata["local_region_rule"] = {
            "status": rule["status"],
            "latency": "p99 empirical higher quantile of provider-local L",
            "cost": "p99 empirical higher quantile of provider-local C",
            "quality": "minimum finite provider-local Q",
        }
        assert_public_i1_card_has_no_forbidden_information(metadata, surface)

        provider_dir = OUTPUT / "public" / provider
        card_path = provider_dir / "card.json"
        surface_path = provider_dir / "sigma_surface.csv"
        _write_json(card_path, metadata)
        provider_dir.mkdir(parents=True, exist_ok=True)
        surface.to_csv(surface_path, index=False)

        if len(surface) != len(rho_values) * len(horizons):
            raise RuntimeError(f"{provider} surface has unexpected number of rows")

        card_sha = _sha256(card_path)
        surface_sha = _sha256(surface_path)
        public_manifest["providers"][provider] = {
            "A_i": region,
            "n_surface_rows": int(len(surface)),
            "card_json_sha256": card_sha,
            "sigma_surface_csv_sha256": surface_sha,
        }
        print(
            f"{provider}: rows={len(surface)} card_sha256={card_sha} "
            f"surface_sha256={surface_sha}"
        )

    manifest_path = OUTPUT / "public" / "card_set_manifest.json"
    _write_json(manifest_path, public_manifest)
    print(f"card_set_manifest_sha256={_sha256(manifest_path)}")
    print("PHASE2_DIRECT_I1_MATERIALIZATION_PASS")
    print("repository_freeze_performed=false")


if __name__ == "__main__":
    main()
