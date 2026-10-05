"""Read-only audit of the completed official Phase-5 V2 I1 stage.

The audit verifies all four world freeze manifests, config hashes, evidence
manifests, public-card hashes, public-card reload/information firewall, exact
surface size, and the declared N=100+100 evidence split.  It also reports the
measured acquisition wall times recorded in the private evidence manifests.

This script never writes scientific evidence and never opens graph-WB data.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PHASE2 = HERE.parent / "phase2"
if str(PHASE2) not in sys.path:
    sys.path.insert(0, str(PHASE2))

from i1_rho_conditioned_card import load_rho_conditioned_i1_provider_card  # noqa: E402
from i1_provider_card import assert_public_i1_card_has_no_forbidden_information  # noqa: E402

from phase5_runtime_v2 import (
    canonical_provider_world_ids,
    load_phase5_contracts,
    read_json,
    sha256_file,
)

DEFAULT_ROOT = HERE / "results" / "01_i1"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def audit_world(root: Path, world_id: str, contracts) -> dict[str, object]:
    world_root = root / world_id
    freeze_path = world_root / "i1_freeze_manifest.json"
    if not freeze_path.is_file():
        raise FileNotFoundError(freeze_path)
    freeze = read_json(freeze_path)
    if freeze.get("status") != "FROZEN_PHASE5_I1_COMPLETE_V2":
        raise RuntimeError(
            f"{world_id}: unexpected freeze status {freeze.get('status')!r}"
        )

    hashes = contracts.hashes
    expected_hash_keys = {
        "battery_config_sha256": hashes["battery"],
        "seed_registry_sha256": hashes["seeds"],
        "method_contract_sha256": hashes["methods"],
        "analysis_contract_sha256": hashes["analysis"],
        "execution_contract_sha256": hashes["execution"],
    }
    for key, expected in expected_hash_keys.items():
        if freeze.get(key) != expected:
            raise RuntimeError(
                f"{world_id}: {key} mismatch; evidence was not frozen "
                "against the current V2 contracts"
            )

    region_path = world_root / "i1_region_evidence_manifest.json"
    sigma_path = world_root / "i1_sigma_evidence_manifest.json"
    public_manifest_path = (
        world_root / "public" / "i1_rho_conditioned_manifest_v2.json"
    )
    for path in (region_path, sigma_path, public_manifest_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    region = read_json(region_path)
    sigma = read_json(sigma_path)
    public = read_json(public_manifest_path)

    if region.get("status") != "FROZEN_PHASE5_I1_REGION_EVIDENCE_V2":
        raise RuntimeError(f"{world_id}: invalid region-evidence status")
    if sigma.get("status") != "FROZEN_PHASE5_I1_SIGMA_EVIDENCE_V2":
        raise RuntimeError(f"{world_id}: invalid sigma-evidence status")
    if int(region.get("n_trajectories", -1)) != 100:
        raise RuntimeError(f"{world_id}: region N is not 100")
    if int(sigma.get("n_trajectories", -1)) != 100:
        raise RuntimeError(f"{world_id}: sigma N is not 100")
    if set(map(int, region["seed_bank_private"])).intersection(
        set(map(int, sigma["seed_bank_private"]))
    ):
        raise RuntimeError(f"{world_id}: I1 region/sigma seed overlap")

    if public.get("status") != "FROZEN_PHASE5_PUBLIC_I1_CARDS_V2":
        raise RuntimeError(f"{world_id}: invalid public-I1 status")
    if not bool(public.get("same_cards_reused_across_all_four_graphs")):
        raise RuntimeError(f"{world_id}: graph-reuse flag is false")
    if bool(public.get("public_card_payloads_contain_hidden_world_parameters")):
        raise RuntimeError(f"{world_id}: public-card hidden-world leak flag is true")

    n_h = len(public["H"])
    n_region_rho = len(public["region_rho"])
    n_query_rho = len(public["query_rho"])
    expected_points = n_h * n_region_rho * n_query_rho
    if expected_points != 49 * 5 * 5:
        raise RuntimeError(f"{world_id}: unexpected public support size")

    for provider in PROVIDERS:
        rec = public["cards"][provider]
        card_dir = world_root / "public" / provider
        card_path = card_dir / "card.json"
        surface_path = card_dir / "sigma_surface.csv"
        if sha256_file(card_path) != rec["card_json_sha256"]:
            raise RuntimeError(f"{world_id}/{provider}: card hash mismatch")
        if sha256_file(surface_path) != rec["sigma_surface_sha256"]:
            raise RuntimeError(f"{world_id}/{provider}: surface hash mismatch")
        metadata, surface = load_rho_conditioned_i1_provider_card(card_dir)
        assert_public_i1_card_has_no_forbidden_information(metadata, surface)
        if len(surface) != expected_points:
            raise RuntimeError(
                f"{world_id}/{provider}: expected {expected_points} points, "
                f"found {len(surface)}"
            )
        if set(surface["n_trajectories"].astype(int)) != {100}:
            raise RuntimeError(
                f"{world_id}/{provider}: public sigma N is not uniformly 100"
            )

    region_seconds = float(region.get("python_wall_seconds", 0.0))
    sigma_seconds = float(sigma.get("python_wall_seconds", 0.0))
    return {
        "world": world_id,
        "status": "PASS",
        "region_seconds": region_seconds,
        "sigma_seconds": sigma_seconds,
        "acquisition_seconds": region_seconds + sigma_seconds,
        "acquisition_minutes": (region_seconds + sigma_seconds) / 60.0,
        "public_points_per_provider": expected_points,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only audit of frozen Phase-5 V2 I1 evidence"
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()

    contracts = load_phase5_contracts(HERE)
    rows = [
        audit_world(args.root.resolve(), world_id, contracts)
        for world_id in canonical_provider_world_ids(contracts)
    ]
    table = pd.DataFrame(rows)
    print("PHASE5_I1_V2_AUDIT_PASS")
    print(table.to_string(index=False))
    total = float(table["acquisition_seconds"].sum())
    print(
        f"total_recorded_acquisition_wall={total/60.0:.1f} min "
        "(sum of sequential region+sigma acquisition timers; "
        "card materialization overhead excluded)"
    )


if __name__ == "__main__":
    main()
