"""Materialize rho-conditioned I1 cards from disjoint frozen provider evidence.

This candidate correction uses two independent private corpora:

T_i^Gamma -> fit joint log(L,C) model -> A_i(rho_region)
T_i^sigma -> estimate sigma_i(A_i(rho_region), H; rho_query)

The region-construction corpus is the existing frozen Phase-2 evidence. The
sigma-estimation corpus is acquired separately under
config_phase2_i1_sigma_acquisition_v1.json. The two seed banks must be disjoint.
Neither private corpus is exposed to M0/M1; both methods receive the same public
I1 cards.
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
    write_i1_provider_card,
)
from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card
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


def _load_verified_ledgers(
    provider_root: Path,
    *,
    expected_hashes: dict[str, object],
    expected_rows: dict[str, object],
    expected_trajectories: dict[str, object],
    label: str,
) -> dict[str, pd.DataFrame]:
    ledgers: dict[str, pd.DataFrame] = {}
    for provider in PROVIDERS:
        path = provider_root / provider / "provider_request_ledgers.csv"
        if not path.exists():
            raise FileNotFoundError(f"missing {label} evidence: {path}")
        if sha256_file(path) != str(expected_hashes[provider]):
            raise RuntimeError(f"{provider} {label} evidence SHA-256 mismatch")
        ledger = pd.read_csv(path)
        if len(ledger) != int(expected_rows[provider]):
            raise RuntimeError(f"{provider} {label} evidence row-count mismatch")
        if int(ledger["trajectory"].nunique()) != int(
            expected_trajectories[provider]
        ):
            raise RuntimeError(
                f"{provider} {label} evidence trajectory-count mismatch"
            )
        ledgers[provider] = ledger
    return ledgers


def load_and_verify_region_provider_ledgers(
    provider_root: Path,
    evidence_manifest: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Load the frozen T_i^Gamma corpus used only to construct A_i(rho)."""
    if (
        evidence_manifest.get("status")
        != "FROZEN_PHASE2_I1_REGION_EVIDENCE_V1"
    ):
        raise ValueError("unexpected region-construction evidence freeze manifest")
    return _load_verified_ledgers(
        provider_root,
        expected_hashes=evidence_manifest["provider_corpus_sha256"],
        expected_rows=evidence_manifest["provider_rows"],
        expected_trajectories=evidence_manifest["provider_trajectories"],
        label="region-construction",
    )


