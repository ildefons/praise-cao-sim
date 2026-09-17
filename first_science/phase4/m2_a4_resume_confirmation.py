"""Repair an evaluated M2-A4 confirmation checkpoint and resume safely.

Two post-processing defects were found after the expensive simulations had
already completed:

1. The original confirmation runner writes derived compatibility columns back
   into its confirmation checkpoint. On rerun those collide with the same
   columns merged from the frozen previous-M2-A reference and pandas suffixes
   them, producing a KeyError.
2. The generic checkpoint evaluator expects provisional candidates to expose
   ``local_mse``. The final confirmed portfolio instead carries the same value
   forward as ``local_search_mse``, so replay can fail after its first simulated
   candidate while constructing the output row.

This recovery utility preserves all measured confirmation results, strips only
derived post-processing columns, patches the checkpoint evaluator in memory so
that it accepts either loss-column spelling, and then invokes the original main
routine. No confirmation simulation is repeated when all 15 candidates are
present. Replay remains the frozen independent 24000..24099 diagnostic and is
checkpointed after every completed candidate.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

import pandas as pd

import m2_a4_confirm_portfolio as original

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


def _loss_before_confirmation(rec: Any) -> float:
    """Return the frozen local-search loss from either dataframe schema."""
    if hasattr(rec, "local_mse"):
        return float(rec.local_mse)
    if hasattr(rec, "local_search_mse"):
        return float(rec.local_search_mse)
    raise RuntimeError(
        "candidate record contains neither local_mse nor local_search_mse"
    )


def _fixed_evaluate_with_checkpoint(
    *,
    candidates: pd.DataFrame,
    metadata_by_provider: dict[str, dict[str, object]],
    surfaces: dict[str, pd.DataFrame],
    trajectory_seeds: tuple[int, ...],
    canonical_ipt: float,
    execution_fraction: float,
    output_root: Path,
    stage: str,
) -> pd.DataFrame:
    """Original evaluator with replay-safe local-loss provenance handling."""
    results_path = output_root / f"m2_a4_{stage}_results.csv"
    if results_path.exists():
        results = pd.read_csv(results_path)
        completed = set(results["candidate_id"].astype(str))
        print(
            f"M2-A4 {stage} resume: {len(completed)} candidates already evaluated",
            flush=True,
        )
    else:
        results = pd.DataFrame()
        completed: set[str] = set()

    total = len(candidates)
    for ordinal, rec in enumerate(
        candidates.sort_values(["provider", "selection_order"]).itertuples(index=False),
        start=1,
    ):
        candidate_id = str(rec.candidate_id)
        if candidate_id in completed:
            continue
        provider = str(rec.provider)
        print(f"M2-A4 {stage} {ordinal}/{total} {candidate_id}", flush=True)

        metrics, simulated, comparison = original._simulate_and_score(
            metadata=metadata_by_provider[provider],
            public_surface=surfaces[provider],
            mean_service_time=float(rec.mean_service_time),
            cost_rate=float(rec.cost_rate),
            service_cv=float(rec.service_cv),
            trajectory_seeds=trajectory_seeds,
            canonical_ipt=float(canonical_ipt),
            execution_fraction=float(execution_fraction),
            quiet=True,
        )
        row = {
            "provider": provider,
            "candidate_id": candidate_id,
            "selection_order": int(rec.selection_order),
            "portfolio_role": str(rec.portfolio_role),
            "source_stage": str(rec.source_stage),
            "mean_service_time": float(rec.mean_service_time),
            "cost_rate": float(rec.cost_rate),
            "service_cv": float(rec.service_cv),
            "z_log_mu": float(rec.z_log_mu),
            "z_log_kappa": float(rec.z_log_kappa),
            "z_cv": float(rec.z_cv),
            "local_search_mse": _loss_before_confirmation(rec),
            f"{stage}_mse": float(metrics["mse"]),
            f"{stage}_rmse": float(metrics["rmse"]),
            f"{stage}_mae": float(metrics["mae"]),
            f"{stage}_bias": float(metrics["bias"]),
            f"{stage}_max_abs_error": float(metrics["max_abs_error"]),
        }

        candidate_dir = output_root / f"{stage}_surfaces" / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        simulated.to_csv(candidate_dir / f"{stage}_sigma_surface.csv", index=False)
        comparison.to_csv(candidate_dir / f"{stage}_comparison.csv", index=False)

        results = pd.concat([results, pd.DataFrame([row])], ignore_index=True)
        results = results.drop_duplicates("candidate_id", keep="last").sort_values(
            ["provider", "selection_order"], kind="mergesort"
        )
        results.to_csv(results_path, index=False)
        completed.add(candidate_id)

    return results.reset_index(drop=True)


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

    original._evaluate_with_checkpoint = _fixed_evaluate_with_checkpoint
    print("M2_A4_REPLAY_SAFE_EVALUATOR_PATCHED_IN_MEMORY")
    print("M2_A4_RESUMING_ORIGINAL_CONFIRMATION_MAIN")

    # Avoid forwarding wrapper-specific command-line arguments to argparse in the
    # original runner. The frozen default paths are intentionally retained.
    sys.argv = [str(HERE / "m2_a4_confirm_portfolio.py")]
    original.main()


if __name__ == "__main__":
    main()
