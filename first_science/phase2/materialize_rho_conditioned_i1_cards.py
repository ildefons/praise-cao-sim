"""Materialize rho-conditioned I1 cards from the frozen provider evidence.

This is a versioned candidate correction to the historical one-A_i Phase-2
materialization. It does not overwrite i1_cards_v1.

Private provider evidence is hash-verified exactly as before. For each provider,
rho-conditioned regions A_i(rho_region) are derived by i1_rho_conditioned_region,
then the existing generic I1 card builder materializes the complete Cartesian
surface

    sigma_i(A_i(rho_region), H; rho_query)

over the predeclared region-content and query-rho supports. The official M0
same-rho diagonal later uses rho_region = rho_query = rho_i.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from i1_provider_card import (
    assert_public_i1_card_has_no_forbidden_information,
    build_i1_provider_card,
    load_i1_provider_card,
    write_i1_provider_card,
)
from i1_rho_conditioned_region import derive_nested_rho_regions

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
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
        ).strip()
    except Exception:
        return None


def load_and_verify_private_provider_ledgers(
    provider_root: Path,
    evidence_manifest: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Load T_i only after checking the existing frozen evidence hashes."""
    ledgers: dict[str, pd.DataFrame] = {}
    expected_hashes = evidence_manifest["provider_corpus_sha256"]
    expected_rows = evidence_manifest["provider_rows"]
    expected_trajectories = evidence_manifest["provider_trajectories"]
    for provider in PROVIDERS:
        path = provider_root / provider / "provider_request_ledgers.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing frozen provider evidence: {path}")
        if sha256_file(path) != str(expected_hashes[provider]):
            raise RuntimeError(f"{provider} evidence SHA-256 mismatch")
        ledger = pd.read_csv(path)
        if len(ledger) != int(expected_rows[provider]):
            raise RuntimeError(f"{provider} evidence row-count mismatch")
        if int(ledger["trajectory"].nunique()) != int(
            expected_trajectories[provider]
        ):
            raise RuntimeError(f"{provider} evidence trajectory-count mismatch")
        ledgers[provider] = ledger
    return ledgers


