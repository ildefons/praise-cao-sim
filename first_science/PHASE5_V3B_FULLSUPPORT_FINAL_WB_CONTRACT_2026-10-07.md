# Phase-5 V3b FULL343 final white-box execution contract

**Frozen:** 2026-10-07

The blind graph-prediction battery is complete. The battery-level manifest

`results/04_prediction_v3b_fullsupport/phase5_v3b_fullsupport_global_prediction_freeze_manifest.json`

contains 12 hash-frozen eligible prediction cells and the four previously frozen P2 Step-0 exclusions. The manifest explicitly records that the final white-box evidence had not been read when the prediction freeze was created.

This contract therefore unlocks the untouched final graph reference bank.

## Final reference

For each of the 12 eligible physical cells, run the frozen hidden provider world through the same native graph simulator and graph AST used throughout Phase 5.

Use exactly 1000 trajectories with seeds 54000 through 54999. The same seed bank is reused across eligible cells as common random numbers. One physical ledger is generated per provider-world x graph cell and is reused to score all 15 already-frozen Step-0 queries and all 49 horizons H=0,5,...,240 s.

No P2 graph is generated because all four P2 physical cells were already excluded by the prospective Step-0 gate.

For each frozen query and horizon, the white-box reference is

`sigma_WB(A,H;rho) = (# of trajectories with c_G(A,H) >= rho) / 1000`.

Uncertainty is reported using a 95% Wilson binomial interval over the 1000 trajectory-level Bernoulli outcomes.

## Irreversibility after opening WB

Opening this bank does not permit any change to provider reconstruction, M1 selection, M2 members or weights, M3 candidates/weights/allocation, Step-0 queries, graphs, or provider worlds.

If N=1000 later proves too noisy for a particular secondary analysis, any precision extension must be declared and executed as a separate follow-up experiment. It cannot silently alter the frozen final reference.

## Output namespace

The final reference is written to a new namespace:

`results/05_final_wb_v3b_fullsupport/`

The previous result namespaces remain immutable.

Evaluation is still locked until all 12 eligible final-WB cell manifests are frozen and a battery-level final-WB freeze manifest has been written.
