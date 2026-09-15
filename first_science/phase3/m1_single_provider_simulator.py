"""Native AICon/YAFS single-provider simulator used by the Phase-3 M1 lift.

The simulator is intentionally independent of the hidden Phase-1 provider
configuration. It receives only a public workload contract, public I1 regions,
and the M1 surrogate parameters being calibrated.

Pilot closure conventions
-------------------------
* one native FCFS provider module;
* source and provider colocated, so local L excludes network delay;
* canonical IPT is a numerical gauge, not recovered hardware;
* x=0.5 and LinearQoS(0,1) because the current public I1 cards have degenerate
  Q=0.5;
* local C is native COST(node) * service;
* deterministic service for Stage 1, Gamma service demand for Stage 2.
"""
from __future__ import annotations

import random
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import networkx as nx
import numpy as np
import pandas as pd

from yafs.application import Application, LinearQoS, Message
from yafs.core import Sim
from yafs.distribution import deterministic_distribution, gamma_distribution
from yafs.management_network import ManagementAgentNetwork
from yafs.placement import Placement
from yafs.population import Statical
from yafs.selection import Selection
from yafs.stats import Stats
from yafs.topology import Topology

HERE = Path(__file__).resolve().parent
PHASE1 = HERE.parent / "phase1"
if str(PHASE1) not in sys.path:
    sys.path.insert(0, str(PHASE1))

from sla_compliance_analysis import (  # noqa: E402
    SlaComplianceDefinition,
    build_request_sla_decision_table,
    calculate_empirical_sla_sigma_from_decision_tables,
    calculate_trajectory_cumulative_sla_curve,
)

TOLERANCE = 1e-10
DEFAULT_CANONICAL_IPT = 1_000_000.0
DEFAULT_PILOT_EXECUTION_FRACTION = 0.5
APPLICATION_NAME = "PraiseM1SingleProviderLift"
SOURCE_MODULE = "M1Source"
REQUEST_MESSAGE = "M1.REQUEST"
HOST_NODE = 0


@dataclass(frozen=True)
class SingleProviderSurrogateParameters:
    """Native local surrogate parameters for one provider."""

    mean_service_time: float
    cost_rate: float
    service_cv: float = 0.0

    def __post_init__(self) -> None:
        if self.mean_service_time <= 0.0:
            raise ValueError("mean_service_time must be positive")
        if self.cost_rate < 0.0:
            raise ValueError("cost_rate must be non-negative")
        if self.service_cv < 0.0:
            raise ValueError("service_cv must be non-negative")


class FixedSingleProviderPlacement(Placement):
    """Deploy exactly one provider DES on the single local host."""

    def __init__(self, name: str, provider_id: str, execution_fraction: float):
        super().__init__(name)
        self.provider_id = str(provider_id)
        self.execution_fraction = float(execution_fraction)

    def initial_allocation(self, sim, app_name):
        services = sim.apps[app_name].services
        deployed = sim.deploy_module(
            app_name,
            self.provider_id,
            services[self.provider_id],
            [HOST_NODE],
        )
        if len(deployed) != 1:
            raise RuntimeError(
                f"M1 local lift expected one DES for {self.provider_id}, got {deployed}"
            )
        sim.des_pct_instructions[deployed[0]] = self.execution_fraction


class ColocatedSingleProviderSelection(Selection):
    """Route each local request to the unique provider deployment."""

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
            raise RuntimeError("M1 local lift requires one provider destination")
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


def nominal_instruction_mean(
    mean_service_time: float,
    *,
    canonical_ipt: float = DEFAULT_CANONICAL_IPT,
    execution_fraction: float = DEFAULT_PILOT_EXECUTION_FRACTION,
) -> float:
    """Map the interpretable service-time mean into native nominal instructions."""
    mu = float(mean_service_time)
    ipt = float(canonical_ipt)
    x = float(execution_fraction)
    if mu <= 0.0 or ipt <= 0.0 or not 0.0 < x <= 1.0:
        raise ValueError("mu/IPT/x must satisfy mu>0, IPT>0, 0<x<=1")
    return float(mu * ipt / x)


