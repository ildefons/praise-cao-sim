"""Materialize and hash-freeze the three public Phase-2 I1 cards.

This is the only Phase-2 step that reads the frozen private provider ledgers.
It verifies their SHA-256 fingerprints, derives each fixed A_i with the frozen
coordinate first-crossing rule, materializes the full H x rho surface, writes
public card artifacts, reloads them through the public reader, and emits a
public instance manifest with card hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from i1_local_region import derive_local_regions_from_traces
from i1_provider_card import (
    assert_public_i1_card_has_no_forbidden_information,
    build_i1_provider_card,
    load_i1_provider_card,
    write_i1_provider_card,
)

HERE = Path(__file__).resolve().parent
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(repository_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            text=True,
        ).strip()
    except Exception:
        return None


def load_and_verify_private_provider_ledgers(
    provider_root: Path,
    evidence_manifest: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Load T_i only after checking the frozen row/trajectory/hash contract."""
    ledgers: dict[str, pd.DataFrame] = {}
    expected_hashes = evidence_manifest["provider_corpus_sha256"]
    expected_rows = evidence_manifest["provider_rows"]
    expected_trajectories = evidence_manifest["provider_trajectories"]
    for provider in PROVIDERS:
        path = provider_root / provider / "provider_request_ledgers.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing frozen provider evidence: {path}")
        observed_hash = sha256_file(path)
        if observed_hash != str(expected_hashes[provider]):
            raise RuntimeError(f"{provider} evidence SHA-256 mismatch")
        ledger = pd.read_csv(path)
        if len(ledger) != int(expected_rows[provider]):
            raise RuntimeError(f"{provider} evidence row-count mismatch")
        if int(ledger["trajectory"].nunique()) != int(expected_trajectories[provider]):
            raise RuntimeError(f"{provider} evidence trajectory-count mismatch")
        ledgers[provider] = ledger
    return ledgers


def materialize_frozen_i1_cards(
    *,
    provider_root: Path,
    contract_path: Path,
    evidence_manifest_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    """Materialize the frozen public I1 instances and deterministic hashes."""
    contract = _read_json(contract_path)
    if contract.get("status") != "FROZEN_PHASE2_I1_CARD_CONTRACT_V2_DIRECT_TRACE":
        raise ValueError("unexpected active I1 contract")
    evidence_manifest = _read_json(evidence_manifest_path)
    if evidence_manifest.get("status") != "FROZEN_PHASE2_I1_V1":
        raise ValueError("unexpected provider-evidence freeze manifest")

    horizons = [float(value) for value in contract["H"]["values"]]
    rho_support = [float(value) for value in contract["R"]["values"]]
    workload = dict(contract["workload_contract"])
    calibration = dict(contract["A_i"]["calibration"])
    stop_time = float(workload["horizon_max"])

    ledgers = load_and_verify_private_provider_ledgers(provider_root, evidence_manifest)
    regions, calibration_table = derive_local_regions_from_traces(
        ledgers,
        rho_anchor=float(calibration["rho_anchor"]),
        horizons=horizons,
        stop_time=stop_time,
        anchor_horizon=float(calibration["H_star"]),
        sigma_target=float(calibration["sigma_target"]),
    )

    output_root.mkdir(parents=True, exist_ok=True)
    audit_root = output_root.parent / "private_audit"
    audit_root.mkdir(parents=True, exist_ok=True)
    calibration_table.to_csv(audit_root / "A_i_calibration_diagnostics.csv", index=False)

    cards_manifest: dict[str, Any] = {}
    for provider in PROVIDERS:
        metadata, surface = build_i1_provider_card(
            provider_id=provider,
            private_provider_ledgers=ledgers[provider],
            local_regions=[regions[provider]],
            rho_values=rho_support,
            horizons=horizons,
            stop_time=stop_time,
            workload_contract={
                "period": float(workload["period"]),
                "accounting_origin": float(workload["accounting_origin"]),
                "horizon_max": stop_time,
            },
        )
        metadata["A_i"] = {
            "region_id": str(regions[provider]["region_id"]),
            "l_max": float(regions[provider]["l_max"]),
            "c_max": float(regions[provider]["c_max"]),
            "q_min": float(regions[provider]["q_min"]),
        }
        metadata["construction"] = {
            "status": "FROZEN_PHASE2_TRACE_COORDINATE_SIGMA_CALIBRATION_V1",
            "rho_anchor": float(calibration["rho_anchor"]),
            "H_star": float(calibration["H_star"]),
            "sigma_target": float(calibration["sigma_target"]),
            "phase2_selects_rho_i": False,
        }
        assert_public_i1_card_has_no_forbidden_information(metadata, surface)

        card_directory = output_root / provider
        card_json, surface_csv = write_i1_provider_card(metadata, surface, card_directory)
        reloaded_metadata, reloaded_surface = load_i1_provider_card(card_directory)
        if reloaded_metadata["provider_id"] != provider:
            raise RuntimeError(f"{provider} public card reload mismatch")
        if len(reloaded_surface) != len(horizons) * len(rho_support):
            raise RuntimeError(f"{provider} public card support-size mismatch")

        cards_manifest[provider] = {
            "directory": provider,
            "A_i": dict(metadata["A_i"]),
            "n_surface_points": int(len(surface)),
            "card_json_sha256": sha256_file(card_json),
            "sigma_surface_sha256": sha256_file(surface_csv),
        }

    manifest: dict[str, Any] = {
        "status": "FROZEN_PHASE2_I1_CARD_INSTANCES_V1",
        "schema": str(contract["schema"]),
        "information_technology": str(contract["information_technology"]),
        "same_materialized_I1_for_M0_and_M1": True,
        "phase2_selects_rho_i": False,
        "private_evidence_verified_against_frozen_hashes": True,
        "H": horizons,
        "R": rho_support,
        "A_i_calibration": {
            "rho_anchor": float(calibration["rho_anchor"]),
            "H_star": float(calibration["H_star"]),
            "sigma_target": float(calibration["sigma_target"]),
            "coordinate_rule": str(calibration["coordinate_rule"]),
            "joint_sigma_forced_to_target": False,
        },
        "cards": cards_manifest,
        "git_commit": _git_head(HERE.parents[1]),
    }
    manifest_path = output_root / "i1_card_instances_manifest_v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("PHASE2_I1_CARD_MATERIALIZATION_PASS")
    print("PRIVATE_EVIDENCE_HASH_VERIFICATION_PASS")
    print("THREE_PUBLIC_I1_CARDS_WRITTEN_PASS")
    print("PUBLIC_I1_CARD_HASH_FREEZE_PASS")
    print("SAME_I1_FOR_M0_M1_PASS")
    print(f"public_output={output_root.resolve()}")
    print(f"private_audit={audit_root.resolve()}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize the frozen three-provider I1 cards")
    parser.add_argument(
        "--provider-root",
        type=Path,
        default=HERE / "results" / "i1_acquisition_v1" / "private",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase2_i1_provider_card_v2.json",
    )
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=HERE / "phase2_i1_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "i1_cards_v1" / "public",
    )
    args = parser.parse_args()
    materialize_frozen_i1_cards(
        provider_root=args.provider_root.resolve(),
        contract_path=args.contract.resolve(),
        evidence_manifest_path=args.evidence_manifest.resolve(),
        output_root=args.output.resolve(),
    )


if __name__ == "__main__":
    main()