def materialize_rho_conditioned_i1_cards(
    *,
    provider_root: Path,
    contract_path: Path,
    evidence_manifest_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    contract = _read_json(contract_path)
    if contract.get("status") != "PHASE2_I1_RHO_CONDITIONED_CONTRACT_V1":
        raise ValueError("unexpected rho-conditioned I1 contract")
    evidence_manifest = _read_json(evidence_manifest_path)
    if evidence_manifest.get("status") != "FROZEN_PHASE2_I1_V1":
        raise ValueError("unexpected provider-evidence freeze manifest")

    horizons = [float(v) for v in contract["H"]["values"]]
    region_rhos = [float(v) for v in contract["region_rho"]["values"]]
    query_rhos = [float(v) for v in contract["query_rho"]["values"]]
    workload = dict(contract["workload_contract"])
    gmm = dict(contract["joint_model"])
    stop_time = float(workload["horizon_max"])

    ledgers = load_and_verify_private_provider_ledgers(
        provider_root, evidence_manifest
    )
    output_root.mkdir(parents=True, exist_ok=True)
    audit_root = output_root.parent / "private_audit"
    audit_root.mkdir(parents=True, exist_ok=True)

    cards_manifest: dict[str, Any] = {}
    for provider_index, provider in enumerate(PROVIDERS):
        provider_seed = int(gmm["random_state"]) + 1000 * provider_index
        regions, private_audit = derive_nested_rho_regions(
            ledgers[provider],
            region_rhos,
            max_components=int(gmm["max_components"]),
            model_samples=int(gmm["model_samples"]),
            random_state=provider_seed,
        )
        private_audit.to_csv(
            audit_root / f"{provider}_rho_conditioned_region_fit.csv",
            index=False,
        )

        # The existing card builder is already generic over multiple exact A_i.
        # Materialize all (A_i(rho_region), rho_query, H) combinations so the
        # representation remains explicit and future methods can query exact
        # off-diagonal points without private evidence access.
        metadata, surface = build_i1_provider_card(
            provider_id=provider,
            private_provider_ledgers=ledgers[provider],
            local_regions=regions,
            rho_values=query_rhos,
            horizons=horizons,
            stop_time=stop_time,
            workload_contract={
                "period": float(workload["period"]),
                "accounting_origin": float(workload["accounting_origin"]),
                "horizon_max": stop_time,
            },
        )

        region_rho_by_id = {
            str(region["region_id"]): float(region["region_rho"])
            for region in regions
        }
        surface.insert(
            surface.columns.get_loc("region_id") + 1,
            "region_rho",
            surface["region_id"].map(region_rho_by_id).astype(float),
        )
        metadata["schema"] = str(contract["schema"])
        metadata["information_technology"] = str(
            contract["information_technology"]
        )
        metadata["card_instance"] = (
            "I1_i=({A_i(rho_region)},W_i,R_region,R_query,"
            "{sigma_i(A_i(rho_region),H;rho_query)})"
        )
        metadata["rho_conditioned_regions"] = [
            dict(region) for region in regions
        ]
        metadata["supported_region_rho_values"] = region_rhos
        metadata["supported_query_rho_values"] = query_rhos
        metadata["construction"] = {
            "status": "JOINT_LOG_GMM_MIN_AREA_RHO_REGION_V1",
            "joint_coordinates": ["log_L", "log_C"],
            "quality_rule": "constant_Q_is_preserved_exactly",
            "component_selection": "minimum_BIC",
            "max_components": int(gmm["max_components"]),
            "covariance_type": "full",
            "model_samples": int(gmm["model_samples"]),
            "nested_regions": True,
            "finite_region_rho_requires_rho_less_than_1": True,
            "phase1_whitebox_used": False,
        }
        metadata["query_semantics"] = (
            "exact_materialized_A_i_of_rho_region_H_rho_query_points_v2"
        )
        assert_public_i1_card_has_no_forbidden_information(metadata, surface)

        card_directory = output_root / provider
        card_json, surface_csv = write_i1_provider_card(
            metadata, surface, card_directory
        )
        reloaded_metadata, reloaded_surface = load_i1_provider_card(
            card_directory
        )
        expected_points = len(regions) * len(query_rhos) * len(horizons)
        if str(reloaded_metadata["provider_id"]) != provider:
            raise RuntimeError(f"{provider} public card reload mismatch")
        if len(reloaded_surface) != expected_points:
            raise RuntimeError(
                f"{provider} expected {expected_points} rho-conditioned surface "
                f"points, found {len(reloaded_surface)}"
            )
        if "region_rho" not in reloaded_surface.columns:
            raise RuntimeError(f"{provider} public card lost region_rho on reload")

        cards_manifest[provider] = {
            "directory": provider,
            "rho_conditioned_regions": [dict(region) for region in regions],
            "n_surface_points": int(len(surface)),
            "card_json_sha256": sha256_file(card_json),
            "sigma_surface_sha256": sha256_file(surface_csv),
        }

    manifest: dict[str, Any] = {
        "status": "PHASE2_I1_RHO_CONDITIONED_CARD_INSTANCES_V1",
        "scientific_status": "candidate_correction_pending_result_review",
        "supersedes_after_validation": (
            "fixed-one-A_i materialization only; private provider evidence and "
            "Phase-1 benchmark remain unchanged"
        ),
        "schema": str(contract["schema"]),
        "information_technology": str(contract["information_technology"]),
        "same_materialized_I1_for_M0_and_M1": True,
        "private_evidence_verified_against_frozen_hashes": True,
        "phase1_whitebox_used_to_construct_I1": False,
        "H": horizons,
        "region_rho": region_rhos,
        "query_rho": query_rhos,
        "official_same_rho_diagonal": "rho_region=rho_query=rho_i",
        "cards": cards_manifest,
        "git_commit": _git_head(HERE.parents[1]),
    }
    manifest_path = output_root / "i1_rho_conditioned_manifest_v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("PHASE2_RHO_CONDITIONED_I1_MATERIALIZATION_PASS")
    print("PRIVATE_EVIDENCE_HASH_VERIFICATION_PASS")
    print("JOINT_LOG_GMM_REGION_EXTRACTION_PASS")
    print("NESTED_A_I_OF_RHO_PASS")
    print("PUBLIC_I1_RHO_REGION_CARTESIAN_SURFACE_PASS")
    print("SAME_CORRECTED_I1_FOR_M0_M1_PASS")
    print(f"public_output={output_root.resolve()}")
    print(f"private_audit={audit_root.resolve()}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize rho-conditioned joint-GMM I1 cards"
    )
    parser.add_argument(
        "--provider-root",
        type=Path,
        default=HERE / "results" / "i1_acquisition_v1" / "private",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE
        / "config_phase2_i1_provider_card_v3_rho_conditioned.json",
    )
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=HERE / "phase2_i1_freeze_manifest_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE
        / "results"
        / "i1_cards_v2_rho_conditioned"
        / "public",
    )
    args = parser.parse_args()
    materialize_rho_conditioned_i1_cards(
        provider_root=args.provider_root.resolve(),
        contract_path=args.contract.resolve(),
        evidence_manifest_path=args.evidence_manifest.resolve(),
        output_root=args.output.resolve(),
    )


if __name__ == "__main__":
    main()
