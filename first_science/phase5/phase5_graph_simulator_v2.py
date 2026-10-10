"""Generic native graph simulator for the frozen Phase-5 V2 battery.

The four public graph ASTs are compiled to PRAISE branch dependencies by
phase5_graph_ast_v2.  The physical embedding remains the frozen symmetric
Source/Fpre/provider/Fpost topology.  Sequence is implemented through the
native PRAISE composition-controller dependency mechanism: a dependent branch
is released only after its declared predecessor branch(es) complete.

This module contains no Step-0 selection or method-selection logic and can be
used by hidden WB, M1, M2, M3, and engineering smoke runs with different
provider-process parameters.
"""
from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from yafs.application import Application, LinearQoS, Message, fractional_selectivity
from yafs.core import Sim
from yafs.distribution import deterministic_distribution, gamma_distribution
from yafs.management_network import ManagementAgentNetwork
from yafs.population import Statical
from yafs.stats import Stats
from yafs.topology import Topology

HERE = Path(__file__).resolve().parent
PHASE3 = HERE.parent / "phase3"
if str(PHASE3) not in sys.path:
    sys.path.insert(0, str(PHASE3))

from m1_graph_simulator_v2 import (  # noqa: E402
    POSTPROCESS_MODULE,
    POSTPROCESS_NODE,
    PREPROCESS_MODULE,
    PREPROCESS_NODE,
    PROVIDERS,
    PROVIDER_NODES,
    ROOT_REQUEST_MESSAGE,
    SOURCE_MODULE,
    SOURCE_NODE,
    FixedM1GraphPlacement,
    GraphProviderSurrogate,
    ShortestPathForM1Graph,
    extract_top_level_request_ledger_from_native_trace,
    nominal_instruction_mean,
)

from phase5_graph_ast_v2 import (  # noqa: E402
    PROVIDER_BRANCH_ID,
    assert_frozen_graph_compilation,
)

APPLICATION_NAME = "PraisePhase5V2Graph"
COMPOSITION_PREFIX = "PHASE5"
TOL = 1e-12


def _validate_graph_invariants(invariants: Mapping[str, Any]) -> None:
    required = (
        "Fpre_instructions",
        "Fpost_instructions",
        "network_bw_mbps",
        "network_pr_seconds",
        "request_bytes",
        "branch_bytes",
        "join_bytes",
    )
    missing = [key for key in required if key not in invariants]
    if missing:
        raise ValueError(f"graph invariants missing {missing}")


