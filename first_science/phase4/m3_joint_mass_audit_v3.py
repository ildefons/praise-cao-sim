"""Audit exact joint mass of the frozen M3-v3 provider-weight product.

No simulation and no graph/WB reads. This enumerates the finite 48^3 weighted
joint support implied by the public-I1-selected lambda and reports how many
joint hypotheses are needed to cover prescribed cumulative mass levels.

For a top-mass truncation with retained mass m, the worst-case absolute error
of the renormalized mixture mean for any sigma in [0,1] is <= 1-m.
"""
from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
THRESHOLDS = (0.50, 0.90, 0.95, 0.99, 0.995, 0.999, 0.9999)


def _expected_unique(p: np.ndarray, k: int) -> float:
    p = np.asarray(p, dtype=float)
    return float(np.sum(1.0 - np.power(1.0 - p, int(k))))


def _count_for_mass(sorted_p: np.ndarray, target: float) -> int:
    return int(np.searchsorted(np.cumsum(sorted_p), float(target), side="left") + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit M3-v3 exact joint weight mass")
    parser.add_argument(
        "--weights",
        type=Path,
        default=HERE / "results" / "m3_lambda_cv_v3" / "m3_v3_provider_weights.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "results" / "m3_lambda_cv_v3" / "m3_v3_joint_mass_audit.csv",
    )
    args = parser.parse_args()

    weights = pd.read_csv(args.weights.resolve())
    tables = {}
    for provider in PROVIDERS:
        g = (
            weights[weights["provider"].astype(str) == provider]
            .sort_values("weight_v3", ascending=False)
            .reset_index(drop=True)
        )
        if len(g) != 48:
            raise RuntimeError(f"{provider}: expected 48 weights, found {len(g)}")
        if not np.isclose(g["weight_v3"].sum(), 1.0, atol=1e-10):
            raise RuntimeError(f"{provider}: weights do not sum to one")
        tables[provider] = g

    rows = []
    A, B, C = tables["ProviderA"], tables["ProviderB"], tables["ProviderC"]
    for ia, ib, ic in product(range(48), range(48), range(48)):
        wa = float(A.iloc[ia]["weight_v3"])
        wb = float(B.iloc[ib]["weight_v3"])
        wc = float(C.iloc[ic]["weight_v3"])
        rows.append(
            {
                "joint_weight": wa * wb * wc,
                "A": str(A.iloc[ia]["candidate_id"]),
                "B": str(B.iloc[ib]["candidate_id"]),
                "C": str(C.iloc[ic]["candidate_id"]),
                "wA": wa,
                "wB": wb,
                "wC": wc,
            }
        )

    joint = pd.DataFrame(rows).sort_values(
        "joint_weight", ascending=False, kind="mergesort"
    ).reset_index(drop=True)
    joint["rank"] = np.arange(1, len(joint) + 1)
    joint["cumulative_mass"] = joint["joint_weight"].cumsum()

    out = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    joint.to_csv(out, index=False)

    p = joint["joint_weight"].to_numpy(float)
    if not np.isclose(p.sum(), 1.0, atol=1e-10):
        raise RuntimeError(f"joint mass sums to {p.sum()}")

    print("M3_V3_EXACT_JOINT_MASS_AUDIT")
    print(f"support={len(joint)} exact_mass={p.sum():.12f}")
    print(
        f"expected_unique_K100={_expected_unique(p,100):.4f} "
        f"expected_unique_K200={_expected_unique(p,200):.4f}"
    )

    summary = []
    for target in THRESHOLDS:
        n = _count_for_mass(p, target)
        retained = float(joint.iloc[n - 1]["cumulative_mass"])
        omitted = 1.0 - retained
        summary.append(
            {
                "target_mass": target,
                "n_joint_hypotheses": n,
                "retained_mass": retained,
                "omitted_mass": omitted,
                "worst_case_abs_sigma_error_bound_if_renormalized": omitted,
            }
        )
    summary_df = pd.DataFrame(summary)

    print("\nMASS_COVERAGE")
    print(summary_df.to_string(index=False))
    print("\nTOP_20_JOINT_HYPOTHESES")
    print(
        joint[
            ["rank", "joint_weight", "cumulative_mass", "A", "B", "C"]
        ].head(20).to_string(index=False)
    )
    print("\nM3_V3_EXACT_JOINT_MASS_AUDIT_COMPLETE")
    print(f"output={out}")


if __name__ == "__main__":
    main()
