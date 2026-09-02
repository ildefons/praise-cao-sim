"""Native AICon/YAFS white-box atlas for PRAISE first-science Phase 1.

The development atlas executes Fpre -> ParAll(A,B,C) -> Fpost for a small
explicit grid of physical (central provider service-instruction requirement,
provider heterogeneity) settings. ``Message.instructions`` on A/B/C denotes the
computational instructions required by the provider service for one invocation;
it is not the external root arrival workload. Admissibility regions are scanned
only after native trajectories have been reduced to top-level request ledgers.
No I1 card, M0, or M1 appears here.
"""
from __future__ import annotations

import argparse
import json
import logging.config
import random
import shutil
from pathlib import Path

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

from atlas_analysis import (
    scan_admissibility_regions_for_one_physical_setting,
    select_representative_regions_for_each_achievable_anchor_survival,
)

APPLICATION_NAME = "PraisePhase1WhiteboxAtlas"
SOURCE_MODULE = "Source"
PREPROCESS_MODULE = "Fpre"
PROVIDER_MODULES = ("ProviderA", "ProviderB", "ProviderC")
POSTPROCESS_MODULE = "Fpost"
ROOT_REQUEST_MESSAGE = "M.ROOT"
BRANCH_MESSAGE_NAMES = ("M.A", "M.B", "M.C")
JOIN_MESSAGE = "M.JOIN"
COMPOSITION_ID = "G0_PARALL"
SOURCE_NODE = 0
PREPROCESS_NODE = 1
PROVIDER_NODES = (2, 3, 4)
POSTPROCESS_NODE = 5


class ShortestPathForFixedReferenceGraph(Selection):
    """Select the unique shortest path to each fixed module deployment.

    Called by:
        - AICon/YAFS routing machinery through ``Selection.get_path``.
    """

    def get_path(self, sim, app_name, message, topology_src, alloc_DES, alloc_module, traffic, from_des):
        """Return one shortest path and destination DES for a message.

        The method name/signature are mandated by the YAFS ``Selection`` API.

        Called by:
            - AICon/YAFS core whenever a message requires routing.
        """
        destination_processes = alloc_module[app_name][message.dst]
        if len(destination_processes) != 1:
            raise RuntimeError(
                f"fixed Phase-1 graph expects one deployment for {message.dst}, "
                f"got {destination_processes}"
            )
        destination_process = destination_processes[0]
        destination_node = alloc_DES[destination_process]
        path = list(nx.shortest_path(sim.topology.G, source=topology_src, target=destination_node))
        return [path], [destination_process]


class FixedPlacementForPhase1ReferenceGraph(Placement):
    """Deploy Fpre, A/B/C, and Fpost on fixed distinct nodes.

    Provider DES processes receive the shared execution fraction ``x`` while
    deterministic Fpre/Fpost use execution fraction 1 and are QoS-neutral.

    Called by:
        - AICon/YAFS deployment machinery through ``Placement.initial_allocation``.
    """

    def __init__(self, name: str, provider_execution_fraction: float):
        """Store the provider execution fraction used during deployment.

        Called by:
            - ``execute_one_whitebox_trajectory`` in this module.
        """
        super().__init__(name)
        self.provider_execution_fraction = float(provider_execution_fraction)

    def initial_allocation(self, sim, app_name):
        """Deploy exactly one process for every physical service module.

        The method name/signature are mandated by the YAFS ``Placement`` API.

        Called by:
            - AICon/YAFS application deployment machinery.
        """
        services = sim.apps[app_name].services
        deployment = {
            PREPROCESS_MODULE: PREPROCESS_NODE,
            PROVIDER_MODULES[0]: PROVIDER_NODES[0],
            PROVIDER_MODULES[1]: PROVIDER_NODES[1],
            PROVIDER_MODULES[2]: PROVIDER_NODES[2],
            POSTPROCESS_MODULE: POSTPROCESS_NODE,
        }
        for module_name, node_id in deployment.items():
            deployed_processes = sim.deploy_module(
                app_name, module_name, services[module_name], [node_id]
            )
            if len(deployed_processes) != 1:
                raise RuntimeError(f"expected one DES for {module_name}, got {deployed_processes}")
            execution_fraction = (
                self.provider_execution_fraction if module_name in PROVIDER_MODULES else 1.0
            )
            sim.des_pct_instructions[deployed_processes[0]] = execution_fraction


