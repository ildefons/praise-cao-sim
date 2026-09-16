"""Native smoke test for composed M1-v2 G0 simulation."""
from __future__ import annotations

from math import isclose

from m1_graph_simulator_v2 import (
    GraphProviderSurrogate,
    execute_one_m1_graph_trajectory,
    nominal_instruction_mean,
)


def _public_graph_spec() -> dict[str, object]:
    return {
        "graph": "Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost",
        "network_model": {
            "request_bytes": 1000,
            "branch_bytes": 1000,
            "join_bytes": 1000,
            "BW_mbps": 1000.0,
            "PR": 0.001,
        },
        "fixed_service_model": {
            "Fpre_instructions": 5_000_000.0,
            "Fpost_instructions": 5_000_000.0,
            "effective_IPT": 1_000_000_000.0,
            "COST_rate": 3.0,
        },
    }


def main() -> None:
    assert isclose(
        nominal_instruction_mean(
            0.02, canonical_ipt=1_000_000.0, execution_fraction=0.5
        ),
        40_000.0,
        abs_tol=1e-12,
    )

    providers = {
        provider: GraphProviderSurrogate(
            mean_service_time=0.02,
            cost_rate=2.0,
            service_cv=0.0,
        )
        for provider in ("ProviderA", "ProviderB", "ProviderC")
    }
    ledger = execute_one_m1_graph_trajectory(
        provider_surrogates=providers,
        graph_spec=_public_graph_spec(),
        workload_period=0.2,
        stop_time=2.0,
        trajectory_seed=12345,
        canonical_ipt=1_000_000.0,
        execution_fraction=0.5,
    )
    assert not ledger.empty
    completed = ledger[ledger["completed_by_stop"]].copy()
    assert not completed.empty
    assert completed["L"].astype(float).gt(0.0).all()
    assert completed["C"].astype(float).gt(0.0).all()
    assert completed["Q"].astype(float).eq(0.5).all()

    # Native PRAISE ParAll sends one zero-byte completion-control message from
    # each completed provider back to the join controller. In this topology the
    # controller is colocated with Fpre, so the critical branch pays one reverse
    # branch propagation delay PR before the join message can be emitted.
    # Hence deterministic G0 latency is:
    # root hop + Fpre + branch hop + max(provider + control-return hop)
    # + join hop + Fpost.
    completion_control_latency = 0.001
    expected_latency = (
        0.001001
        + 0.005
        + 0.001001
        + 0.02
        + completion_control_latency
        + 0.001001
        + 0.005
    )
    assert isclose(
        float(completed.iloc[0]["L"]), expected_latency, rel_tol=0.0, abs_tol=1e-8
    )

    # Cost is Fpre+Fpost (2*3*0.005) plus all three provider costs
    # (3*2*0.02). The completion-control message has zero instructions/cost.
    expected_cost = 0.03 + 3.0 * 2.0 * 0.02
    assert isclose(
        float(completed.iloc[0]["C"]), expected_cost, rel_tol=0.0, abs_tol=1e-8
    )

    print("PHASE3_M1_V2_GRAPH_SIMULATOR_SMOKE_PASS")
    print("M1_V2_NATIVE_PARALL_LATENCY_PASS")
    print("M1_V2_NATIVE_GRAPH_COST_PASS")
    print("M1_V2_NATIVE_GRAPH_QOS_PASS")


if __name__ == "__main__":
    main()
