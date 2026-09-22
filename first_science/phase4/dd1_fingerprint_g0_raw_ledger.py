#!/usr/bin/env python3
"""DD-1: fingerprint the existing G0 raw top-level ledger with zero simulation.

The fingerprint uses request cost because queue waiting and network latency do
not enter the cost accumulator. Under the frozen native provider family,

    C_G = C_fixed + alpha * (I_A + I_B + I_C)
    alpha = COST_rate * execution_fraction_x / IPT

and for the symmetric family

    E[I_A + I_B + I_C] = 3D

independently of dispersion d. Therefore the observed mean request cost gives a
direct estimate of the hidden center instruction mean D:

    D_hat = (mean(C_G) - C_fixed) / (3 alpha)

This cleanly discriminates D300 from D330. The cost variance is also reported
as a secondary, less robust estimate of dispersion because end-of-run censoring
can bias the completed-request sample.

No simulator is imported or executed.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FIRST_SCIENCE = HERE.parent
PHASE1 = FIRST_SCIENCE / "phase1"

D300_ID = "D300000000_d0.200"
D330_ID = "D330000000_d0.150"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate(center: float, delta: float, *, alpha: float, cv: float, fixed_cost: float) -> dict[str, float]:
    means = [center * (1.0 - delta), center, center * (1.0 + delta)]
    return {
        "center_instruction_mean": center,
        "dispersion": delta,
        "expected_cost_mean": fixed_cost + alpha * sum(means),
        "expected_cost_std": alpha * cv * math.sqrt(sum(m * m for m in means)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DD-1 read-only physical fingerprint of the existing G0 ledger"
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=PHASE1
        / "results"
        / "phase1_v2_fresh_confirmation_v1"
        / "all_top_level_request_ledgers.csv",
    )
    parser.add_argument(
        "--phase1-config",
        type=Path,
        default=PHASE1 / "config_phase1_discovery_v1.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HERE / "results" / "dd1_g0_raw_ledger_fingerprint_v1",
    )
    args = parser.parse_args()

    ledger_path = args.ledger.resolve()
    if not ledger_path.exists():
        raise FileNotFoundError(f"G0 ledger not found: {ledger_path}")

    config = _read_json(args.phase1_config.resolve())
    family = dict(config["provider_family"])
    graph = dict(config["graph"])

    cv = float(family["instruction_cv"])
    ipt = float(family["effective_ipt"])
    cost_rate = float(family["cost_rate"])
    x = float(family["x"])
    alpha = cost_rate * x / ipt

    pre_instructions = float(graph["pre_instructions"])
    post_instructions = float(graph["post_instructions"])
    # Fpre/Fpost execute at full fraction 1.0.
    fixed_cost = cost_rate * (pre_instructions + post_instructions) / ipt

    candidates = {
        D300_ID: _candidate(300_000_000.0, 0.20, alpha=alpha, cv=cv, fixed_cost=fixed_cost),
        D330_ID: _candidate(330_000_000.0, 0.15, alpha=alpha, cv=cv, fixed_cost=fixed_cost),
    }

    frame = pd.read_csv(ledger_path)
    if "C" not in frame.columns:
        raise RuntimeError("G0 ledger has no C column")

    costs = pd.to_numeric(frame["C"], errors="coerce")
    finite_mask = np.isfinite(costs.to_numpy(dtype=float))
    finite = costs[finite_mask].astype(float)
    if len(finite) < 2:
        raise RuntimeError("G0 ledger has fewer than two finite cost observations")

    mean_cost = float(finite.mean())
    std_cost = float(finite.std(ddof=1))
    sem_naive = std_cost / math.sqrt(len(finite))
    center_hat = (mean_cost - fixed_cost) / (3.0 * alpha)

    # Secondary dispersion estimate from Var(sum gamma_i). It is diagnostic,
    # not the primary classifier, because incomplete end-of-run requests have
    # no observed C and can weakly bias the completed-request variance.
    normalized_second_moment = (
        std_cost * std_cost
        / (alpha * alpha * cv * cv * center_hat * center_hat)
    )
    delta_sq_hat = max(0.0, (normalized_second_moment - 3.0) / 2.0)
    delta_hat = math.sqrt(delta_sq_hat)

    distances = {}
    for cid, spec in candidates.items():
        # Primary discrimination on mean cost. Standardize by the empirical
        # naive SEM only to express how far apart the hypotheses are; do not
        # interpret this as an iid inferential z-score because requests within
        # trajectories need not be independent.
        distances[cid] = {
            "absolute_mean_cost_error": abs(mean_cost - spec["expected_cost_mean"]),
            "mean_cost_error_in_naive_SEM_units": abs(mean_cost - spec["expected_cost_mean"])
            / max(sem_naive, 1e-15),
            "absolute_std_cost_error": abs(std_cost - spec["expected_cost_std"]),
        }

    nearest_by_mean = min(
        distances,
        key=lambda cid: distances[cid]["absolute_mean_cost_error"],
    )

    completion_fraction = None
    if "completion" in frame.columns:
        completion = pd.to_numeric(frame["completion"], errors="coerce")
        completion_fraction = float(
            np.isfinite(completion.to_numpy(dtype=float)).mean()
        )
    elif "completed_by_stop" in frame.columns:
        completion_fraction = float(frame["completed_by_stop"].astype(bool).mean())

    seed_info = {}
    for column in ("seed", "trajectory_seed", "trajectory"):
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            unique = sorted(int(v) for v in values[np.isfinite(values)].unique())
            seed_info[column] = {
                "n_unique": len(unique),
                "minimum": unique[0] if unique else None,
                "maximum": unique[-1] if unique else None,
            }

    result = {
        "status": "DD1_G0_RAW_LEDGER_FINGERPRINT_COMPLETE",
        "scientific_role": "read-only provenance audit; zero simulation",
        "ledger": str(ledger_path),
        "n_rows": int(len(frame)),
        "n_finite_cost_rows": int(len(finite)),
        "completion_fraction": completion_fraction,
        "seed_or_trajectory_columns": seed_info,
        "frozen_cost_model": {
            "instruction_cv": cv,
            "effective_IPT": ipt,
            "cost_rate": cost_rate,
            "provider_execution_fraction_x": x,
            "alpha_cost_per_instruction": alpha,
            "fixed_Fpre_Fpost_cost": fixed_cost,
        },
        "observed_cost_fingerprint": {
            "mean": mean_cost,
            "std": std_cost,
            "naive_SEM_note_not_iid_inference": sem_naive,
            "estimated_center_instruction_mean": center_hat,
            "secondary_estimated_dispersion": delta_hat,
        },
        "candidate_expectations": candidates,
        "candidate_distances": distances,
        "nearest_candidate_by_mean_cost": nearest_by_mean,
        "primary_conclusion": (
            "G0 ledger is consistent with D300 center"
            if nearest_by_mean == D300_ID
            else "G0 ledger is closer to D330 center"
        ),
        "caution": (
            "Mean cost is the primary fingerprint. The dispersion estimate from "
            "cost variance is secondary because top-level C is observed only for "
            "requests completed by simulation stop."
        ),
    }

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "dd1_g0_raw_ledger_fingerprint.json"
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    rows = []
    for cid, spec in candidates.items():
        rows.append(
            {
                "candidate": cid,
                **spec,
                **distances[cid],
            }
        )
    csv_path = output / "dd1_candidate_comparison.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    print("DD1_G0_RAW_LEDGER_FINGERPRINT_COMPLETE")
    print(f"ledger_rows={len(frame)} finite_cost_rows={len(finite)}")
    if completion_fraction is not None:
        print(f"completion_fraction={completion_fraction:.6f}")
    print(f"observed_cost_mean={mean_cost:.9f}")
    print(f"observed_cost_std={std_cost:.9f}")
    print(f"estimated_center_instruction_mean={center_hat:.3f}")
    print(f"secondary_estimated_dispersion={delta_hat:.6f}")
    print("")
    print("CANDIDATE_EXPECTATIONS")
    for cid, spec in candidates.items():
        print(
            f"{cid}: expected_mean={spec['expected_cost_mean']:.9f} "
            f"expected_std={spec['expected_cost_std']:.9f} "
            f"|mean_error|={distances[cid]['absolute_mean_cost_error']:.9f}"
        )
    print("")
    print(f"nearest_candidate_by_mean_cost={nearest_by_mean}")
    print(f"primary_conclusion={result['primary_conclusion']}")
    print(f"result={json_path}")


if __name__ == "__main__":
    main()
