"""Compatibility entry point for M1-v2 graph prediction after the native-control M0 fix.

The graph-prediction implementation remains ``run_m1_graph_prediction_v2``.
The only compatibility change here is the expected status string of the
canonical corrected M0 contract.  The canonical file name is unchanged:
``config_phase3_m0_contract_v1.json``.
"""
from __future__ import annotations

import run_m1_graph_prediction_v2 as runner

runner.EXPECTED_M0_CONTRACT_STATUS = (
    "FROZEN_PHASE3_M0_BASELINE_V2_1_NATIVE_CONTROL_RETURN_FIX"
)

if __name__ == "__main__":
    runner.main()
