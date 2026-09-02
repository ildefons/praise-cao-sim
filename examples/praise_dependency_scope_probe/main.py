# -*- coding: utf-8 -*-
"""
PRAISE dependency-scope isolation stress test.

Purpose
-------
Validate that branch completion/dependency bookkeeping is scoped to the
owning composition.

Outer composition F0:
    branch 0 -> ServiceSlow, depends_on=()
    branch 1 -> nested composition F1, depends_on=()
    branch 2 -> ServiceDependent, depends_on=(0, 1)

Inner composition F1:
    branch 0 -> ServiceInner0, depends_on=()
    branch 1 -> ServiceInner1, depends_on=()

The branch IDs 0 and 1 are deliberately reused in F0 and F1.

The timing is adversarial:
    * F0.b0 is deliberately slow.
    * F1.b0 and F1.b1 finish first.
    * F1 joins and its single output completes F0.b1.
    * F0.b2 MUST remain blocked until F0.b0 also completes.

A scope bug that lets inner completions satisfy outer dependencies can
therefore activate M.DEP prematurely. The selector contains assertions that
make that failure explicit.

This probe changes no shared YAFS/AICon substrate.
"""

import logging.config
import os
import random
import time
from pathlib import Path

import networkx as nx
import numpy as np

from yafs.application import (
    Application,
    Message,
    LinearQoS,
    fractional_selectivity
)
from yafs.core import Sim
from yafs.distribution import deterministic_distribution, uniformDistribution
from yafs.management_network import ManagementAgent, ManagementAgentNetwork
from yafs.placement import Placement
from yafs.population import Statical
from yafs.selection import Selection
from yafs.stats import Stats
from yafs.topology import Topology


class ActuatorAgent(ManagementAgent):
    """Passive management agent retained from the validated PRAISE probes."""

    def agent_behavior(self, collected_metrics):
        return []


class ScopeIsolationPath(Selection):
    """
    Shortest-path selector with scope-isolation assertions.

    The selector observes messages when they are routed. For each root request,
    it records which OUTER F0 completion messages have already been emitted.

    If M.DEP is ever routed before both outer prerequisites have emitted their
    own F0 completion messages, the probe fails immediately.
    """

    def __init__(self):
        super().__init__()
        self.outer_completion_messages_seen = {}

    def get_path(
            self,
            sim,
            app_name,
            message,
            topology_src,
            alloc_DES,
            alloc_module,
            traffic,
            from_des):

        node_src = topology_src
        DES_dst = alloc_module[app_name][message.dst]

        path_tuple = tuple(message.composition_path)

        print(
            "PATH_PROBE",
            "time=", sim.env.now,
            "message=", message.name,
            "id=", message.id,
            "composition_path=", message.composition_path
        )

        request_seen = self.outer_completion_messages_seen.setdefault(
            message.id,
            set()
        )

        # Record only OUTER-F0 completion events.
        # Inner F1 completions must never count toward this set.
        if message.name == "__PRAISE_COMPLETE__F0__0":
            request_seen.add(0)

        elif message.name == "__PRAISE_COMPLETE__F0__1":
            request_seen.add(1)

        # Structural path assertions for the decisive messages.
        if message.name == "M.INNER_OUT":
            assert path_tuple == (("F0", 1),), (
                "Inner F1 join did not pop exactly one frame: "
                f"path={path_tuple}"
            )

        elif message.name == "M.DEP":
            assert path_tuple == (("F0", 2),), (
                "Dependent outer branch has wrong composition scope: "
                f"path={path_tuple}"
            )

            assert request_seen == {0, 1}, (
                "DEPENDENCY-SCOPE FAILURE: M.DEP activated before both "
                "OUTER F0 prerequisites completed. "
                f"request_id={message.id}, "
                f"outer_completion_messages_seen={sorted(request_seen)}"
            )

            print(
                "SCOPE_ASSERTION_PASS",
                "request_id=", message.id,
                "M.DEP activated only after outer F0 completions {0,1}"
            )

        elif message.name == "M.OUT":
            assert path_tuple == (), (
                "Final F0 output did not pop the outer frame: "
                f"path={path_tuple}"
            )

        bestPath = []
        bestDES = []

        for des in DES_dst:
            dst_node = alloc_DES[des]
            path = list(
                nx.shortest_path(
                    sim.topology.G,
                    source=node_src,
                    target=dst_node
                )
            )
            bestPath = [path]
            bestDES = [des]

        return bestPath, bestDES