def load_and_verify_sigma_provider_ledgers(
    provider_root: Path,
    acquisition_manifest: dict[str, Any],
    acquisition_contract: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Load the independent T_i^sigma corpus used only for sigma estimation."""
    if (
        acquisition_manifest.get("status")
        != "FROZEN_PHASE2_I1_PRIVATE_ACQUISITION_CORPUS_V1"
    ):
        raise ValueError("unexpected sigma-evidence acquisition manifest status")
    if acquisition_manifest.get("acquisition_config") != acquisition_contract:
        raise RuntimeError(
            "sigma-evidence acquisition manifest does not match the frozen contract"
        )
    if acquisition_contract.get("corpus_role") != "sigma_estimation_only":
        raise ValueError("sigma acquisition contract must be sigma_estimation_only")
    return _load_verified_ledgers(
        provider_root,
        expected_hashes=acquisition_manifest["provider_sha256"],
        expected_rows=acquisition_manifest["provider_rows"],
        expected_trajectories=acquisition_manifest["provider_trajectories"],
        label="sigma-estimation",
    )


def _declared_seed_bank(acquisition_config: dict[str, Any]) -> tuple[int, ...]:
    acquisition = acquisition_config["acquisition"]
    seed_start = int(acquisition["seed_start"])
    seed_end = int(acquisition["seed_end_inclusive"])
    seeds = tuple(range(seed_start, seed_end + 1))
    if len(seeds) != int(acquisition["n_trajectories"]):
        raise ValueError("declared acquisition seed range does not match n_trajectories")
    return seeds


def assert_disjoint_evidence_sources(
    region_acquisition_config: dict[str, Any],
    sigma_acquisition_manifest: dict[str, Any],
    sigma_acquisition_contract: dict[str, Any],
) -> None:
    """Enforce trajectory-level independence between Gamma and sigma evidence."""
    region_seeds = set(_declared_seed_bank(region_acquisition_config))
    sigma_declared = tuple(_declared_seed_bank(sigma_acquisition_contract))
    sigma_recorded = tuple(int(x) for x in sigma_acquisition_manifest["seed_bank"])
    if sigma_recorded != sigma_declared:
        raise RuntimeError("sigma-evidence recorded seed bank differs from its contract")
    overlap = region_seeds.intersection(sigma_recorded)
    if overlap:
        raise RuntimeError(
            "region-construction and sigma-estimation seed banks overlap: "
            + ", ".join(str(x) for x in sorted(overlap))
        )


def _assert_distinct_corpus_hashes(
    region_manifest: dict[str, Any],
    sigma_manifest: dict[str, Any],
) -> None:
    for provider in PROVIDERS:
        if str(region_manifest["provider_corpus_sha256"][provider]) == str(
            sigma_manifest["provider_sha256"][provider]
        ):
            raise RuntimeError(
                f"{provider} region and sigma corpora have identical hashes"
            )


def materialize_rho_conditioned_i1_cards(
    *,
    provider_root: Path,
    contract_path: Path,
    evidence_manifest_path: Path,
    region_acquisition_config_path: Path,
    sigma_provider_root: Path,
    sigma_acquisition_manifest_path: Path,
    sigma_acquisition_config_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    contract = _read_json(contract_path)
    if contract.get("status") != "PHASE2_I1_RHO_CONDITIONED_CONTRACT_V1":
        raise ValueError("unexpected rho-conditioned I1 contract")

    region_evidence_manifest = _read_json(evidence_manifest_path)
    region_acquisition_config = _read_json(region_acquisition_config_path)
    sigma_acquisition_manifest = _read_json(sigma_acquisition_manifest_path)
    sigma_acquisition_contract = _read_json(sigma_acquisition_config_path)

    assert_disjoint_evidence_sources(
        region_acquisition_config,
        sigma_acquisition_manifest,
        sigma_acquisition_contract,
    )
    _assert_distinct_corpus_hashes(
        region_evidence_manifest, sigma_acquisition_manifest
    )

    region_ledgers = load_and_verify_region_provider_ledgers(
        provider_root, region_evidence_manifest
    )
    sigma_ledgers = load_and_verify_sigma_provider_ledgers(
        sigma_provider_root,
        sigma_acquisition_manifest,
        sigma_acquisition_contract,
    )

    horizons = [float(v) for v in contract["H"]["values"]]
    region_rhos = [float(v) for v in contract["region_rho"]["values"]]
    query_rhos = [float(v) for v in contract["query_rho"]["values"]]
    workload = dict(contract["workload_contract"])
    gmm = dict(contract["joint_model"])
    stop_time = float(workload["horizon_max"])

    output_root.mkdir(parents=True, exist_ok=True)
    audit_root = output_root.parent / "private_audit"
    audit_root.mkdir(parents=True, exist_ok=True)

    cards_manifest: dict[str, Any] = {}
    for provider_index, provider in enumerate(PROVIDERS):
        provider_seed = int(gmm["random_state"]) + 1000 * provider_index

        # T_i^Gamma is used only here: region construction.
        regions, private_audit = derive_nested_rho_regions(
            region_ledgers[provider],
            region_rhos,
            max_components=int(gmm["max_components"]),
            model_samples=int(gmm["model_samples"]),
            random_state=provider_seed,
        )
        private_audit.to_csv(
            audit_root / f"{provider}_rho_conditioned_region_fit.csv",
            index=False,
        )

        # T_i^sigma is used only here: independent sigma estimation for regions
        # already fixed by T_i^Gamma.
        metadata, surface = build_i1_provider_card(
            provider_id=provider,
            private_provider_ledgers=sigma_ledgers[provider],
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
        metadata["rho_conditioned_regions"] = [dict(region) for region in regions]
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
            "region_and_sigma_evidence_are_trajectory_disjoint": True,
            "region_fit_evidence": "frozen_private_T_i^Gamma",
            "sigma_estimation_evidence": "independent_frozen_private_T_i^sigma",
        }
        metadata["query_semantics"] = (
            "exact_materialized_A_i_of_rho_region_H_rho_query_points_v2"
        )
        assert_public_i1_card_has_no_forbidden_information(metadata, surface)

        card_directory = output_root / provider
        card_json, surface_csv = write_i1_provider_card(
            metadata, surface, card_directory
        )
        reloaded_metadata, reloaded_surface = (
            load_rho_conditioned_i1_provider_card(card_directory)
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
            "fixed-one-A_i materialization only; Phase-1 benchmark remains unchanged"
        ),
        "schema": str(contract["schema"]),
        "information_technology": str(contract["information_technology"]),
        "same_materialized_I1_for_M0_and_M1": True,
        "region_evidence_verified_against_frozen_hashes": True,
        "sigma_evidence_verified_against_frozen_acquisition_manifest": True,
        "region_and_sigma_evidence_are_trajectory_disjoint": True,
        "phase1_whitebox_used_to_construct_I1": False,
        "H": horizons,
        "region_rho": region_rhos,
        "query_rho": query_rhos,
        "official_same_rho_diagonal": "rho_region=rho_query=rho_i",
        "region_evidence_manifest_sha256": sha256_file(evidence_manifest_path),
        "sigma_acquisition_manifest_sha256": sha256_file(
            sigma_acquisition_manifest_path
        ),
        "cards": cards_manifest,
        "git_commit": _git_head(HERE.parents[1]),
    }
    manifest_path = output_root / "i1_rho_conditioned_manifest_v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("PHASE2_RHO_CONDITIONED_I1_MATERIALIZATION_PASS")
    print("REGION_EVIDENCE_HASH_VERIFICATION_PASS")
    print("SIGMA_EVIDENCE_HASH_VERIFICATION_PASS")
    print("TRAJECTORY_DISJOINT_REGION_SIGMA_EVIDENCE_PASS")
    print("JOINT_LOG_GMM_REGION_EXTRACTION_PASS")
    print("NESTED_A_I_OF_RHO_PASS")
    print("PUBLIC_I1_RHO_REGION_CARTESIAN_SURFACE_PASS")
    print("SAME_CORRECTED_I1_FOR_M0_M1_PASS")
    print(f"public_output={output_root.resolve()}")
    print(f"private_audit={audit_root.resolve()}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize rho-conditioned I1 from disjoint region/sigma evidence"
    )
    parser.add_argument(
        "--provider-root",
        type=Path,
        default=HERE / "results" / "i1_acquisition_v1" / "private",
        help="frozen T_i^Gamma provider root used only to fit A_i(rho)",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=HERE / "config_phase2_i1_provider_card_v3_rho_conditioned.json",
    )
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=HERE / "phase2_i1_region_evidence_manifest_v1.json",
    )
    parser.add_argument(
        "--region-acquisition-config",
        type=Path,
        default=HERE / "config_phase2_i1_acquisition_v1.json",
    )
    parser.add_argument(
        "--sigma-provider-root",
        type=Path,
        default=HERE / "results" / "i1_sigma_acquisition_v1" / "private",
        help="independent T_i^sigma provider root used only for sigma estimation",
    )
    parser.add_argument(
        "--sigma-acquisition-manifest",
        type=Path,
        default=HERE
        / "results"
        / "i1_sigma_acquisition_v1"
        / "private"
        / "acquisition_manifest.json",
    )
    parser.add_argument(
        "--sigma-acquisition-config",
        type=Path,
        default=HERE / "config_phase2_i1_sigma_acquisition_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "i1_cards_v2_rho_conditioned" / "public",
    )
    args = parser.parse_args()
    materialize_rho_conditioned_i1_cards(
        provider_root=args.provider_root.resolve(),
        contract_path=args.contract.resolve(),
        evidence_manifest_path=args.evidence_manifest.resolve(),
        region_acquisition_config_path=args.region_acquisition_config.resolve(),
        sigma_provider_root=args.sigma_provider_root.resolve(),
        sigma_acquisition_manifest_path=args.sigma_acquisition_manifest.resolve(),
        sigma_acquisition_config_path=args.sigma_acquisition_config.resolve(),
        output_root=args.output.resolve(),
    )


if __name__ == "__main__":
    main()
