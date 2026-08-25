"""
    PRAISE dependency-barrier stress test.

    One Par scope F1 with three sibling branches:

        branch 0 -> ServiceB, depends_on=()
        branch 1 -> ServiceC, depends_on=()
        branch 2 -> ServiceE, depends_on=(0, 1)

    The F1 controller must activate branch 2 only after it has observed
    completion of branches 0 and 1 for the same request.

    F1 emits one final composition output M.OUT -> ServiceD only after
    branches 0, 1 and 2 have all completed.

    @author: Ildefons Magrans de Abril
"""

import random
import networkx as nx
from pathlib import Path
import time
import numpy as np

from yafs.core import Sim
from yafs.application import Application, Message
from yafs.population import *
from yafs.topology import Topology
from yafs.stats import Stats
from yafs.distribution import deterministic_distribution
from yafs.application import fractional_selectivity
from yafs.placement import Placement
from yafs.selection import Selection

# ILDE: added as part of the agent management network
from yafs.management_network import (
    ManagementAgent,
    ManagementAgentNetwork,
)


# ---------------------------------------------------------------------
# Management agents retained from the existing PRAISE probe structure
# ---------------------------------------------------------------------

class CloudAgent(ManagementAgent):
    def __custom_init__(self):
        self.state_id = 0

    def agent_behavior(self, collected_metrics):
        myactions2 = self.actions["discrete_node_ipt"]

        if self.sim.env.now >= 2000 and self.state_id == 0:
            self.state_id = 1
            myactions2(action_id=1, node_id=self.node_id)
        elif self.sim.env.now >= 4000 and self.state_id == 1:
            self.state_id = 2
            myactions2(action_id=0, node_id=self.node_id)
        elif self.state_id == 2:
            sublist_metrics = [
                item
                for item in collected_metrics
                if item["metric"] == "NodeAverageWaitingTime"
                and item["node_id"] == self.node_id
            ]
            if sublist_metrics[0]["value"] > 550:
                myactions2(action_id=1, node_id=self.node_id)
            if sublist_metrics[0]["value"] < 200:
                myactions2(action_id=0, node_id=self.node_id)


class SensorAgent(ManagementAgent):
    def agent_behavior(self, collected_metrics):
        return []


class ActuatorAgent(ManagementAgent):
    def agent_behavior(self, collected_metrics):
        return []


# ---------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------

class MinimunPath(Selection):

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
        """
        Compute the shortest path from the message's current topology node
        to the deployed destination module.
        """

        node_src = topology_src
        DES_dst = alloc_module[app_name][message.dst]

        # PRAISE execution-semantics probe.
        print(
            "PATH_PROBE",
            "time=", sim.env.now,
            "message=", message.name,
            "id=", message.id,
            "composition_path=", message.composition_path,
        )

        bestPath = []
        bestDES = []

        for des in DES_dst:
            dst_node = alloc_DES[des]
            path = list(
                nx.shortest_path(
                    sim.topology.G,
                    source=node_src,
                    target=dst_node,
                )
            )
            bestPath = [path]
            bestDES = [des]

        return bestPath, bestDES


# ---------------------------------------------------------------------
# Fixed placement for the barrier probe
# ---------------------------------------------------------------------

class BarrierPlacement(Placement):
    """
    Fixed deployment for the dependency-barrier probe.

    Camera source: node 1

    F1 origin:
        ServiceA: node 0
        F1 controller: colocated automatically at node 0

    F1 branches:
        branch 0 -> ServiceB: node 2
        branch 1 -> ServiceC: node 3
        branch 2 -> ServiceE: node 5

    F1 final output:
        ServiceD: node 4
    """

    def initial_allocation(self, sim, app_name):

        app = sim.apps[app_name]
        services = app.services

        deployment = {
            "ServiceA": 0,
            "ServiceB": 2,
            "ServiceC": 3,
            "ServiceD": 4,
            "ServiceE": 5,
        }

        for module, node_id in deployment.items():
            sim.deploy_module(
                app_name,
                module,
                services[module],
                [node_id],
            )


RANDOM_SEED = 1


# ---------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------

