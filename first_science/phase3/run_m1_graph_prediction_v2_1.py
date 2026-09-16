"""Compatibility entry point for M1-v2 graph prediction after the native-control M0 fix.

The canonical corrected M0 contract intentionally keeps the frozen status
``FROZEN_PHASE3_M0_BASELINE_V2_SAME_RHO`` while recording the native control-
return latency correction in its provenance fields. Therefore no status override
is required here. This wrapper simply delegates to the canonical runner.
"""
from __future__ import annotations

import run_m1_graph_prediction_v2 as runner

if __name__ == "__main__":
    runner.main()