def validate_pilot_public_card(
    metadata: Mapping[str, object],
    surface: pd.DataFrame,
    *,
    expected_quality: float = DEFAULT_PILOT_EXECUTION_FRACTION,
) -> None:
    """Reject accidental use of the Q-degenerate pilot adapter on richer cards."""
    provider = str(metadata.get("provider_id", "")).strip()
    if not provider:
        raise ValueError("public I1 metadata lacks provider_id")
    workload = metadata.get("workload_contract")
    if not isinstance(workload, Mapping):
        raise ValueError("public I1 metadata lacks workload_contract")
    for field in ("period", "accounting_origin", "horizon_max"):
        if field not in workload:
            raise ValueError(f"public workload contract lacks {field}")
    if float(workload["period"]) <= 0.0:
        raise ValueError("public workload period must be positive")
    if abs(float(workload["accounting_origin"])) > TOLERANCE:
        raise ValueError("M1 pilot currently requires accounting_origin=0")

    if "q_min" not in surface.columns:
        raise ValueError("public I1 surface lacks q_min")
    q_values = np.unique(surface["q_min"].astype(float).to_numpy())
    if len(q_values) != 1 or not np.isclose(
        q_values[0], float(expected_quality), atol=TOLERANCE, rtol=0.0
    ):
        raise ValueError(
            "M1 pilot Q adapter applies only to cards with constant q_min=0.5"
        )


def create_single_provider_application(
    provider_id: str,
    parameters: SingleProviderSurrogateParameters,
    *,
    canonical_ipt: float,
    execution_fraction: float,
    trajectory_seed: int,
) -> Application:
    """Create the native terminal provider application for one M1 trajectory."""
    provider = str(provider_id).strip()
    if not provider:
        raise ValueError("provider_id must be non-empty")
    instruction_mean = nominal_instruction_mean(
        parameters.mean_service_time,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
    )
    if parameters.service_cv <= TOLERANCE:
        instruction_demand: object = float(instruction_mean)
    else:
        instruction_demand = gamma_distribution(
            mean=float(instruction_mean),
            cv=float(parameters.service_cv),
            seed=int(trajectory_seed),
            name=f"m1_{provider}_instructions_seed_{int(trajectory_seed)}",
        )

    application = Application(name=APPLICATION_NAME)
    application.set_modules(
        [
            {SOURCE_MODULE: {"Type": Application.TYPE_SOURCE}},
            {provider: {"RAM": 10, "Type": Application.TYPE_MODULE}},
        ]
    )
    request = Message(
        REQUEST_MESSAGE,
        SOURCE_MODULE,
        provider,
        instructions=instruction_demand,
        bytes=0,
        qos=LinearQoS(L=0.0, R=1.0),
    )
    application.add_source_messages(request)
    application.add_service_module(provider, request)
    return application


def create_single_provider_topology(
    parameters: SingleProviderSurrogateParameters,
    *,
    canonical_ipt: float,
) -> Topology:
    """Create one local host carrying both source and provider deployment."""
    ipt = float(canonical_ipt)
    if ipt <= 0.0:
        raise ValueError("canonical_ipt must be positive")
    topology = Topology()
    topology.load(
        {
            "entity": [
                {
                    "id": HOST_NODE,
                    "model": "m1-local-provider-host",
                    "mytag": "m1-local-provider-host",
                    "IPT": ipt,
                    "RAM": 4000,
                    "COST": float(parameters.cost_rate),
                    "WATT": 0.0,
                }
            ],
            "link": [],
        }
    )
    return topology


def _scheduled_periodic_arrivals(period: float, stop_time: float) -> pd.DataFrame:
    """Reconstruct the deterministic source schedule used by YAFS population.

    YAFS source populations wait once for ``distribution.next()`` before their
    first emission, so a deterministic period T emits at T, 2T, ... .
    """
    t = float(period)
    stop = float(stop_time)
    if t <= 0.0 or stop <= 0.0:
        raise ValueError("period and stop_time must be positive")
    n = int(np.floor((stop + TOLERANCE) / t))
    indices = np.arange(1, n + 1, dtype=int)
    return pd.DataFrame(
        {
            "request_id": indices,
            "emission": indices.astype(float) * t,
        }
    )