class ScopeIsolationPlacement(Placement):
    """
    Fixed one-module-per-device deployment.

    Camera:            node 1
    ServiceA:          node 0   (F0 origin; F0 controller colocates here)
    ServiceSlow:       node 2   (F0.b0; deliberately slow)
    ServiceX:          node 3   (F0.b1 / F1 origin; F1 controller here)
    ServiceInner0:     node 4   (F1.b0)
    ServiceInner1:     node 5   (F1.b1)
    ServiceInnerOut:   node 6   (single F1 output; completes F0.b1)
    ServiceDependent:  node 7   (F0.b2, depends_on=(0, 1))
    ServiceOut:        node 8   (single F0 output)
    """

    def initial_allocation(self, sim, app_name):

        app = sim.apps[app_name]
        services = app.services

        deployment = {
            "ServiceA": 0,
            "ServiceSlow": 2,
            "ServiceX": 3,
            "ServiceInner0": 4,
            "ServiceInner1": 5,
            "ServiceInnerOut": 6,
            "ServiceDependent": 7,
            "ServiceOut": 8,
        }

        for module, node_id in deployment.items():
            des_ids = sim.deploy_module(
                app_name,
                module,
                services[module],
                [node_id]
            )

            # QoS semantic probe: apply 50% of nominal instructions only to
            # the single deployed ServiceX instance. This is set here because
            # the DES id exists immediately after deploy_module() returns.
            if module == "ServiceX":
                assert len(des_ids) == 1, (
                    f"Expected exactly one ServiceX DES, got {des_ids}"
                )

                service_x_des = des_ids[0]
                sim.des_pct_instructions[service_x_des] = 0.5

                print(
                    "QOS_PROBE_SETUP",
                    "ServiceX DES=", service_x_des,
                    "node=", node_id,
                    "pct_instructions=", 0.5
                )


RANDOM_SEED = 1


