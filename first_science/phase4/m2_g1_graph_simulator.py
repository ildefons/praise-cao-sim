"""Native prediction-side simulator for frozen prospective condition G1.

G1 preserves the logical G0 ParAll composition and provider workload but uses
the predeclared asymmetric public branch propagation delays. This module never
reads or generates white-box evidence.
"""
from __future__ import annotations

import random
import tempfile
from pathlib import Path
from typing import Mapping

import numpy as np

from yafs.core import Sim
from yafs.distribution import deterministic_distribution
from yafs.management_network import ManagementAgentNetwork
from yafs.population import Statical
from yafs.topology import Topology

from m1_graph_simulator_v2 import (
    APPLICATION_NAME,
    POSTPROCESS_NODE,
    PREPROCESS_NODE,
    PROVIDERS,
    PROVIDER_NODES,
    ROOT_REQUEST_MESSAGE,
    SOURCE_NODE,
    FixedM1GraphPlacement,
    GraphProviderSurrogate,
    ShortestPathForM1Graph,
    create_m1_graph_application,
    extract_top_level_request_ledger_from_native_trace,
)
from m2_g1_public_adapter import validate_g1_public_graph_spec

TOL = 1e-12


def create_g1_prediction_topology(
    provider_surrogates: Mapping[str, GraphProviderSurrogate],
    graph_spec: Mapping[str, object],
    *,
    canonical_ipt: float,
) -> Topology:
    """Create the frozen asymmetric G1 topology from public information only."""
    if set(provider_surrogates) != set(PROVIDERS):
        raise ValueError("provider_surrogates must contain ProviderA/B/C")
    validate_g1_public_graph_spec(graph_spec)

    network = dict(graph_spec["network_model"])
    fixed = dict(graph_spec["fixed_service_model"])
    pr = dict(network["PR_seconds"])

    provider_ipt = float(canonical_ipt)
    fixed_ipt = float(fixed["effective_IPT"])
    fixed_cost_rate = float(fixed["COST_rate"])
    bandwidth = float(network["BW_mbps"])
    if provider_ipt <= 0.0 or fixed_ipt <= 0.0 or bandwidth <= 0.0:
        raise ValueError("G1 IPT and bandwidth values must be positive")

    entities = [
        {
            "id": SOURCE_NODE,
            "model": "source",
            "mytag": "source",
            "IPT": fixed_ipt,
            "RAM": 4000,
            "COST": 0.0,
            "WATT": 0.0,
        },
        {
            "id": PREPROCESS_NODE,
            "model": "fpre",
            "mytag": "fpre",
            "IPT": fixed_ipt,
            "RAM": 4000,
            "COST": fixed_cost_rate,
            "WATT": 0.0,
        },
    ]
    for provider, node_id in zip(PROVIDERS, PROVIDER_NODES):
        entities.append(
            {
                "id": node_id,
                "model": provider.lower(),
                "mytag": provider.lower(),
                "IPT": provider_ipt,
                "RAM": 4000,
                "COST": float(provider_surrogates[provider].cost_rate),
                "WATT": 0.0,
            }
        )
    entities.append(
        {
            "id": POSTPROCESS_NODE,
            "model": "fpost",
            "mytag": "fpost",
            "IPT": fixed_ipt,
            "RAM": 4000,
            "COST": fixed_cost_rate,
            "WATT": 0.0,
        }
    )

    links = [
        {
            "s": SOURCE_NODE,
            "d": PREPROCESS_NODE,
            "BW": bandwidth,
            "PR": float(pr["Source_to_Fpre"]),
        },
        {
            "s": PREPROCESS_NODE,
            "d": PROVIDER_NODES[0],
            "BW": bandwidth,
            "PR": float(pr["Fpre_to_ProviderA"]),
        },
        {
            "s": PREPROCESS_NODE,
            "d": PROVIDER_NODES[1],
            "BW": bandwidth,
            "PR": float(pr["Fpre_to_ProviderB"]),
        },
        {
            "s": PREPROCESS_NODE,
            "d": PROVIDER_NODES[2],
            "BW": bandwidth,
            "PR": float(pr["Fpre_to_ProviderC"]),
        },
        {
            "s": PREPROCESS_NODE,
            "d": POSTPROCESS_NODE,
            "BW": bandwidth,
            "PR": float(pr["Fpre_to_Fpost_join"]),
        },
    ]
    topology = Topology()
    topology.load({"entity": entities, "link": links})
    return topology


def execute_one_g1_prediction_trajectory(
    *,
    provider_surrogates: Mapping[str, GraphProviderSurrogate],
    graph_spec: Mapping[str, object],
    workload_period: float,
    stop_time: float,
    trajectory_seed: int,
    canonical_ipt: float,
    execution_fraction: float,
):
    """Run one blind G1 surrogate trajectory and return its top-level ledger."""
    period = float(workload_period)
    stop = float(stop_time)
    if period <= 0.0 or stop <= 0.0:
        raise ValueError("workload period and stop_time must be positive")

    random.seed(int(trajectory_seed))
    np.random.seed(int(trajectory_seed))

    topology = create_g1_prediction_topology(
        provider_surrogates,
        graph_spec,
        canonical_ipt=float(canonical_ipt),
    )
    # The application-level message/composition mechanics are unchanged from
    # G0. Only the physical network delays differ in G1.
    application = create_m1_graph_application(
        provider_surrogates,
        graph_spec,
        canonical_ipt=float(canonical_ipt),
        execution_fraction=float(execution_fraction),
        trajectory_seed=int(trajectory_seed),
    )
    placement = FixedM1GraphPlacement(
        "m2_g1_prediction_fixed_placement",
        provider_execution_fraction=float(execution_fraction),
    )
    population = Statical("m2_g1_prediction_periodic_population")
    population.set_src_control(
        {
            "model": "source",
            "number": 1,
            "message": application.get_message(ROOT_REQUEST_MESSAGE),
            "distribution": deterministic_distribution(
                name=f"m2_g1_prediction_period_{period}",
                time=period,
            ),
        }
    )

    with tempfile.TemporaryDirectory(prefix="praise_m2_g1_prediction_") as temporary:
        trace_base = str(Path(temporary) / "sim_trace")
        simulation = Sim(topology, default_results_path=trace_base)
        management_network = ManagementAgentNetwork(
            "m2_g1_empty_management_network", [], simulation
        )
        simulation.deploy_app_agentic(
            application,
            placement,
            population,
            ShortestPathForM1Graph(),
            management_network,
        )
        simulation.run(stop, show_progress_monitor=False)
        ledger = extract_top_level_request_ledger_from_native_trace(
            simulation,
            trace_base,
            stop_time=stop,
        )

    ledger.insert(0, "seed", int(trajectory_seed))
    return ledger