def extract_provider_ledger_from_native_trace(
    trace_base: str,
    provider_id: str,
    *,
    period: float,
    stop_time: float,
    cost_rate: float,
) -> pd.DataFrame:
    """Return one local ledger row for every scheduled provider arrival."""
    scheduled = _scheduled_periodic_arrivals(period, stop_time)
    try:
        metric_rows = Stats(defaultPath=trace_base).df.copy()
    except Exception:
        metric_rows = pd.DataFrame()

    if metric_rows.empty:
        completed = pd.DataFrame(
            columns=["request_id", "completion", "L", "C", "Q"]
        )
    else:
        provider_rows = metric_rows[metric_rows["module"] == str(provider_id)].copy()
        if provider_rows.empty:
            completed = pd.DataFrame(
                columns=["request_id", "completion", "L", "C", "Q"]
            )
        else:
            emitted = provider_rows["time_emit"].astype(float).to_numpy()
            arrival_index = np.rint(emitted / float(period)).astype(int)
            expected = arrival_index.astype(float) * float(period)
            if np.any(np.abs(emitted - expected) > 1e-7):
                raise RuntimeError(
                    "native M1 local emissions do not match the public periodic W_i"
                )
            if len(set(arrival_index.tolist())) != len(arrival_index):
                raise RuntimeError("native M1 local trace contains duplicate request arrivals")
            completion = provider_rows["time_out"].astype(float).to_numpy()
            service = provider_rows["service"].astype(float).to_numpy()
            quality = provider_rows["qos"].astype(float).to_numpy()
            completed = pd.DataFrame(
                {
                    "request_id": arrival_index,
                    "completion": completion,
                    "L": completion - expected,
                    "C": float(cost_rate) * service,
                    "Q": quality,
                }
            )

    ledger = scheduled.merge(completed, on="request_id", how="left", validate="one_to_one")
    ledger["completed_by_stop"] = ledger["completion"].notna()
    ledger["status"] = np.where(
        ledger["completed_by_stop"], "completed", "incomplete"
    )
    return ledger[
        [
            "request_id",
            "emission",
            "completion",
            "completed_by_stop",
            "status",
            "L",
            "C",
            "Q",
        ]
    ].sort_values(["emission", "request_id"]).reset_index(drop=True)


def execute_one_single_provider_trajectory(
    *,
    provider_id: str,
    parameters: SingleProviderSurrogateParameters,
    workload_contract: Mapping[str, object],
    trajectory_seed: int,
    canonical_ipt: float = DEFAULT_CANONICAL_IPT,
    execution_fraction: float = DEFAULT_PILOT_EXECUTION_FRACTION,
) -> pd.DataFrame:
    """Run one native local-provider trajectory and return its request ledger."""
    period = float(workload_contract["period"])
    stop_time = float(workload_contract["horizon_max"])
    if abs(float(workload_contract.get("accounting_origin", 0.0))) > TOLERANCE:
        raise ValueError("M1 pilot currently requires accounting_origin=0")

    random.seed(int(trajectory_seed))
    np.random.seed(int(trajectory_seed))
    topology = create_single_provider_topology(
        parameters,
        canonical_ipt=float(canonical_ipt),
    )
    application = create_single_provider_application(
        provider_id,
        parameters,
        canonical_ipt=float(canonical_ipt),
        execution_fraction=float(execution_fraction),
        trajectory_seed=int(trajectory_seed),
    )
    placement = FixedSingleProviderPlacement(
        "m1_single_provider_placement",
        provider_id=str(provider_id),
        execution_fraction=float(execution_fraction),
    )
    population = Statical("m1_periodic_provider_workload")
    population.set_src_control(
        {
            "model": "m1-local-provider-host",
            "number": 1,
            "message": application.get_message(REQUEST_MESSAGE),
            "distribution": deterministic_distribution(
                name=f"m1_period_{period}",
                time=period,
            ),
        }
    )

    with tempfile.TemporaryDirectory(prefix="praise_m1_local_") as temporary:
        trace_base = str(Path(temporary) / "sim_trace")
        simulation = Sim(topology, default_results_path=trace_base)
        management_network = ManagementAgentNetwork(
            "m1_empty_management_network", [], simulation
        )
        simulation.deploy_app_agentic(
            application,
            placement,
            population,
            ColocatedSingleProviderSelection(),
            management_network,
        )
        simulation.run(stop_time, show_progress_monitor=False)
        ledger = extract_provider_ledger_from_native_trace(
            trace_base,
            str(provider_id),
            period=period,
            stop_time=stop_time,
            cost_rate=float(parameters.cost_rate),
        )
    ledger.insert(0, "trajectory", int(trajectory_seed))
    return ledger


def _regions_from_metadata(metadata: Mapping[str, object]) -> list[dict[str, object]]:
    regions_object = metadata.get("rho_conditioned_regions")
    if not isinstance(regions_object, list) or not regions_object:
        raise ValueError("public I1 metadata lacks rho_conditioned_regions")
    regions = [dict(region) for region in regions_object]
    required = {"region_id", "region_rho", "l_max", "c_max", "q_min"}
    for region in regions:
        missing = required.difference(region)
        if missing:
            raise ValueError(
                "public I1 region missing fields: " + ", ".join(sorted(missing))
            )
    return regions


