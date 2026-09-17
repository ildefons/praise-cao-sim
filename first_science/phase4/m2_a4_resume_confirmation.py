"""Repair an already-evaluated M2-A4 confirmation checkpoint and resume safely.

The original confirmation runner writes derived compatibility columns back into
its checkpoint after the 15 confirmation simulations. On a later rerun those
columns can collide with the same columns merged from the frozen previous-M2-A
reference, producing pandas ``_x``/``_y`` suffixes and a KeyError. This recovery
utility preserves the measured confirmation results, strips only derived
post-processing columns, and then invokes the unchanged confirmation runner.

No confirmation simulation is repeated when all 15 candidate ids are already
present. Replay, if the frozen gate passes, is still performed by the original
runner and remains checkpointed normally.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "results" / "m2_a4_portfolio_confirmation_v1"
CHECKPOINT_NAME = "m2_a4_confirmation_results.csv"
EXPECTED_CONFIRMATION_COUNT = 15

RAW_COLUMNS = [
    "provider",
    "candidate_id",
    "selection_order",
    "portfolio_role",
    "source_stage",
    "mean_service_time",
    "cost_rate",
    "service_cv",
    "z_log_mu",
    "z_log_kappa",
    "z_cv",
    "local_search_mse",
    "confirmation_mse",
    "confirmation_rmse",
    "confirmation_mae",
    "confirmation_bias",
    "confirmation_max_abs_error",
]


def main() -> None:
    output = DEFAULT_OUTPUT
    checkpoint = output / CHECKPOINT_NAME
    if not checkpoint.exists():
        raise FileNotFoundError(f"confirmation checkpoint not found: {checkpoint}")

    frame = pd.read_csv(checkpoint)
    missing = [column for column in RAW_COLUMNS if column not in frame.columns]
    if missing:
        raise RuntimeError(
            "confirmation checkpoint is missing raw measured columns: "
            + ", ".join(missing)
        )
    if frame["candidate_id"].astype(str).duplicated().any():
        raise RuntimeError("confirmation checkpoint contains duplicate candidate ids")
    if len(frame) != EXPECTED_CONFIRMATION_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_CONFIRMATION_COUNT} completed confirmation candidates, "
            f"found {len(frame)}; refusing recovery so incomplete simulations are not hidden"
        )

    backup = output / "m2_a4_confirmation_results_pre_resume_fix.csv"
    if not backup.exists():
        shutil.copy2(checkpoint, backup)

    raw = frame[RAW_COLUMNS].copy().sort_values(
        ["provider", "selection_order"], kind="mergesort"
    )
    raw.to_csv(checkpoint, index=False)
    print("M2_A4_CONFIRMATION_CHECKPOINT_RECOVERED_NO_SIMULATION")
    print(f"candidates_preserved={len(raw)}")
    print(f"backup={backup}")

    command = [sys.executable, str(HERE / "m2_a4_confirm_portfolio.py")]
    print("M2_A4_RESUMING_ORIGINAL_CONFIRMATION_RUNNER")
    subprocess.run(command, cwd=HERE, check=True)


if __name__ == "__main__":
    main()
