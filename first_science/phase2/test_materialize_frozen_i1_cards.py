"""Simulator-independent tests for frozen I1 card materialization helpers."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd

from materialize_frozen_i1_cards import (
    load_and_verify_private_provider_ledgers,
    sha256_file,
)

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")


def _write_ledger(path: Path, provider_offset: float) -> None:
    rows = []
    for trajectory in range(2):
        for request_id in range(3):
            emission = float(request_id)
            latency = provider_offset + 0.1 + 0.01 * request_id
            completion = emission + latency
            rows.append(
                {
                    "trajectory": trajectory,
                    "request_id": request_id,
                    "emission": emission,
                    "completion": completion,
                    "L": latency,
                    "C": 3.0 * latency,
                    "Q": 0.5,
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        expected_hashes = {}
        expected_rows = {}
        expected_trajectories = {}
        for index, provider in enumerate(PROVIDERS):
            path = root / provider / "provider_request_ledgers.csv"
            _write_ledger(path, 0.01 * index)
            expected_hashes[provider] = sha256_file(path)
            expected_rows[provider] = 6
            expected_trajectories[provider] = 2

        manifest = {
            "provider_corpus_sha256": expected_hashes,
            "provider_rows": expected_rows,
            "provider_trajectories": expected_trajectories,
        }
        ledgers = load_and_verify_private_provider_ledgers(root, manifest)
        assert set(ledgers) == set(PROVIDERS)
        assert all(len(frame) == 6 for frame in ledgers.values())

        # Any mutation of private evidence must be rejected before card materialization.
        corrupted = root / "ProviderB" / "provider_request_ledgers.csv"
        corrupted.write_text(corrupted.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        try:
            load_and_verify_private_provider_ledgers(root, manifest)
        except RuntimeError as error:
            assert "SHA-256 mismatch" in str(error)
        else:
            raise AssertionError("mutated private provider evidence was accepted")

        sample = root / "sample.txt"
        sample.write_text("PRAISE-I1", encoding="utf-8")
        expected = hashlib.sha256(b"PRAISE-I1").hexdigest()
        assert sha256_file(sample) == expected

    print("PHASE2_I1_MATERIALIZATION_HELPER_TESTS_PASS")
    print("PRIVATE_EVIDENCE_HASH_GUARD_PASS")
    print("DETERMINISTIC_SHA256_HELPER_PASS")


if __name__ == "__main__":
    main()