def calculate_provider_instruction_means_for_physical_setting(
    center_instruction_mean: float,
    dispersion: float,
) -> tuple[float, float, float]:
    """Calculate symmetric A/B/C mean service-instruction requirements.

    ``center_instruction_mean`` is retained as the implementation/configuration
    name, but its scientific meaning is the central mean number of instructions
    required by a provider service to execute one invocation. ``dispersion``
    (delta) controls provider-to-provider heterogeneity in that mean; it is not
    the request-to-request stochastic variability, which is controlled
    separately by the frozen gamma CV. The periodic root workload is a separate
    fixed specification of invocation timing.

    Called by:
        - ``create_whitebox_application_for_physical_setting`` in this module.
        - ``enumerate_development_physical_settings`` in this module.
    """
    center = float(center_instruction_mean)
    delta = float(dispersion)
    if center <= 0.0:
        raise ValueError("center_instruction_mean must be positive")
    if not 0.0 <= delta < 1.0:
        raise ValueError("dispersion must satisfy 0 <= delta < 1")
    return center * (1.0 - delta), center, center * (1.0 + delta)


def create_whitebox_application_for_physical_setting(
    configuration: dict,
    center_instruction_mean: float,
    dispersion: float,
    trajectory_seed: int,
) -> Application:
    """Create one native composed G0 application for a physical atlas setting.

    A/B/C use identical service semantics. Their development-atlas difference is
    the mean of independent seeded gamma distributions attached natively to each
    branch ``Message.instructions``. Each realization is the computational work
    required by that provider service for one invocation, not an external root
    workload realization. The root workload remains the fixed periodic source
    configured separately below. L, C, and Q are never directly sampled.

    Called by:
        - ``execute_one_whitebox_trajectory`` in this module.
    """
    application = Application(name=APPLICATION_NAME)
    application.set_modules(
        [
            {SOURCE_MODULE: {"Type": Application.TYPE_SOURCE}},
            {PREPROCESS_MODULE: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {PROVIDER_MODULES[0]: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {PROVIDER_MODULES[1]: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {PROVIDER_MODULES[2]: {"RAM": 10, "Type": Application.TYPE_MODULE}},
            {POSTPROCESS_MODULE: {"RAM": 10, "Type": Application.TYPE_MODULE}},
        ]
    )

    root_request = Message(
        ROOT_REQUEST_MESSAGE,
        SOURCE_MODULE,
        PREPROCESS_MODULE,
        instructions=float(configuration["graph"]["pre_instructions"]),
        bytes=int(configuration["topology"]["request_bytes"]),
        qos=LinearQoS(L=0.0, R=1.0),
    )
    application.add_source_messages(root_request)

    provider_means = calculate_provider_instruction_means_for_physical_setting(
        center_instruction_mean, dispersion
    )
    branch_messages = []
    for branch_index, (module_name, message_name, provider_mean) in enumerate(
        zip(PROVIDER_MODULES, BRANCH_MESSAGE_NAMES, provider_means)
    ):
        branch_distribution = gamma_distribution(
            mean=float(provider_mean),
            cv=float(configuration["provider_family"]["instruction_cv"]),
            seed=int(trajectory_seed) * 100 + branch_index + 1,
            name=f"phase1_{message_name}_seed_{trajectory_seed}",
        )
        branch_message = Message(
            message_name,
            PREPROCESS_MODULE,
            module_name,
            instructions=branch_distribution,
            bytes=int(configuration["topology"]["branch_bytes"]),
            qos=LinearQoS(L=0.0, R=1.0),
        )
        branch_messages.append(branch_message)
        application.add_service_module_praise(
            PREPROCESS_MODULE,
            root_request,
            branch_message,
            fractional_selectivity,
            composition_id=COMPOSITION_ID,
            branch_id=branch_index,
            depends_on=(),
            threshold=1.0,
        )

    for module_name, branch_message in zip(PROVIDER_MODULES, branch_messages):
        application.add_service_module(module_name, branch_message)

    join_message = Message(
        JOIN_MESSAGE,
        application.compositions[COMPOSITION_ID]["controller_name"],
        POSTPROCESS_MODULE,
        instructions=float(configuration["graph"]["post_instructions"]),
        bytes=int(configuration["topology"]["join_bytes"]),
        qos=LinearQoS(L=0.0, R=1.0),
    )
    application.set_composition_output_praise(
        composition_id=COMPOSITION_ID,
        message_out=join_message,
    )
    application.add_service_module(POSTPROCESS_MODULE, join_message)
    return application


def create_fixed_topology_for_phase1_reference_graph(configuration: dict) -> Topology:
    """Create the simple symmetric fixed topology for the development atlas.

    Numerical values are explicitly development-only diagnostics and do not
    freeze the later scientific regime.

    Called by:
        - ``execute_one_whitebox_trajectory`` in this module.
    """
    effective_ipt = float(configuration["provider_family"]["effective_ipt"])
    cost_rate = float(configuration["provider_family"]["cost_rate"])
    bandwidth = float(configuration["topology"]["network_bw_mbps"])
    propagation = float(configuration["topology"]["network_pr"])
    entities = [
        {"id": SOURCE_NODE, "model": "source", "mytag": "source", "IPT": effective_ipt, "RAM": 4000, "COST": 0.0, "WATT": 0.0},
        {"id": PREPROCESS_NODE, "model": "fpre", "mytag": "fpre", "IPT": effective_ipt, "RAM": 4000, "COST": cost_rate, "WATT": 0.0},
        {"id": PROVIDER_NODES[0], "model": "provider-a", "mytag": "provider-a", "IPT": effective_ipt, "RAM": 4000, "COST": cost_rate, "WATT": 0.0},
        {"id": PROVIDER_NODES[1], "model": "provider-b", "mytag": "provider-b", "IPT": effective_ipt, "RAM": 4000, "COST": cost_rate, "WATT": 0.0},
        {"id": PROVIDER_NODES[2], "model": "provider-c", "mytag": "provider-c", "IPT": effective_ipt, "RAM": 4000, "COST": cost_rate, "WATT": 0.0},
        {"id": POSTPROCESS_NODE, "model": "fpost", "mytag": "fpost", "IPT": effective_ipt, "RAM": 4000, "COST": cost_rate, "WATT": 0.0},
    ]
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
    configuration: dict,
) -> pd.DataFrame:
    """Reduce native module metrics to one top-level row per logical request.

    PRAISE preserves root message IDs through the composition. Therefore Fpre,
    A/B/C, and Fpost rows for one logical request can be grouped by ``id``.
    ``L`` is source emission to Fpost completion and includes graph/runtime
    networking. ``C`` sums native ``COST(node)*service`` over all five physical
    service modules. ``Q`` is the minimum native module QoS.

    Called by:
        - ``execute_one_whitebox_trajectory`` in this module.
    """
    stop_time = float(configuration["horizon"]["simulation_stop_time"])
    metric_rows = Stats(defaultPath=trace_base).df.copy()
    if metric_rows.empty:
        raise RuntimeError("native simulation produced no metric rows")

    expected_modules = {
        PREPROCESS_MODULE,
        PROVIDER_MODULES[0],
        PROVIDER_MODULES[1],
        PROVIDER_MODULES[2],
        POSTPROCESS_MODULE,
    }
    root_rows = metric_rows[metric_rows["module"] == PREPROCESS_MODULE].copy()
    if root_rows.empty:
        raise RuntimeError("native trace contains no Fpre root-request rows")

    topology_information = simulation.topology.get_info()
    output_rows = []
    for root_row in root_rows.itertuples(index=False):
        request_id = int(root_row.id)
        request_rows = metric_rows[
            (metric_rows["id"] == request_id) & (metric_rows["module"].isin(expected_modules))
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
            possible_completion = float(post_rows.iloc[0]["time_out"])
            if possible_completion <= stop_time + 1e-12:
                module_counts = request_rows["module"].value_counts().to_dict()
                invalid_modules = [
                    module_name
                    for module_name in expected_modules
                    if int(module_counts.get(module_name, 0)) != 1
                ]
                if invalid_modules:
                    raise RuntimeError(
                        f"completed request {request_id} lacks exactly one row for {invalid_modules}"
                    )
                completion = possible_completion
                latency = completion - emission
                accumulated_cost = 0.0
                for _, metric_row in request_rows.iterrows():
                    node_id = int(metric_row["TOPO.dst"])
                    accumulated_cost += (
                        float(topology_information[node_id]["COST"]) * float(metric_row["service"])
                    )
                cost = accumulated_cost
                quality = float(request_rows["qos"].min())

        output_rows.append(
            {
                "request_id": request_id,
                "emission": emission,
                "completion": completion,
                "completed_by_stop": completion is not None,
                "status": "completed" if completion is not None else "incomplete",
                "L": latency,
                "C": cost,
                "Q": quality,
                "stop_time": stop_time,
            }
        )
    return pd.DataFrame(output_rows).sort_values(["emission", "request_id"]).reset_index(drop=True)


def execute_one_whitebox_trajectory(
    configuration: dict,
    center_instruction_mean: float,
    dispersion: float,
    trajectory_seed: int,
    trajectory_output_directory: Path,
) -> pd.DataFrame:
    """Execute one native AICon/YAFS trajectory of the composed physical graph.

    Called by:
        - ``execute_development_whitebox_atlas_simulations`` in this module.
    """
    random.seed(int(trajectory_seed))
    np.random.seed(int(trajectory_seed))
    trajectory_output_directory.mkdir(parents=True, exist_ok=True)
    trace_base = str(trajectory_output_directory / "sim_trace")

    topology = create_fixed_topology_for_phase1_reference_graph(configuration)
    application = create_whitebox_application_for_physical_setting(
        configuration, center_instruction_mean, dispersion, trajectory_seed
    )
    placement = FixedPlacementForPhase1ReferenceGraph(
        "phase1_fixed_reference_placement",
        provider_execution_fraction=float(configuration["provider_family"]["x"]),
    )
    population = Statical("phase1_periodic_population")
    population.set_src_control(
        {
            "model": "source",
            "number": 1,
            "message": application.get_message(ROOT_REQUEST_MESSAGE),
            "distribution": deterministic_distribution(
                name=f"phase1_period_{configuration['workload']['period']}",
                time=float(configuration["workload"]["period"]),
            ),
        }
    )

    simulation = Sim(topology, default_results_path=trace_base)
    empty_management_network = ManagementAgentNetwork("management_network", [], simulation)
    simulation.deploy_app_agentic(
        application,
        placement,
        population,
        ShortestPathForFixedReferenceGraph(),
        empty_management_network,
    )
    simulation.run(
        float(configuration["horizon"]["simulation_stop_time"]),
        show_progress_monitor=False,
    )
    request_ledger = extract_top_level_request_ledger_from_native_trace(
        simulation, trace_base, configuration
    )
    request_ledger.insert(0, "seed", int(trajectory_seed))
    request_ledger.to_csv(trajectory_output_directory / "top_level_request_ledger.csv", index=False)
    return request_ledger


def enumerate_development_physical_settings(configuration: dict) -> list[dict]:
    """Enumerate the development-only ``(Dbar, delta)`` provider grid.

    Here ``Dbar`` is the central mean service-instruction requirement per
    provider invocation and ``delta`` is provider-to-provider heterogeneity in
    that mean. Neither quantity is the periodic root workload, which remains
    fixed across the atlas.

    Called by:
        - ``execute_development_whitebox_atlas_simulations`` in this module.
        - ``test_whitebox_atlas_configuration.py``.
    """
    settings = []
    for center in configuration["physical_atlas"]["center_instruction_means"]:
        for dispersion in configuration["physical_atlas"]["dispersions"]:
            provider_means = calculate_provider_instruction_means_for_physical_setting(
                center, dispersion
            )
            settings.append(
                {
                    "physical_setting_id": f"D{float(center):.0f}_d{float(dispersion):.3f}",
                    "center_instruction_mean": float(center),
                    "dispersion": float(dispersion),
                    "provider_a_instruction_mean": provider_means[0],
                    "provider_b_instruction_mean": provider_means[1],
                    "provider_c_instruction_mean": provider_means[2],
                }
            )
    return settings


def execute_development_whitebox_atlas_simulations(
    configuration: dict,
    output_directory: Path,
    maximum_physical_settings: int | None,
    maximum_trajectories_per_setting: int | None,
) -> pd.DataFrame:
    """Generate and cache native white-box request ledgers for the atlas grid.

    Called by:
        - ``execute_command_line_phase1_atlas`` in this module.
    """
    settings = enumerate_development_physical_settings(configuration)
    if maximum_physical_settings is not None:
        settings = settings[: int(maximum_physical_settings)]
    seeds = list(map(int, configuration["development_seeds"]))
    if maximum_trajectories_per_setting is not None:
        seeds = seeds[: int(maximum_trajectories_per_setting)]

    all_ledgers = []
    for setting in settings:
        setting_id = str(setting["physical_setting_id"])
        for trajectory_index, seed in enumerate(seeds):
            trajectory_directory = (
                output_directory
                / "trajectories"
                / setting_id
                / f"trajectory_{trajectory_index:02d}_seed_{seed}"
            )
            ledger = execute_one_whitebox_trajectory(
                configuration,
                float(setting["center_instruction_mean"]),
                float(setting["dispersion"]),
                seed,
                trajectory_directory,
            )
            ledger.insert(0, "trajectory", trajectory_index)
            ledger.insert(0, "dispersion", float(setting["dispersion"]))
            ledger.insert(0, "center_instruction_mean", float(setting["center_instruction_mean"]))
            ledger.insert(0, "physical_setting_id", setting_id)
            all_ledgers.append(ledger)

    if not all_ledgers:
        raise RuntimeError("no Phase-1 development trajectories were executed")
    combined = pd.concat(all_ledgers, ignore_index=True)
    combined.to_csv(output_directory / "all_top_level_request_ledgers.csv", index=False)
    pd.DataFrame(settings).to_csv(output_directory / "physical_settings.csv", index=False)
    return combined


def build_phase1_horizon_grid(configuration: dict) -> list[float]:
    """Build the inclusive [0,240] grid and guarantee H*=120 is present.

    Called by:
        - ``scan_all_physical_settings_and_write_atlas_outputs`` in this module.
        - ``test_whitebox_atlas_configuration.py``.
    """
    minimum = float(configuration["horizon"]["minimum"])
    maximum = float(configuration["horizon"]["maximum"])
    step = float(configuration["horizon"]["grid_step"])
    if minimum != 0.0 or maximum != 240.0 or step <= 0.0:
        raise ValueError("development atlas requires positive-step horizon domain [0,240]")
    grid = np.arange(minimum, maximum + step * 0.5, step, dtype=float).tolist()
    anchor = float(configuration["admissibility_scan"]["anchor_horizon"])
    if not any(abs(value - anchor) <= 1e-12 for value in grid):
        grid.append(anchor)
        grid.sort()
    return grid


def scan_all_physical_settings_and_write_atlas_outputs(
    all_request_ledgers: pd.DataFrame,
    configuration: dict,
    output_directory: Path,
) -> None:
    """Scan offline ARs and write achievable-sigma and representative tables.

    Called by:
        - ``execute_command_line_phase1_atlas`` in this module.
    """
    horizons = build_phase1_horizon_grid(configuration)
    anchor = float(configuration["admissibility_scan"]["anchor_horizon"])
    quality_threshold = float(configuration["provider_family"]["x"])
    stop_time = float(configuration["horizon"]["simulation_stop_time"])
    region_summaries = []
    survival_curves = []

    for setting_id, setting_ledger in all_request_ledgers.groupby("physical_setting_id", sort=True):
        summary, curves = scan_admissibility_regions_for_one_physical_setting(
            setting_ledger,
            physical_setting_id=str(setting_id),
            center_instruction_mean=float(setting_ledger["center_instruction_mean"].iloc[0]),
            dispersion=float(setting_ledger["dispersion"].iloc[0]),
            quality_threshold=quality_threshold,
            anchor_horizon=anchor,
            horizons=horizons,
            stop_time=stop_time,
            threshold_relative_epsilon=float(
                configuration["admissibility_scan"]["threshold_relative_epsilon"]
            ),
            unconstrained_threshold_multiplier=float(
                configuration["admissibility_scan"]["include_unconstrained_threshold_multiplier"]
            ),
        )
        region_summaries.append(summary)
        survival_curves.append(curves)

    combined_summary = pd.concat(region_summaries, ignore_index=True)
    combined_curves = pd.concat(survival_curves, ignore_index=True)
    representatives = select_representative_regions_for_each_achievable_anchor_survival(
        combined_summary,
        int(configuration["admissibility_scan"]["representatives_per_anchor_survival"]),
    )
    achievable_sigmas = (
        combined_summary.groupby(["physical_setting_id", "sigma_anchor"], as_index=False)
        .agg(
            number_of_regions=("region_id", "count"),
            minimum_l_max=("l_max", "min"),
            maximum_l_max=("l_max", "max"),
            minimum_c_max=("c_max", "min"),
            maximum_c_max=("c_max", "max"),
        )
        .sort_values(["physical_setting_id", "sigma_anchor"])
    )
    combined_summary.to_csv(output_directory / "admissibility_regions.csv", index=False)
    combined_curves.to_csv(output_directory / "survival_curves.csv", index=False)
    representatives.to_csv(output_directory / "representative_regions_by_sigma.csv", index=False)
    achievable_sigmas.to_csv(output_directory / "achievable_sigmas.csv", index=False)
    print("PHASE1_DEVELOPMENT_ATLAS_SCAN_PASS")
    print(achievable_sigmas.to_string(index=False))


def load_and_validate_development_atlas_configuration(configuration_path: Path) -> dict:
    """Load the atlas config and reject scientific-budget or semantics drift.

    Called by:
        - ``execute_command_line_phase1_atlas`` in this module.
        - ``test_whitebox_atlas_configuration.py``.
    """
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    if configuration.get("configuration_status") != "DEVELOPMENT_ATLAS_SMOKE_ONLY":
        raise ValueError("runner accepts only DEVELOPMENT_ATLAS_SMOKE_ONLY config")
    if configuration.get("scientific_evidence") is not False:
        raise ValueError("development atlas must remain marked non-scientific")
    seeds = list(configuration["development_seeds"])
    if int(configuration["development_trajectory_count"]) != 10 or len(seeds) != 10:
        raise ValueError("development atlas must use exactly N=10 seeds")
    if len(set(map(int, seeds))) != len(seeds):
        raise ValueError("development seeds must be unique")
    if configuration["provider_family"].get("direct_sampling_of_L_C_Q") is not False:
        raise ValueError("L/C/Q must remain simulator-derived")
    if float(configuration["admissibility_scan"]["anchor_horizon"]) != 120.0:
        raise ValueError("H*=120 is frozen")
    if float(configuration["horizon"]["simulation_stop_time"]) < 240.0:
        raise ValueError("simulation stop must cover H=240")
    return configuration


def execute_command_line_phase1_atlas() -> None:
    """Execute the development simulator atlas and its offline AR scan.

    Called by:
        - Python ``__main__`` entry point of ``whitebox_atlas.py``.
    """
    module_directory = Path(__file__).resolve().parent
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument(
        "--config", type=Path, default=module_directory / "config_phase1_atlas_smoke.json"
    )
    argument_parser.add_argument(
        "--output", type=Path, default=module_directory / "results" / "development_atlas"
    )
    argument_parser.add_argument("--max-physical-settings", type=int, default=None)
    argument_parser.add_argument("--max-trajectories-per-setting", type=int, default=None)
    argument_parser.add_argument("--scan-existing-ledger", type=Path, default=None)
    argument_parser.add_argument("--clean", action="store_true")
    arguments = argument_parser.parse_args()

    logging_configuration = module_directory / "logging.ini"
    if logging_configuration.exists():
        logging.config.fileConfig(logging_configuration)
    configuration = load_and_validate_development_atlas_configuration(arguments.config)
    output_directory = arguments.output.resolve()
    if arguments.clean and output_directory.exists() and arguments.scan_existing_ledger is None:
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "effective_config.json").write_text(
        json.dumps(configuration, indent=2), encoding="utf-8"
    )

    if arguments.scan_existing_ledger is None:
        all_request_ledgers = execute_development_whitebox_atlas_simulations(
            configuration,
            output_directory,
            arguments.max_physical_settings,
            arguments.max_trajectories_per_setting,
        )
    else:
        all_request_ledgers = pd.read_csv(arguments.scan_existing_ledger)
    scan_all_physical_settings_and_write_atlas_outputs(
        all_request_ledgers, configuration, output_directory
    )


if __name__ == "__main__":
    execute_command_line_phase1_atlas()
