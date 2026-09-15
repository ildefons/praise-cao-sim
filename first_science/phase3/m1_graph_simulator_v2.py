"""Native AICon/YAFS graph simulator for the Phase-3 M1-v2 prediction.

The simulator composes the already-selected provider surrogates in the public
G0 graph

    Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost

without reading hidden Phase-1 provider parameters. Provider service demand is
constructed only from the M1-v2 lifted (mu, kappa, CV) parameters. Fixed graph
stages and network terms are supplied by the already-public Phase-3 M0 benchmark
adapter contract.
"""
from __future__ import annotations

import random
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import networkx as nx
import numpy as np
import pandas as pd

from yafs.application import Application, LinearQoS, Message, fractional_selectivity
from yafs.core import Sim
from yafs.distribution import deterministic_distribution, gamma_distribution
from yafs.management_network import ManagementAgentNetwork
from yafs.placement import Placement
from yafs.population import Statical
from yafs.selection import Selection
from yafs.stats import Stats
from yafs.topology import Topology

PROVIDERS = ("ProviderA", "ProviderB", "ProviderC")
APPLICATION_NAME = "PraiseM1V2GraphPrediction"
SOURCE_MODULE = "Source"
PREPROCESS_MODULE = "Fpre"
POSTPROCESS_MODULE = "Fpost"
ROOT_REQUEST_MESSAGE = "M.ROOT"
BRANCH_MESSAGE_NAMES = ("M.A", "M.B", "M.C")
JOIN_MESSAGE = "M.JOIN"
COMPOSITION_ID = "G0_PARALL"
SOURCE_NODE = 0
PREPROCESS_NODE = 1
PROVIDER_NODES = (2, 3, 4)
POSTPROCESS_NODE = 5
TOLERANCE = 1e-12


@dataclass(frozen=True)
class GraphProviderSurrogate:
    """Selected M1-v2 surrogate for one provider."""

    mean_service_time: float
    cost_rate: float
    service_cv: float

    def __post_init__(self) -> None:
        if float(self.mean_service_time) <= 0.0:
            raise ValueError("mean_service_time must be positive")
        if float(self.cost_rate) < 0.0:
            raise ValueError("cost_rate must be non-negative")
        if float(self.service_cv) < 0.0:
            raise ValueError("service_cv must be non-negative")


def nominal_instruction_mean(
    mean_service_time: float,
    *,
    canonical_ipt: float,
    execution_fraction: float,
) -> float:
    """Map lifted mean service time to native nominal instruction demand."""
    mu = float(mean_service_time)
    ipt = float(canonical_ipt)
    x = float(execution_fraction)
    if mu <= 0.0 or ipt <= 0.0 or not 0.0 < x <= 1.0:
        raise ValueError("mu/IPT/x must satisfy mu>0, IPT>0, 0<x<=1")
    return float(mu * ipt / x)


class FixedM1GraphPlacement(Placement):
    """Deploy the fixed G0 modules and assign provider execution fraction x."""

    def __init__(self, name: str, provider_execution_fraction: float):
        super().__init__(name)
        self.provider_execution_fraction = float(provider_execution_fraction)

    def initial_allocation(self, sim, app_name):
        services = sim.apps[app_name].services
        deployment = {
            PREPROCESS_MODULE: PREPROCESS_NODE,
            PROVIDERS[0]: PROVIDER_NODES[0],
            PROVIDERS[1]: PROVIDER_NODES[1],
            PROVIDERS[2]: PROVIDER_NODES[2],
            POSTPROCESS_MODULE: POSTPROCESS_NODE,
        }
        for module_name, node_id in deployment.items():
            deployed = sim.deploy_module(
                app_name, module_name, services[module_name], [node_id]
            )
            if len(deployed) != 1:
                raise RuntimeError(
                    f"M1-v2 graph expected one DES for {module_name}, got {deployed}"
                )
            fraction = (
                self.provider_execution_fraction
                if module_name in PROVIDERS
                else 1.0
            )
            sim.des_pct_instructions[deployed[0]] = fraction


class ShortestPathForM1Graph(Selection):
    """Select the unique shortest path to each fixed G0 module deployment."""

    def get_path(
        self,
        sim,
        app_name,
        message,
        topology_src,
        alloc_DES,
        alloc_module,
        traffic,
        from_des,
    ):
        destinations = alloc_module[app_name][message.dst]
        if len(destinations) != 1:
            raise RuntimeError(
                f"M1-v2 graph expected one destination for {message.dst}"
            )
        des = destinations[0]
        destination_node = alloc_DES[des]
        path = list(
            nx.shortest_path(
                sim.topology.G,
                source=topology_src,
                target=destination_node,
            )
        )
        return [path], [des]


