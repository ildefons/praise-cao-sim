"""Read-only diagnostic for provider-specific Phase-2 I1 admissibility regions.

Scientific purpose
------------------
A concrete I1 card contains a provider-local admissibility region A_i.  The
previous equal cost split made the same local cost threshold apply to all three
heterogeneous providers and produced degenerate cards.  This diagnostic tests a
more principled, method-independent construction using only:

* the already frozen global A_G thresholds and public graph structure; and
* the already frozen provider-local Phase-2 acquisition ledgers.

No Phase-1 sigma outcomes, no final confirmation traces, and no M0/M1 outputs
are read.

Candidate policy
----------------
For each frozen global A_G:

1. latency (max composition): give every branch the maximal structurally
   admissible local latency threshold;
2. quality (min composition): copy the global quality floor;
3. cost (sum composition): allocate the residual global cost budget so that all
   providers receive the same empirical cost percentile.  The common percentile
   p* solves

       sum_i Q_i^C(p*) = C_G,max - C_fixed,

   where Q_i^C is the empirical provider-local cost quantile from the frozen
   acquisition ledger.

The equal-percentile rule uses traces only where the additive structural rule
leaves a genuine allocation degree of freedom.  It does not inspect sigma_i,
choose rho, or optimize a composition result.

This script only prints candidate A_i values.  It does not overwrite the current
query declaration or materialized cards.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1"
ACQUISITION = HERE / "results" / "i1_acquisition_v1" / "private"
PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
TOL = 1e-12


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def yafs_single_link_latency(message_bytes: float, bandwidth_mbps: float, propagation: float) -> float:
    return float(message_bytes) / (float(bandwidth_mbps) * 1_000_000.0) + float(propagation)


def derive_public_fixed_terms(configuration: Mapping[str, object]) -> dict[str, object]:
    """Derive deterministic public latency/cost terms from the frozen graph."""
    graph = configuration["graph"]
    topology = configuration["topology"]
    provider_family = configuration["provider_family"]

    ipt = float(provider_family["effective_ipt"])
    cost_rate = float(provider_family["cost_rate"])
    pre_service = float(graph["pre_instructions"]) / ipt
    post_service = float(graph["post_instructions"]) / ipt
    bw = float(topology["network_bw_mbps"])
    pr = float(topology["network_pr"])

    root_network = yafs_single_link_latency(topology["request_bytes"], bw, pr)
    branch_network = yafs_single_link_latency(topology["branch_bytes"], bw, pr)
    join_network = yafs_single_link_latency(topology["join_bytes"], bw, pr)

    return {
        "latency_common": root_network + pre_service + join_network + post_service,
        "branch_network_latency": {provider: branch_network for provider in PROVIDERS},
        "fixed_execution_cost": cost_rate * (pre_service + post_service),
        "fixed_quality_floor": 1.0,
    }


def empirical_quantile(values: np.ndarray, probability: float) -> float:
    """Linear empirical quantile used by the proposed trace-balanced rule."""
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        raise ValueError("empirical quantile requires at least one finite value")
    p = float(probability)
    if not 0.0 <= p <= 1.0:
        raise ValueError("quantile probability must lie in [0,1]")
    return float(np.quantile(array, p))


def solve_equal_percentile_cost_allocation(
    cost_samples: Mapping[str, np.ndarray],
    residual_budget: float,
    *,
    tolerance: float = 1e-12,
    iterations: int = 100,
) -> tuple[float, dict[str, float]]:
    """Return common percentile p* and provider caps whose sum matches budget.

    The sum of linear empirical quantiles is monotone and continuous in p.  The
    current benchmark must place the residual cost budget inside the empirical
    support.  Outside-support cases are rejected rather than silently inventing
    an extrapolation rule.
    """
    if set(cost_samples) != set(PROVIDERS):
        raise ValueError("cost samples must contain exactly ProviderA/B/C")
    budget = float(residual_budget)
    if budget < 0.0:
        raise ValueError("residual cost budget must be non-negative")

    cleaned: dict[str, np.ndarray] = {}
    for provider in PROVIDERS:
        values = np.asarray(cost_samples[provider], dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            raise ValueError(f"{provider} has no completed finite cost samples")
        cleaned[provider] = values

    lower_sum = sum(empirical_quantile(cleaned[p], 0.0) for p in PROVIDERS)
    upper_sum = sum(empirical_quantile(cleaned[p], 1.0) for p in PROVIDERS)
    if budget < lower_sum - tolerance or budget > upper_sum + tolerance:
        raise ValueError(
            "residual cost budget lies outside pooled empirical quantile support: "
            f"budget={budget:.12g}, min_sum={lower_sum:.12g}, max_sum={upper_sum:.12g}"
        )

    lo, hi = 0.0, 1.0
    for _ in range(int(iterations)):
        mid = (lo + hi) / 2.0
        candidate_sum = sum(empirical_quantile(cleaned[p], mid) for p in PROVIDERS)
        if candidate_sum <= budget:
            lo = mid
        else:
            hi = mid

    p_star = (lo + hi) / 2.0
    caps = {p: empirical_quantile(cleaned[p], p_star) for p in PROVIDERS}
    if abs(sum(caps.values()) - budget) > 1e-9:
        raise RuntimeError("equal-percentile cost allocation did not close the budget")
    return float(p_star), caps


def load_provider_cost_samples(acquisition_directory: Path = ACQUISITION) -> dict[str, np.ndarray]:
    """Load only provider-local completed cost samples from frozen acquisition ledgers."""
    samples: dict[str, np.ndarray] = {}
    for provider in PROVIDERS:
        path = acquisition_directory / provider / "provider_request_ledgers.csv"
        frame = pd.read_csv(path, usecols=["C"])
        values = frame["C"].dropna().astype(float).to_numpy()
        if values.size == 0:
            raise RuntimeError(f"{provider} has no completed local cost observations")
        samples[provider] = values
    return samples


def main() -> None:
    phase1_manifest = _read_json(PHASE1 / "phase1_v2_ar_freeze_manifest_v1.json")
    phase1_config = _read_json(PHASE1 / "config_phase1_discovery_v1.json")
    if phase1_manifest.get("status") != "FROZEN_PHASE1_V2_AR_SELECTION_V1":
        raise ValueError("Phase-1 v2 A_G battery is not frozen")

    fixed = derive_public_fixed_terms(phase1_config)
    costs = load_provider_cost_samples()

    print("PHASE2_PROVIDER_SPECIFIC_AI_DIAGNOSTIC_PASS")
    print("policy=maximal_latency + copied_quality + equal_empirical_cost_percentile")
    print("selection_uses_phase1_sigma_outcomes=false")
    print("selection_uses_M0_or_M1_outputs=false")
    print("rho_selection_performed=false")
    print()

    distribution_rows = []
    for provider in PROVIDERS:
        values = costs[provider]
        distribution_rows.append(
            {
                "provider": provider,
                "n_completed_cost": int(values.size),
                "mean_C": float(np.mean(values)),
                "q50_C": empirical_quantile(values, 0.50),
                "q90_C": empirical_quantile(values, 0.90),
                "q95_C": empirical_quantile(values, 0.95),
                "q975_C": empirical_quantile(values, 0.975),
                "q99_C": empirical_quantile(values, 0.99),
            }
        )
    print("PROVIDER_LOCAL_COST_DISTRIBUTIONS")
    print(pd.DataFrame(distribution_rows).to_string(index=False, float_format=lambda x: f"{x:.9f}"))
    print()

    candidate_rows = []
    for whitebox in phase1_manifest["whiteboxes"]:
        residual_cost = float(whitebox["c_max"]) - float(fixed["fixed_execution_cost"])
        p_star, cost_caps = solve_equal_percentile_cost_allocation(costs, residual_cost)
        for provider in PROVIDERS:
            branch = float(fixed["branch_network_latency"][provider])
            local_latency = float(whitebox["l_max"]) - float(fixed["latency_common"]) - branch
            if local_latency < -TOL:
                raise ValueError("negative local latency residual")
            cap = float(cost_caps[provider])
            empirical_coverage = float(np.mean(costs[provider] <= cap + TOL))
            candidate_rows.append(
                {
                    "global_case": str(whitebox["case_id"]),
                    "role": str(whitebox["selection_role"]),
                    "provider": provider,
                    "common_cost_percentile": p_star,
                    "l_max": max(0.0, local_latency),
                    "c_max": cap,
                    "q_min": float(whitebox["q_min"]),
                    "empirical_cost_coverage": empirical_coverage,
                }
            )

    candidates = pd.DataFrame(candidate_rows)
    print("CANDIDATE_PROVIDER_SPECIFIC_AI")
    print(candidates.to_string(index=False, float_format=lambda x: f"{x:.9f}"))
    print()

    budget_rows = []
    fixed_cost = float(fixed["fixed_execution_cost"])
    for whitebox in phase1_manifest["whiteboxes"]:
        case = str(whitebox["case_id"])
        block = candidates[candidates["global_case"] == case]
        local_sum = float(block["c_max"].sum())
        budget_rows.append(
            {
                "global_case": case,
                "C_G_max": float(whitebox["c_max"]),
                "C_fixed": fixed_cost,
                "sum_local_C_max": local_sum,
                "recomposed_C_max": fixed_cost + local_sum,
                "budget_error": fixed_cost + local_sum - float(whitebox["c_max"]),
            }
        )
    print("STRUCTURAL_COST_BUDGET_CHECK")
    print(pd.DataFrame(budget_rows).to_string(index=False, float_format=lambda x: f"{x:.12f}"))


if __name__ == "__main__":
    main()
