"""Simulator-independent tests for the frozen Phase-1 v2 confirmation contract."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pandas as pd

from run_phase1_v2_confirmation import (
    assess_v2_confirmation_summary,
    build_effective_v2_confirmation_configuration,
    validate_v2_confirmation_inputs,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _synthetic_wide(manifest: dict) -> pd.DataFrame:
    rows = []
    role_to_observed = {"latency": "latency", "cost": "cost", "mixed": "mixed"}
    for whitebox in manifest["whiteboxes"]:
        rows.append(
            {
                "region_id": whitebox["region_id"],
                "descriptive_role": role_to_observed[whitebox["selection_role"]],
                "area_rho_0p95": 0.98,
                "area_rho_0p975": 0.90,
                "area_rho_0p99": 0.80,
                "sigma_120_rho_0p95": 0.98,
                "sigma_240_rho_0p95": 0.99,
                "sigma_120_rho_0p99": 0.75,
                "sigma_240_rho_0p99": 0.80,
                "latency_failure_count": 10,
                "cost_failure_count": 10,
            }
        )
    return pd.DataFrame(rows)


def run_all_tests() -> None:
    here = Path(__file__).resolve().parent
    base = _load(here / "config_phase1_discovery_v1.json")
    protocol = _load(here / "config_phase1_v2_confirmation_v1.json")
    manifest = _load(here / "phase1_v2_ar_freeze_manifest_v1.json")

    validate_v2_confirmation_inputs(base, protocol, manifest)

    effective = build_effective_v2_confirmation_configuration(base, protocol)
    assert effective["confirmation"]["confirmation_seed_bank"] == list(range(7000, 7100))
    assert effective["phase1_v2_confirmation"]["selection_already_frozen"] is True
    assert effective["phase1_v2_confirmation"]["recalibration_forbidden"] is True

    assessed = assess_v2_confirmation_summary(_synthetic_wide(manifest), manifest, protocol)
    assert len(assessed) == 3
    assert assessed["fresh_confirmation_pass"].astype(bool).all()
    assert assessed["role_replication_pass"].astype(bool).all()
    assert assessed["nominal_health_pass"].astype(bool).all()
    assert assessed["stress_informativeness_pass"].astype(bool).all()

    nominal_fail = _synthetic_wide(manifest)
    nominal_fail.loc[0, "area_rho_0p95"] = 0.949
    assessed_nominal = assess_v2_confirmation_summary(nominal_fail, manifest, protocol)
    assert not bool(assessed_nominal.iloc[0]["fresh_confirmation_pass"])
    assert not bool(assessed_nominal.iloc[0]["nominal_health_pass"])

    stress_high_fail = _synthetic_wide(manifest)
    stress_high_fail.loc[1, "area_rho_0p99"] = 0.951
    assessed_stress_high = assess_v2_confirmation_summary(stress_high_fail, manifest, protocol)
    assert not bool(assessed_stress_high.iloc[1]["fresh_confirmation_pass"])
    assert not bool(assessed_stress_high.iloc[1]["stress_informativeness_pass"])

    stress_low_fail = _synthetic_wide(manifest)
    stress_low_fail.loc[2, "area_rho_0p99"] = 0.499
    assessed_stress_low = assess_v2_confirmation_summary(stress_low_fail, manifest, protocol)
    assert not bool(assessed_stress_low.iloc[2]["fresh_confirmation_pass"])
    assert not bool(assessed_stress_low.iloc[2]["stress_informativeness_pass"])

    role_fail = _synthetic_wide(manifest)
    role_fail.loc[0, "descriptive_role"] = "mixed"
    assessed_role = assess_v2_confirmation_summary(role_fail, manifest, protocol)
    assert not bool(assessed_role.iloc[0]["fresh_confirmation_pass"])
    assert not bool(assessed_role.iloc[0]["role_replication_pass"])

    bad_protocol = deepcopy(protocol)
    bad_protocol["reopen_selection_gate"] = True
    try:
        validate_v2_confirmation_inputs(base, bad_protocol, manifest)
    except ValueError:
        pass
    else:
        raise AssertionError("confirmation contract must reject reopening selection")

    bad_seeds = deepcopy(protocol)
    bad_seeds["seed_bank"] = list(range(7001, 7101))
    try:
        validate_v2_confirmation_inputs(base, bad_seeds, manifest)
    except ValueError:
        pass
    else:
        raise AssertionError("confirmation contract must reject seed-bank drift")

    print("PHASE1_V2_CONFIRMATION_CONTRACT_TESTS_PASS")


if __name__ == "__main__":
    run_all_tests()