def simulate_deterministic_compliance_surface(
    *,
    metadata: Mapping[str, object],
    public_surface: pd.DataFrame,
    mean_service_time: float,
    cost_rate: float,
    canonical_ipt: float = DEFAULT_CANONICAL_IPT,
    execution_fraction: float = DEFAULT_PILOT_EXECUTION_FRACTION,
) -> pd.DataFrame:
    """Run Stage 1 and return c_det(A_i,H) for every public region/H."""
    validate_pilot_public_card(
        metadata,
        public_surface,
        expected_quality=execution_fraction,
    )
    provider = str(metadata["provider_id"])
    workload = dict(metadata["workload_contract"])
    horizons = [float(value) for value in metadata["supported_horizons"]]
    parameters = SingleProviderSurrogateParameters(
        mean_service_time=float(mean_service_time),
        cost_rate=float(cost_rate),
        service_cv=0.0,
    )
    ledger = execute_one_single_provider_trajectory(
        provider_id=provider,
        parameters=parameters,
        workload_contract=workload,
        trajectory_seed=0,
        canonical_ipt=canonical_ipt,
        execution_fraction=execution_fraction,
    )

    rows: list[dict[str, object]] = []
    for region in _regions_from_metadata(metadata):
        decisions = build_request_sla_decision_table(
            ledger,
            latency_threshold=float(region["l_max"]),
            cost_threshold=float(region["c_max"]),
            quality_threshold=float(region["q_min"]),
            stop_time=float(workload["horizon_max"]),
        )
        curve = calculate_trajectory_cumulative_sla_curve(
            decisions,
            horizons,
            SlaComplianceDefinition(
                rho=0.5,
                accounting_origin=float(workload["accounting_origin"]),
                zero_decision_compliance=1.0,
            ),
        )
        for point in curve.itertuples(index=False):
            rows.append(
                {
                    "provider_id": provider,
                    "region_id": str(region["region_id"]),
                    "region_rho": float(region["region_rho"]),
                    "horizon": float(point.horizon),
                    "compliance_fraction": float(point.compliance_fraction),
                    "decided_requests": int(point.decided_requests),
                    "compliant_requests": int(point.compliant_requests),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["region_rho", "horizon"]
    ).reset_index(drop=True)


def simulate_stochastic_sigma_surface(
    *,
    metadata: Mapping[str, object],
    public_surface: pd.DataFrame,
    mean_service_time: float,
    cost_rate: float,
    service_cv: float,
    trajectory_seeds: Iterable[int],
    canonical_ipt: float = DEFAULT_CANONICAL_IPT,
    execution_fraction: float = DEFAULT_PILOT_EXECUTION_FRACTION,
) -> pd.DataFrame:
    """Run Stage 2 and estimate the full public-key local sigma surface."""
    validate_pilot_public_card(
        metadata,
        public_surface,
        expected_quality=execution_fraction,
    )
    seeds = tuple(int(seed) for seed in trajectory_seeds)
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Stage-2 trajectory seeds must be non-empty and unique")

    provider = str(metadata["provider_id"])
    workload = dict(metadata["workload_contract"])
    horizons = [float(value) for value in metadata["supported_horizons"]]
    query_rhos = [float(value) for value in metadata["supported_query_rho_values"]]
    parameters = SingleProviderSurrogateParameters(
        mean_service_time=float(mean_service_time),
        cost_rate=float(cost_rate),
        service_cv=float(service_cv),
    )
    ledgers = [
        execute_one_single_provider_trajectory(
            provider_id=provider,
            parameters=parameters,
            workload_contract=workload,
            trajectory_seed=seed,
            canonical_ipt=canonical_ipt,
            execution_fraction=execution_fraction,
        )
        for seed in seeds
    ]

    rows: list[dict[str, object]] = []
    for region in _regions_from_metadata(metadata):
        decision_tables = [
            build_request_sla_decision_table(
                ledger,
                latency_threshold=float(region["l_max"]),
                cost_threshold=float(region["c_max"]),
                quality_threshold=float(region["q_min"]),
                stop_time=float(workload["horizon_max"]),
            )
            for ledger in ledgers
        ]
        for rho in query_rhos:
            sigma_curve, _ = calculate_empirical_sla_sigma_from_decision_tables(
                decision_tables,
                horizons,
                SlaComplianceDefinition(
                    rho=float(rho),
                    accounting_origin=float(workload["accounting_origin"]),
                    zero_decision_compliance=1.0,
                ),
            )
            for point in sigma_curve.itertuples(index=False):
                rows.append(
                    {
                        "provider_id": provider,
                        "region_id": str(region["region_id"]),
                        "region_rho": float(region["region_rho"]),
                        "rho": float(rho),
                        "horizon": float(point.horizon),
                        "sigma_hat": float(point.sigma),
                        "n_trajectories": len(seeds),
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["region_rho", "rho", "horizon"]
    ).reset_index(drop=True)
