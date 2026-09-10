"""Structural guards for the preliminary I1-M0 consolidation pipeline."""
from __future__ import annotations

import inspect
from pathlib import Path

from consolidate_preliminary_i1_m0_results import (
    PRELIMINARY_RHOS,
    consolidate_preliminary_results,
)

HERE = Path(__file__).resolve().parent


def main() -> None:
    assert PRELIMINARY_RHOS == (0.95, 0.975, 0.9833333333333333, 0.99)
    signature = inspect.signature(consolidate_preliminary_results)
    assert "i1_card_root" in signature.parameters
    assert "i1_card_manifest_path" in signature.parameters
    assert "provider_root" not in signature.parameters

    diagnostic_source = (HERE / "diagnose_real_wb_vs_i1_m0.py").read_text(encoding="utf-8")
    consolidation_source = (HERE / "consolidate_preliminary_i1_m0_results.py").read_text(encoding="utf-8")
    for source in (diagnostic_source, consolidation_source):
        assert "provider_request_ledgers.csv" not in source
        assert "derive_local_regions_from_traces" not in source
    assert "PRELIMINARY_I1_M0_DIAGNOSTIC_V1" in consolidation_source
    assert "preliminary_not_final_evaluation" in consolidation_source
    assert "phase3_reads_private_provider_traces" in consolidation_source

    print("PHASE3_PRELIMINARY_I1_M0_CONSOLIDATION_CONTRACT_TESTS_PASS")
    print("FOUR_RHO_SWEEP_FROZEN_PASS")
    print("PHASE3_PUBLIC_I1_ONLY_CONSOLIDATION_PASS")
    print("PRELIMINARY_NOT_FINAL_STATUS_GUARD_PASS")


if __name__ == "__main__":
    main()