def create_application():

    a = Application(name="PraiseDependencyScopeProbe")

    a.set_modules([
        {"Camera": {
            "Type": Application.TYPE_SOURCE
        }},
        {"ServiceA": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceSlow": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceX": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceInner0": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceInner1": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceInnerOut": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceDependent": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceOut": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
    ])

    # External/root request: Camera -> outer composition origin ServiceA.
    m_a = Message(
        "M.A",
        "Camera",
        "ServiceA",
        instructions=20 * 10**6,
        bytes=1000
    )

    # -------------------------------------------------
    # OUTER F0
    # -------------------------------------------------

    # F0 branch 0: deliberately slow ordinary branch.
    #
    # ServiceSlow runs at 1e9 IPT, so 12e9 instructions creates a very large
    # timing margin relative to the inner branches. This is intentional:
    # the test is semantic, not a performance comparison.
    m_slow = Message(
        "M.SLOW",
        "ServiceA",
        "ServiceSlow",
        instructions=12 * 10**9,
        bytes=1000
    )

    # F0 branch 1: enters nested composition F1 at ServiceX.
    m_x_instructions = uniformDistribution(
        18 * 10**6,
        22 * 10**6,
        seed=123,
        name="M.X.instructions"
    )

    m_x = Message(
        "M.X",
        "ServiceA",
        "ServiceX",
        instructions=m_x_instructions,
        bytes=1000,
        qos=LinearQoS(L=0.0, R=1.0)
    )

    a.add_source_messages(m_a)

    # Root F0 branch 0.
    a.add_service_module_praise(
        "ServiceA",
        m_a,
        m_slow,
        fractional_selectivity,
        composition_id="F0",
        branch_id=0,
        depends_on=(),
        threshold=1.0
    )

    # Root F0 branch 1.
    a.add_service_module_praise(
        "ServiceA",
        m_a,
        m_x,
        fractional_selectivity,
        composition_id="F0",
        branch_id=1,
        depends_on=(),
        threshold=1.0
    )

    # F0 branch 2 is semantically an ordinary sibling branch.
    #
    # Its logical source remains the F0 composition origin (ServiceA).
    # depends_on changes only WHEN the branch activates. The composition
    # controller performs the delayed runtime release, but it does not become
    # the logical Message.src.
    m_dep = Message(
        "M.DEP",
        "ServiceA",
        "ServiceDependent",
        instructions=20 * 10**6,
        bytes=1000
    )

    a.add_service_module_praise(
        "ServiceA",
        m_a,
        m_dep,
        fractional_selectivity,
        composition_id="F0",
        branch_id=2,
        depends_on=(0, 1),
        threshold=1.0
    )

    # -------------------------------------------------
    # INNER F1
    #
    # Deliberately reuse local branch IDs 0 and 1.
    # These IDs belong only to F1 and must never satisfy F0 dependencies.
    # -------------------------------------------------

    m_inner0 = Message(
        "M.INNER0",
        "ServiceX",
        "ServiceInner0",
        instructions=10 * 10**6,
        bytes=1000
    )

    m_inner1 = Message(
        "M.INNER1",
        "ServiceX",
        "ServiceInner1",
        instructions=12 * 10**6,
        bytes=1000
    )

    a.add_service_module_praise(
        "ServiceX",
        m_x,
        m_inner0,
        fractional_selectivity,
        composition_id="F1",
        branch_id=0,
        depends_on=(),
        threshold=1.0
    )

    a.add_service_module_praise(
        "ServiceX",
        m_x,
        m_inner1,
        fractional_selectivity,
        composition_id="F1",
        branch_id=1,
        depends_on=(),
        threshold=1.0
    )

    # Single output of COMPLETE F1.
    #
    # The F1 join pops exactly one frame. Therefore M.INNER_OUT must carry
    # only the parent F0 branch-1 frame:
    #
    #     (("F0", 1),)
    #
    # Consuming this message at ServiceInnerOut completes F0.b1.
    m_inner_out = Message(
        "M.INNER_OUT",
        a.compositions["F1"]["controller_name"],
        "ServiceInnerOut",
        instructions=0,
        bytes=1000
    )

    a.set_composition_output_praise(
        composition_id="F1",
        message_out=m_inner_out
    )

    # Single output of COMPLETE F0.
    m_out = Message(
        "M.OUT",
        a.compositions["F0"]["controller_name"],
        "ServiceOut",
        instructions=0,
        bytes=1000
    )

    a.set_composition_output_praise(
        composition_id="F0",
        message_out=m_out
    )

    # -------------------------------------------------
    # Static declaration audit
    # -------------------------------------------------

    for composition_id in ("F0", "F1"):
        composition = a.compositions[composition_id]

        print(
            "COMPOSITION_PROBE",
            "composition=", composition_id,
            "origin_module=", composition["origin_module"],
            "message_in=", composition["message_in"].name,
            "controller_name=", composition["controller_name"],
            "branches=", sorted(composition["branches"].keys()),
            "message_out=", composition["message_out"].name
        )

        for branch_id, registration in sorted(
                composition["branches"].items()):
            print(
                "BRANCH_PROBE",
                "composition=", composition_id,
                "branch=", branch_id,
                "depends_on=", registration["depends_on"],
                "message_out=", registration["message_out"].name
            )

    # -------------------------------------------------
    # Terminal / ordinary services
    # -------------------------------------------------

    a.add_service_module("ServiceSlow", m_slow)
    a.add_service_module("ServiceInner0", m_inner0)
    a.add_service_module("ServiceInner1", m_inner1)
    a.add_service_module("ServiceInnerOut", m_inner_out)
    a.add_service_module("ServiceDependent", m_dep)
    a.add_service_module("ServiceOut", m_out)

    return a


def create_json_topology():

    topology_json = {
        "entity": [],
        "link": []
    }

    # ServiceA is kept slower, matching the scale used by the validated probes.
    service_a_dev = {
        "id": 0,
        "model": "service-a-device",
        "mytag": "service-a",
        "IPT": 300 * 10**5,
        "RAM": 40000,
        "COST": 3,
        "WATT": 20.0
    }

    sensor_dev = {
        "id": 1,
        "model": "sensor-device",
        "IPT": 100 * 10**6,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    service_slow_dev = {
        "id": 2,
        "model": "service-slow-device",
        "IPT": 100 * 10**7,   # 1e9 IPT
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    service_x_dev = {
        "id": 3,
        "model": "service-x-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    service_inner0_dev = {
        "id": 4,
        "model": "service-inner0-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    service_inner1_dev = {
        "id": 5,
        "model": "service-inner1-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    service_inner_out_dev = {
        "id": 6,
        "model": "service-inner-out-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    service_dependent_dev = {
        "id": 7,
        "model": "service-dependent-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    service_out_dev = {
        "id": 8,
        "model": "service-out-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    topology_json["entity"].extend([
        service_a_dev,
        sensor_dev,
        service_slow_dev,
        service_x_dev,
        service_inner0_dev,
        service_inner1_dev,
        service_inner_out_dev,
        service_dependent_dev,
        service_out_dev
    ])

    # Keep all links simple. The semantic ordering comes from the intentionally
    # large ServiceSlow execution time, not from delicate network timing.

    topology_json["link"].extend([
        # Camera -> ServiceA
        {"s": 1, "d": 0, "BW": 10, "PR": 1},

        # F0 root branches
        {"s": 0, "d": 2, "BW": 10, "PR": 1},  # ServiceA -> ServiceSlow
        {"s": 0, "d": 3, "BW": 10, "PR": 1},  # ServiceA -> ServiceX

        # F1 branches
        {"s": 3, "d": 4, "BW": 10, "PR": 1},  # ServiceX -> ServiceInner0
        {"s": 3, "d": 5, "BW": 10, "PR": 1},  # ServiceX -> ServiceInner1

        # F1 single output
        {"s": 3, "d": 6, "BW": 10, "PR": 1},

        # F0 dependent branch and final output
        {"s": 0, "d": 7, "BW": 10, "PR": 1},
        {"s": 0, "d": 8, "BW": 10, "PR": 1},
    ])

    return topology_json


def main(simulated_time):

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    folder_results = Path("results/")
    folder_results.mkdir(parents=True, exist_ok=True)
    folder_results = str(folder_results) + "/"

    # TOPOLOGY
    t = Topology()
    t_json = create_json_topology()
    t.load(t_json)
    nx.write_gexf(t.G, folder_results + "graph_main1")

    # APPLICATION
    app = create_application()

    # PLACEMENT
    placement = ScopeIsolationPlacement("scope-isolation-placement")

    # POPULATION
    pop = Statical("Statical")

    # The validated probes emit their first deterministic request after one
    # distribution period. Using a long period gives exactly one root request
    # during the default 140-time-unit run: at t=100, with the next at t=200.
    dDistribution = deterministic_distribution(
        name="Deterministic",
        time=100
    )

    pop.set_src_control({
        "model": "sensor-device",
        "number": 1,
        "message": app.get_message("M.A"),
        "distribution": dDistribution
    })

    # SELECTOR + semantic assertions
    selectorPath = ScopeIsolationPath()

    # SIMULATION ENGINE
    stop_time = simulated_time
    sim = Sim(t, default_results_path=folder_results + "sim_trace")

    # Keep the same passive management-network setup used by the validated
    # probes. The agent sleep period is much longer than this probe run.
    agent_configs_json = [
        {
            "node_id": 3,
            "agent_type": ActuatorAgent,
            "sleep_time": 500,
            "instructions_per_wakeup": 10 * 10 * 10**6,
            "agent_ipt_percentage": 0.5,
            "observable_node_ids": [3, 0],
            "metrics": {
                "service_node_utilization": {
                    "module": "yafs.management_network",
                    "class": "ServiceNodeUtilization"
                },
                "agent_node_utilization": {
                    "module": "yafs.management_network",
                    "class": "AgentNodeUtilization"
                },
                "node_average_waiting_time": {
                    "module": "yafs.management_network",
                    "class": "NodeAverageWaitingTime"
                },
                "node_request_waiting_in": {
                    "module": "yafs.management_network",
                    "class": "NodeRequestsWaitingIn"
                },
                "node_requests_out": {
                    "module": "yafs.management_network",
                    "class": "NodeRequestsOut"
                },
                "net_buffer_size": {
                    "module": "yafs.management_network",
                    "class": "NetBufferSize"
                },
                "node_nominalwatt": {
                    "module": "yafs.management_network",
                    "class": "NodeNominalWatt"
                },
                "linear_cost_buyya": {
                    "module": "yafs.management_network",
                    "class": "LinearCostBuyya",
                    "params": {
                        "cost_alpha": 1.0
                    }
                }
            }
        }
    ]

    management_network = ManagementAgentNetwork(
        "management_network",
        agent_configs_json,
        sim
    )

    sim.deploy_app_agentic(
        app,
        placement,
        pop,
        selectorPath,
        management_network
    )

    # RUN
    sim.run(stop_time, show_progress_monitor=False)
    sim.print_debug_assignaments()

    # A valid run must have reached the dependent branch exactly once.
    # With the single-root-request schedule, there should be one request key
    # whose observed outer completion set is exactly {0, 1}.
    completed_outer_sets = [
        seen
        for seen in selectorPath.outer_completion_messages_seen.values()
        if seen
    ]

    assert completed_outer_sets, (
        "Probe did not observe any outer F0 completion events."
    )

    assert any(seen == {0, 1} for seen in completed_outer_sets), (
        "Probe ended without observing both outer F0 prerequisites "
        f"for a request: {completed_outer_sets}"
    )

    print(
        "\nSCOPE_PROBE_PASS",
        "Inner F1 branch IDs 0/1 did not prematurely satisfy "
        "outer F0 dependency (0,1)."
    )

    # STATS
    mypath = folder_results + "sim_trace"
    m = Stats(defaultPath=mypath)

    # -------------------------------------------------
    # Integrated ServiceX stochastic-instruction + cost probe
    #
    # M.X nominal instructions are sampled by Message.instantiate() from
    # uniformDistribution(18e6, 22e6, seed=123).
    #
    # For ServiceX:
    #   x = 0.5
    #   node IPT = 1e9
    #   the passive management agent reserves 50% of node IPT
    #
    # Thus:
    #   available_IPT = 0.5e9
    #   D_exec = 0.5 * D_nominal
    #   t_service = D_exec / available_IPT = D_nominal / 1e9
    #
    # Therefore the realized nominal instruction draw can be reconstructed
    # directly from the native service trace as:
    #   D_nominal = t_service * 1e9
    #
    # Per-request native operating cost is:
    #   C_request = COST(node) * t_service
    # -------------------------------------------------

    service_x_rows = m.df[m.df["module"] == "ServiceX"]

    assert len(service_x_rows) == 1, (
        "SERVICE_X_PROBE expected exactly one ServiceX invocation, "
        f"got {len(service_x_rows)}"
    )

    service_x_row = service_x_rows.iloc[0]

    service_x_node = int(service_x_row["TOPO.dst"])
    service_x_time = float(service_x_row["service"])
    service_x_cost_rate = float(
        t.get_info()[service_x_node]["COST"]
    )

    service_x_nominal_instructions = service_x_time * 1e9
    service_x_request_cost = (
        service_x_cost_rate * service_x_time
    )

    print(
        "\nINSTRUCTION_DISTRIBUTION_PROBE",
        "module=", "ServiceX",
        "service_time=", service_x_time,
        "reconstructed_nominal_instructions=",
        service_x_nominal_instructions
    )

    assert 18 * 10**6 <= service_x_nominal_instructions <= 22 * 10**6, (
        "MESSAGE_INSTANTIATE distribution failure: reconstructed "
        "ServiceX nominal instructions are outside the configured "
        "[18e6, 22e6] support. "
        f"got {service_x_nominal_instructions}"
    )

    print(
        "MESSAGE_INSTANTIATE_DISTRIBUTION_PASS",
        "ServiceX instruction draw lies inside [18e6, 22e6]"
    )

    print(
        "\nCOST_PROBE",
        "module=", "ServiceX",
        "node=", service_x_node,
        "service_time=", service_x_time,
        "cost_rate=", service_x_cost_rate,
        "request_cost=", service_x_request_cost
    )

    # Cost is no longer expected to be the old fixed 0.06 because M.X
    # nominal instruction demand is now stochastic.
    assert service_x_request_cost >= 0.0, (
        "COST_PROBE failure: per-request cost must be non-negative"
    )

    print(
        "COST_PROBE_PASS",
        "ServiceX request cost = COST(node) * service_time"
    )

    print("\n\t- Network saturation -")
    print("\t\tAverage waiting messages : %i" %
          m.average_messages_not_transmitted())
    print("\t\tPeak of waiting messages : %i" %
          m.peak_messages_not_transmitted())
    print("\t\tTOTAL messages not transmitted: %i" %
          m.messages_not_transmitted())

    print("\n\t- Stats of each service deployed -")
    print(m.get_df_modules())
    print(m.get_df_service_utilization("ServiceA", simulated_time))

    print("\n\t- Stats of each module deployed (except sources) -")
    print(m.get_df_modules())

    print("\n\t- Stats of each management agent deployed -")
    print(m.get_df_agent_modules())


if __name__ == '__main__':

    logging.config.fileConfig(os.getcwd() + '/logging.ini')

    start_time = time.time()
    main(simulated_time=140)

    print("\n--- %s seconds ---" % (time.time() - start_time))