def create_application():

    a = Application(name="PraiseDependencyBarrierProbe")

    a.set_modules([
        {"Camera": {
            "Type": Application.TYPE_SOURCE
        }},
        {"ServiceA": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceB": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceC": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceD": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
        {"ServiceE": {
            "RAM": 10,
            "Type": Application.TYPE_MODULE
        }},
    ])

    # External request -> F1 origin.
    m_a = Message(
        "M.A",
        "Camera",
        "ServiceA",
        instructions=20 * 10**6,
        bytes=1000,
    )

    # F1 branch 0.
    m_b = Message(
        "M.B",
        "ServiceA",
        "ServiceB",
        instructions=30 * 10**6,
        bytes=1000,
    )

    # F1 branch 1.
    m_c = Message(
        "M.C",
        "ServiceA",
        "ServiceC",
        instructions=40 * 10**6,
        bytes=1000,
    )

    a.add_source_messages(m_a)

    # -------------------------------------------------
    # F1: Par + local branch dependencies
    #
    #   branch 0 -> ServiceB, depends_on=()
    #   branch 1 -> ServiceC, depends_on=()
    #   branch 2 -> ServiceE, depends_on=(0, 1)
    #
    # Branch IDs and dependencies are local to F1.
    # -------------------------------------------------

    # Root branch 0. This first declaration creates F1.
    a.add_service_module_praise(
        "ServiceA",
        m_a,
        m_b,
        fractional_selectivity,
        composition_id="F1",
        branch_id=0,
        depends_on=(),
        threshold=1.0,
    )

    # Root branch 1.
    a.add_service_module_praise(
        "ServiceA",
        m_a,
        m_c,
        fractional_selectivity,
        composition_id="F1",
        branch_id=1,
        depends_on=(),
        threshold=1.0,
    )

    # Branch 2 belongs to the same Par scope as branches 0 and 1.
    # Its branch specification is structurally identical.
    # The only difference is its activation dependency:
    # the F1 controller releases branch 2 only after observing
    # completion of sibling branches 0 and 1 for the same request.
    m_e = Message(
        "M.E",
        "ServiceA",
        "ServiceE",
        instructions=25 * 10**6,
        bytes=1000,
    )

    a.add_service_module_praise(
        "ServiceA",
        m_a,
        m_e,
        fractional_selectivity,
        composition_id="F1",
        branch_id=2,
        depends_on=(0, 1),
        threshold=1.0,
    )

    # -------------------------------------------------
    # Single F1 composition output.
    #
    # It is emitted only after all F1 branches
    # {0, 1, 2} have completed.
    # -------------------------------------------------

    m_out = Message(
        "M.OUT",
        a.compositions["F1"]["controller_name"],
        "ServiceD",
        instructions=0,
        bytes=1000,
    )

    a.set_composition_output_praise(
        composition_id="F1",
        message_out=m_out,
    )

    # Static declaration audit.
    composition = a.compositions["F1"]

    print(
        "COMPOSITION_PROBE",
        "composition=", "F1",
        "origin_module=", composition["origin_module"],
        "message_in=", composition["message_in"].name,
        "controller_name=", composition["controller_name"],
        "branches=", sorted(composition["branches"].keys()),
        "message_out=", composition["message_out"].name,
    )

    for branch_id, registration in composition["branches"].items():
        print(
            "BRANCH_PROBE",
            "branch=", branch_id,
            "depends_on=", registration["depends_on"],
            "message_out=", registration["message_out"].name,
        )

    # Terminal services.
    #
    # ServiceB and ServiceC complete root branches 0 and 1.
    # ServiceE completes dependent branch 2.
    # ServiceD consumes the single F1 composition output.
    a.add_service_module("ServiceB", m_b)
    a.add_service_module("ServiceC", m_c)
    a.add_service_module("ServiceE", m_e)
    a.add_service_module("ServiceD", m_out)

    return a


# ---------------------------------------------------------------------
# Physical topology
# ---------------------------------------------------------------------

def create_json_topology():

    topology_json = {
        "entity": [],
        "link": [],
    }

    service_a_dev = {
        "id": 0,
        "model": "service-a-device",
        "mytag": "service-a",
        "IPT": 300 * 10**5,
        "RAM": 40000,
        "COST": 3,
        "WATT": 20.0,
    }

    sensor_dev = {
        "id": 1,
        "model": "sensor-device",
        "IPT": 100 * 10**6,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0,
    }

    service_b_dev = {
        "id": 2,
        "model": "service-b-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0,
    }

    service_c_dev = {
        "id": 3,
        "model": "service-c-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0,
    }

    service_d_dev = {
        "id": 4,
        "model": "service-d-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0,
    }

    service_e_dev = {
        "id": 5,
        "model": "service-e-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0,
    }

    # Camera -> ServiceA.
    link_source_a = {
        "s": 1,
        "d": 0,
        "BW": 10,
        "PR": 1,
    }

    # Root branch 0: ServiceA -> ServiceB.
    #
    # Deliberately faster than branch 1 so that the controller observes
    # one prerequisite before the other.
    link_a_b = {
        "s": 0,
        "d": 2,
        "BW": 10,
        "PR": 2,
    }

    # Root branch 1: ServiceA -> ServiceC.
    link_a_c = {
        "s": 0,
        "d": 3,
        "BW": 10,
        "PR": 6,
    }

    # F1 final output: controller/node0 -> ServiceD.
    link_join_d = {
        "s": 0,
        "d": 4,
        "BW": 10,
        "PR": 2,
    }

    # Dependent branch 2: controller/node0 -> ServiceE.
    link_join_e = {
        "s": 0,
        "d": 5,
        "BW": 10,
        "PR": 3,
    }

    topology_json["entity"].extend([
        service_a_dev,
        sensor_dev,
        service_b_dev,
        service_c_dev,
        service_d_dev,
        service_e_dev,
    ])

    topology_json["link"].extend([
        link_source_a,
        link_a_b,
        link_a_c,
        link_join_d,
        link_join_e,
    ])

    return topology_json


# ---------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------

def main(simulated_time):

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    folder_results = Path("results/")
    folder_results.mkdir(parents=True, exist_ok=True)
    folder_results = str(folder_results) + "/"

    # Topology.
    t = Topology()
    t_json = create_json_topology()
    t.load(t_json)
    nx.write_gexf(
        t.G,
        folder_results + "graph_main1",
    )

    # Application.
    app = create_application()

    # Fixed placement.
    placement = BarrierPlacement("barrier-placement")

    # Population.
    pop = Statical("Statical")

    dDistribution = deterministic_distribution(
        name="Deterministic",
        time=10,
    )

    pop.set_src_control({
        "model": "sensor-device",
        "number": 1,
        "message": app.get_message("M.A"),
        "distribution": dDistribution,
    })

    # Routing.
    selectorPath = MinimunPath()

    # Simulation engine.
    stop_time = simulated_time
    sim = Sim(
        t,
        default_results_path=folder_results + "sim_trace",
    )

    # Retain the same management-network structure used by the probes.
    # With the current 100-time-unit test horizon, the 500-unit agent
    # wake-up does not interfere with the barrier behavior.
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
                    "class": "ServiceNodeUtilization",
                },
                "agent_node_utilization": {
                    "module": "yafs.management_network",
                    "class": "AgentNodeUtilization",
                },
                "node_average_waiting_time": {
                    "module": "yafs.management_network",
                    "class": "NodeAverageWaitingTime",
                },
                "node_request_waiting_in": {
                    "module": "yafs.management_network",
                    "class": "NodeRequestsWaitingIn",
                },
                "node_requests_out": {
                    "module": "yafs.management_network",
                    "class": "NodeRequestsOut",
                },
                "net_buffer_size": {
                    "module": "yafs.management_network",
                    "class": "NetBufferSize",
                },
                "node_nominalwatt": {
                    "module": "yafs.management_network",
                    "class": "NodeNominalWatt",
                },
                "linear_cost_buyya": {
                    "module": "yafs.management_network",
                    "class": "LinearCostBuyya",
                    "params": {
                        "cost_alpha": 1.0,
                    },
                },
            },
        }
    ]

    management_network = ManagementAgentNetwork(
        "management_network",
        agent_configs_json,
        sim,
    )

    sim.deploy_app_agentic(
        app,
        placement,
        pop,
        selectorPath,
        management_network,
    )

    # Run.
    sim.run(
        stop_time,
        show_progress_monitor=False,
    )

    sim.print_debug_assignaments()

    # Statistics.
    mypath = folder_results + "sim_trace"
    m = Stats(defaultPath=mypath)

    print("\t- Network saturation -")
    print(
        "\t\tAverage waiting messages : %i"
        % m.average_messages_not_transmitted()
    )
    print(
        "\t\tPeak of waiting messages : %i"
        % m.peak_messages_not_transmitted()
    )
    print(
        "\t\tTOTAL messages not transmitted: %i"
        % m.messages_not_transmitted()
    )

    print("\n\t- Stats of each service deployed -")
    print(m.get_df_modules())
    print(
        m.get_df_service_utilization(
            "ServiceA",
            simulated_time,
        )
    )

    print("\n\t- Stats of each DEVICE -")

    app_name = "PraiseDependencyBarrierProbe"
    app = sim.apps[app_name]
    services = app.services

    print(
        "\n\t- Stats of each module deployed "
        "(except sources) -"
    )
    print(m.get_df_modules())

    print(
        "\n\t- Stats of each management agent deployed -"
    )
    print(m.get_df_agent_modules())


if __name__ == "__main__":
    import logging.config
    import os

    logging.config.fileConfig(
        os.getcwd() + "/logging.ini"
    )

    start_time = time.time()

    main(simulated_time=100)

    print(
        "\n--- %s seconds ---"
        % (time.time() - start_time)
    )