def validate_public_graph_spec(graph_spec: Mapping[str, object]) -> None:
    """Validate the public deterministic G0 adapter used by M1-v2."""
    if str(graph_spec.get("graph")) != (
        "Source -> Fpre -> ParAll(ProviderA,ProviderB,ProviderC) -> Fpost"
    ):
        raise ValueError("unexpected public G0 graph grammar")
    network = graph_spec.get("network_model")
    fixed = graph_spec.get("fixed_service_model")
    if not isinstance(network, Mapping) or not isinstance(fixed, Mapping):
        raise ValueError("public graph spec lacks network/fixed service mappings")
    for key in ("request_bytes", "branch_bytes", "join_bytes", "BW_mbps", "PR"):
        if key not in network:
            raise ValueError(f"public graph network model lacks {key}")
    for key in (
        "Fpre_instructions",
        "Fpost_instructions",
        "effective_IPT",
        "COST_rate",
    ):
        if key not in fixed:
            raise ValueError(f"public graph fixed service model lacks {key}")


def create_m1_graph_application(
    provider_surrogates: Mapping[str, GraphProviderSurrogate],
    graph_spec: Mapping[str, object],
    *,
    canonical_ipt: float,
    execution_fraction: float,
    trajectory_seed: int,
) -> Application:
    """Create one native G0 application using only lifted provider parameters."""
    if set(provider_surrogates) != set(PROVIDERS):
        raise ValueError("provider_surrogates must contain ProviderA/B/C")
    validate_public_graph_spec(graph_spec)
    network = dict(graph_spec["network_model"])
    fixed = dict(graph_spec["fixed_service_model"])

    application = Application(name=APPLICATION_NAME)
    application.set_modules(
        [
            {SOURCE_MODULE: {"Type": Application.TYPE_SOURCE}},
            {PREPROCESS_MODULE: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {PROVIDERS[0]: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {PROVIDERS[1]: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {PROVIDERS[2]: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {POSTPROCESS_MODULE: {"RAM": 10, "Type": Application.TYPE_MODULE}},
        ]
    )

    root_request = Message(
        ROOT_REQUEST_MESSAGE,
        SOURCE_MODULE,
        PREPROCESS_MODULE,
        instructions=float(fixed["Fpre_instructions"]),
        bytes=int(network["request_bytes"]),
        qos=LinearQoS(L=0.0, R=1.0),
    )
    application.add_source_messages(root_request)

    branch_messages = []
    for provider_ordinal, (provider, message_name) in enumerate(
        zip(PROVIDERS, BRANCH_MESSAGE_NAMES)
    ):
        surrogate = provider_surrogates[provider]
        instruction_mean = nominal_instruction_mean(
            surrogate.mean_service_time,
            canonical_ipt=float(canonical_ipt),
            execution_fraction=float(execution_fraction),
        )
        if float(surrogate.service_cv) <= TOLERANCE:
            instruction_demand: object = float(instruction_mean)
        else:
            provider_seed = int(trajectory_seed) * 100 + provider_ordinal + 1
            instruction_demand = gamma_distribution(
                mean=float(instruction_mean),
                cv=float(surrogate.service_cv),
                seed=provider_seed,
                name=f"m1v2_{provider}_seed_{int(trajectory_seed)}",
            )
        branch_message = Message(
            message_name,
            PREPROCESS_MODULE,
            provider,
            instructions=instruction_demand,
            bytes=int(network["branch_bytes"]),
            qos=LinearQoS(L=0.0, R=1.0),
        )
        branch_messages.append(branch_message)
        application.add_service_module_praise(
            PREPROCESS_MODULE,
            root_request,
            branch_message,
            fractional_selectivity,
            composition_id=COMPOSITION_ID,
            branch_id=provider_ordinal,
            depends_on=(),
            threshold=1.0,
        )

    for provider, branch_message in zip(PROVIDERS, branch_messages):
        application.add_service_module(provider, branch_message)

    join_message = Message(
        JOIN_MESSAGE,
        application.compositions[COMPOSITION_ID]["controller_name"],
        POSTPROCESS_MODULE,
        instructions=float(fixed["Fpost_instructions"]),
        bytes=int(network["join_bytes"]),
        qos=LinearQoS(L=0.0, R=1.0),
    )
    application.set_composition_output_praise(
        composition_id=COMPOSITION_ID,
        message_out=join_message,
    )
    application.add_service_module(POSTPROCESS_MODULE, join_message)
    return application


def create_m1_graph_topology(
    provider_surrogates: Mapping[str, GraphProviderSurrogate],
    graph_spec: Mapping[str, object],
    *,
    canonical_ipt: float,
) -> Topology:
    """Create native G0 topology with public fixed terms and lifted provider rates."""
    if set(provider_surrogates) != set(PROVIDERS):
        raise ValueError("provider_surrogates must contain ProviderA/B/C")
    validate_public_graph_spec(graph_spec)
    network = dict(graph_spec["network_model"])
    fixed = dict(graph_spec["fixed_service_model"])

    provider_ipt = float(canonical_ipt)
    fixed_ipt = float(fixed["effective_IPT"])
    fixed_cost_rate = float(fixed["COST_rate"])
    if provider_ipt <= 0.0 or fixed_ipt <= 0.0:
        raise ValueError("provider/fixed IPT values must be positive")

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

    bandwidth = float(network["BW_mbps"])
    propagation = float(network["PR"])
    links = [
        {"s": SOURCE_NODE, "d": PREPROCESS_NODE, "BW": bandwidth, "PR": propagation},
        {"s": PREPROCESS_NODE, "d": PROVIDER_NODES[0], "BW": bandwidth, "PR": propagation},
        {"s": PREPROCESS_NODE, "d": PROVIDER_NODES[1], "BW": bandwidth, "PR": propagation},
        {"s": PREPROCESS_NODE, "d": PROVIDER_NODES[2], "BW": bandwidth, "PR": propagation},
        {"s": PREPROCESS_NODE, "d": POSTPROCESS_NODE, "BW": bandwidth, "PR": propagation},
    ]
    topology = Topology()
    topology.load({"entity": entities, "link": links})
    return topology


def extract_top_level_request_ledger_from_native_trace(
    simulation: Sim,
    trace_base: str,
    *,
    stop_time: float,
) -> pd.DataFrame:
    """Reduce one native M1-v2 graph trace to top-level request outcomes."""
    metric_rows = Stats(defaultPath=trace_base).df.copy()
    if metric_rows.empty:
        raise RuntimeError("native M1-v2 graph simulation produced no metric rows")

    expected_modules = {
        PREPROCESS_MODULE,
        PROVIDERS[0],
        PROVIDERS[1],
        PROVIDERS[2],
        POSTPROCESS_MODULE,
    }
    root_rows = metric_rows[metric_rows["module"] == PREPROCESS_MODULE].copy()
    if root_rows.empty:
        raise RuntimeError("native M1-v2 graph trace contains no Fpre rows")

    topology_information = simulation.topology.get_info()
    rows: list[dict[str, object]] = []
    for root_row in root_rows.itertuples(index=False):
        request_id = int(root_row.id)
        request_rows = metric_rows[
            (metric_rows["id"] == request_id)
            & (metric_rows["module"].isin(expected_modules))
        ].copy()
        post_rows = request_rows[request_rows["module"] == POSTPROCESS_MODULE]
        if len(post_rows) > 1:
            raise RuntimeError(f"request {request_id} has multiple Fpost rows")

        emission = float(root_row.time_emit)
        completion = None
        latency = None
        cost = None
        quality = None
        if len(post_rows) == 1:
            candidate_completion = float(post_rows.iloc[0]["time_out"])
            if candidate_completion <= float(stop_time) + TOLERANCE:
                module_counts = request_rows["module"].value_counts().to_dict()
                invalid = [
                    module
                    for module in expected_modules
                    if int(module_counts.get(module, 0)) != 1
                ]
                if invalid:
                    raise RuntimeError(
                        f"completed request {request_id} lacks exactly one row for {invalid}"
                    )
                completion = candidate_completion
                latency = completion - emission
                accumulated_cost = 0.0
                for _, metric_row in request_rows.iterrows():
                    node_id = int(metric_row["TOPO.dst"])
                    accumulated_cost += (
                        float(topology_information[node_id]["COST"])
                        * float(metric_row["service"])
                    )
                cost = accumulated_cost
                quality = float(request_rows["qos"].min())

        rows.append(
            {
                "request_id": request_id,
                "emission": emission,
                "completion": completion,
                "completed_by_stop": completion is not None,
                "status": "completed" if completion is not None else "incomplete",
                "L": latency,
                "C": cost,
                "Q": quality,
                "stop_time": float(stop_time),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["emission", "request_id"]
    ).reset_index(drop=True)


def execute_one_m1_graph_trajectory(
    *,
    provider_surrogates: Mapping[str, GraphProviderSurrogate],
    graph_spec: Mapping[str, object],
    workload_period: float,
    stop_time: float,
    trajectory_seed: int,
    canonical_ipt: float,
    execution_fraction: float,
) -> pd.DataFrame:
    """Run one native composed M1-v2 trajectory and return its top-level ledger."""
    period = float(workload_period)
    stop = float(stop_time)
    if period <= 0.0 or stop <= 0.0:
        raise ValueError("workload period and stop_time must be positive")

    random.seed(int(trajectory_seed))
    np.random.seed(int(trajectory_seed))
    topology = create_m1_graph_topology(
        provider_surrogates,
        graph_spec,
        canonical_ipt=float(canonical_ipt),
    )
    application = create_m1_graph_application(
        provider_surrogates,
        graph_spec,
        canonical_ipt=float(canonical_ipt),
        execution_fraction=float(execution_fraction),
        trajectory_seed=int(trajectory_seed),
    )
    placement = FixedM1GraphPlacement(
        "m1_v2_graph_fixed_placement",
        provider_execution_fraction=float(execution_fraction),
    )
    population = Statical("m1_v2_graph_periodic_population")
    population.set_src_control(
        {
            "model": "source",
            "number": 1,
            "message": application.get_message(ROOT_REQUEST_MESSAGE),
            "distribution": deterministic_distribution(
                name=f"m1_v2_graph_period_{period}",
                time=period,
            ),
        }
    )

    with tempfile.TemporaryDirectory(prefix="praise_m1_v2_graph_") as temporary:
        trace_base = str(Path(temporary) / "sim_trace")
        simulation = Sim(topology, default_results_path=trace_base)
        management_network = ManagementAgentNetwork(
            "m1_v2_empty_management_network", [], simulation
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