def create_phase5_application(
    *,
    graph_id: str,
    graph_ast: Mapping[str, Any],
    provider_surrogates: Mapping[str, GraphProviderSurrogate],
    graph_invariants: Mapping[str, Any],
    canonical_ipt: float,
    execution_fraction: float,
    trajectory_seed: int,
) -> Application:
    if set(provider_surrogates) != set(PROVIDERS):
        raise ValueError("provider_surrogates must contain ProviderA/B/C")
    _validate_graph_invariants(graph_invariants)
    plan = assert_frozen_graph_compilation(graph_id, graph_ast)
    deps_by_branch = plan.dependency_branch_ids()

    app = Application(name=APPLICATION_NAME)
    app.set_modules(
        [
            {SOURCE_MODULE: {"Type": Application.TYPE_SOURCE}},
            {PREPROCESS_MODULE: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {PROVIDERS[0]: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {PROVIDERS[1]: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {PROVIDERS[2]: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {POSTPROCESS_MODULE: {"RAM": 10, "Type": Application.TYPE_MODULE}},
        ]
    )

    root = Message(
        ROOT_REQUEST_MESSAGE,
        SOURCE_MODULE,
        PREPROCESS_MODULE,
        instructions=float(graph_invariants["Fpre_instructions"]),
        bytes=int(graph_invariants["request_bytes"]),
        qos=LinearQoS(L=0.0, R=1.0),
    )
    app.add_source_messages(root)

    composition_id = f"{COMPOSITION_PREFIX}_{graph_id}"
    branch_messages: dict[str, Message] = {}

    for provider_ordinal, provider in enumerate(PROVIDERS):
        surrogate = provider_surrogates[provider]
        instruction_mean = nominal_instruction_mean(
            surrogate.mean_service_time,
            canonical_ipt=float(canonical_ipt),
            execution_fraction=float(execution_fraction),
        )
        if float(surrogate.service_cv) <= TOL:
            instruction_demand: object = float(instruction_mean)
        else:
            # Preserve the historical provider-specific seed mapping for every
            # official Phase-5 scientific seed.  The engineering smoke uses a
            # deliberately distant 99,000,000+ seed range, whose historical
            # multiplication by 100 would exceed NumPy RandomState's uint32
            # seed limit.  Only in that out-of-range engineering case do we
            # wrap deterministically; all scientific Phase-5 seeds remain
            # bit-for-bit on the original mapping.
            raw_provider_seed = (
                int(trajectory_seed) * 100 + provider_ordinal + 1
            )
            provider_seed = (
                raw_provider_seed
                if raw_provider_seed <= np.iinfo(np.uint32).max
                else raw_provider_seed % int(np.iinfo(np.uint32).max)
            )
            instruction_demand = gamma_distribution(
                mean=float(instruction_mean),
                cv=float(surrogate.service_cv),
                seed=provider_seed,
                name=f"phase5_{graph_id}_{provider}_{int(trajectory_seed)}",
            )

        msg = Message(
            f"M.{provider}",
            PREPROCESS_MODULE,
            provider,
            instructions=instruction_demand,
            bytes=int(graph_invariants["branch_bytes"]),
            qos=LinearQoS(L=0.0, R=1.0),
        )
        branch_messages[provider] = msg

        app.add_service_module_praise(
            PREPROCESS_MODULE,
            root,
            msg,
            fractional_selectivity,
            composition_id=composition_id,
            branch_id=int(PROVIDER_BRANCH_ID[provider]),
            depends_on=tuple(int(x) for x in deps_by_branch[provider]),
            threshold=1.0,
        )

    for provider in PROVIDERS:
        app.add_service_module(provider, branch_messages[provider])

    join = Message(
        "M.JOIN",
        app.compositions[composition_id]["controller_name"],
        POSTPROCESS_MODULE,
        instructions=float(graph_invariants["Fpost_instructions"]),
        bytes=int(graph_invariants["join_bytes"]),
        qos=LinearQoS(L=0.0, R=1.0),
    )
    app.set_composition_output_praise(
        composition_id=composition_id,
        message_out=join,
    )
    app.add_service_module(POSTPROCESS_MODULE, join)
    return app


def create_phase5_topology(
    *,
    provider_surrogates: Mapping[str, GraphProviderSurrogate],
    graph_invariants: Mapping[str, Any],
    canonical_ipt: float,
) -> Topology:
    if set(provider_surrogates) != set(PROVIDERS):
        raise ValueError("provider_surrogates must contain ProviderA/B/C")
    _validate_graph_invariants(graph_invariants)

    provider_ipt = float(canonical_ipt)
    fixed_ipt = float(graph_invariants.get("effective_IPT", canonical_ipt))
    fixed_cost_rate = float(graph_invariants.get("cost_rate", 3.0))
    bandwidth = float(graph_invariants["network_bw_mbps"])
    propagation = float(graph_invariants["network_pr_seconds"])
    if provider_ipt <= 0 or fixed_ipt <= 0 or bandwidth <= 0:
        raise ValueError("IPT and bandwidth must be positive")

    entities: list[dict[str, Any]] = [
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
            "PR": propagation,
        },
        *[
            {
                "s": PREPROCESS_NODE,
                "d": node_id,
                "BW": bandwidth,
                "PR": propagation,
            }
            for node_id in PROVIDER_NODES
        ],
        {
            "s": PREPROCESS_NODE,
            "d": POSTPROCESS_NODE,
            "BW": bandwidth,
            "PR": propagation,
        },
    ]

    topology = Topology()
    topology.load({"entity": entities, "link": links})
    return topology


def provider_interarrival_statistics_from_native_trace(
    trace_base: str,
) -> pd.DataFrame:
    """Passive provider-arrival diagnostic.

    Prefer a native receive/queue-entry timestamp.  If the installed YAFS trace
    schema exposes neither, return NOT_AVAILABLE rather than substituting source
    emission time, which would erase the topology-induced workload shift.
    """
    metric_rows = Stats(defaultPath=trace_base).df.copy()
    arrival_column = next(
        (
            col
            for col in ("time_reception", "time_in")
            if col in metric_rows.columns
        ),
        None,
    )

    rows: list[dict[str, Any]] = []
    for provider in PROVIDERS:
        if arrival_column is None:
            rows.append(
                {
                    "provider": provider,
                    "status": "NOT_AVAILABLE",
                    "arrival_column": None,
                    "n_arrivals": 0,
                    "mean_interarrival": np.nan,
                    "std_interarrival": np.nan,
                    "cv_interarrival": np.nan,
                    "p10_interarrival": np.nan,
                    "p50_interarrival": np.nan,
                    "p90_interarrival": np.nan,
                }
            )
            continue

        values = (
            pd.to_numeric(
                metric_rows.loc[
                    metric_rows["module"].astype(str) == provider,
                    arrival_column,
                ],
                errors="coerce",
            )
            .dropna()
            .astype(float)
            .sort_values()
            .to_numpy()
        )
        intervals = np.diff(values)
        if len(intervals) == 0:
            mean = std = cv = p10 = p50 = p90 = np.nan
        else:
            mean = float(np.mean(intervals))
            std = float(np.std(intervals, ddof=0))
            cv = float(std / mean) if mean > 0 else np.nan
            p10, p50, p90 = (
                float(x) for x in np.quantile(intervals, [0.10, 0.50, 0.90])
            )
        rows.append(
            {
                "provider": provider,
                "status": "AVAILABLE",
                "arrival_column": arrival_column,
                "n_arrivals": int(len(values)),
                "mean_interarrival": mean,
                "std_interarrival": std,
                "cv_interarrival": cv,
                "p10_interarrival": p10,
                "p50_interarrival": p50,
                "p90_interarrival": p90,
            }
        )

    return pd.DataFrame(rows)


def execute_one_phase5_graph_trajectory(
    *,
    graph_id: str,
    graph_ast: Mapping[str, Any],
    provider_surrogates: Mapping[str, GraphProviderSurrogate],
    graph_invariants: Mapping[str, Any],
    workload_period: float,
    stop_time: float,
    trajectory_seed: int,
    canonical_ipt: float,
    execution_fraction: float,
    return_provider_rows: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame] | tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run graph; optionally return native provider rows for diagnostics only."""
    period = float(workload_period)
    stop = float(stop_time)
    if period <= 0 or stop <= 0:
        raise ValueError("workload_period and stop_time must be positive")

    random.seed(int(trajectory_seed))
    np.random.seed(int(trajectory_seed))

    topology = create_phase5_topology(
        provider_surrogates=provider_surrogates,
        graph_invariants=graph_invariants,
        canonical_ipt=float(canonical_ipt),
    )
    app = create_phase5_application(
        graph_id=graph_id,
        graph_ast=graph_ast,
        provider_surrogates=provider_surrogates,
        graph_invariants=graph_invariants,
        canonical_ipt=float(canonical_ipt),
        execution_fraction=float(execution_fraction),
        trajectory_seed=int(trajectory_seed),
    )

    placement = FixedM1GraphPlacement(
        "phase5_v2_fixed_placement",
        provider_execution_fraction=float(execution_fraction),
    )
    population = Statical("phase5_v2_periodic_population")
    population.set_src_control(
        {
            "model": "source",
            "number": 1,
            "message": app.get_message(ROOT_REQUEST_MESSAGE),
            "distribution": deterministic_distribution(
                name=f"phase5_period_{period}",
                time=period,
            ),
        }
    )

    with tempfile.TemporaryDirectory(prefix="praise_phase5_v2_") as temporary:
        trace_base = str(Path(temporary) / "sim_trace")
        simulation = Sim(topology, default_results_path=trace_base)
        management_network = ManagementAgentNetwork(
            "phase5_v2_empty_management_network", [], simulation
        )
        simulation.deploy_app_agentic(
            app,
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
        diagnostics = provider_interarrival_statistics_from_native_trace(
            trace_base
        )
        if return_provider_rows:
            native = Stats(defaultPath=trace_base).df.copy()
            provider_rows = native.loc[native["module"].isin(PROVIDERS)].copy()

    ledger.insert(0, "graph_id", str(graph_id))
    ledger.insert(0, "seed", int(trajectory_seed))
    diagnostics.insert(0, "graph_id", str(graph_id))
    diagnostics.insert(0, "seed", int(trajectory_seed))
    if return_provider_rows:
        return ledger, diagnostics, provider_rows
    return ledger, diagnostics
