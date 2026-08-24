"""
    @author: Ildefons Magrans de Abril
"""

import random
import networkx as nx
import argparse
from pathlib import Path
import time
import numpy as np

from yafs.core import Sim
from yafs.application import Application,Message,LinearQoS

from yafs.population import *
from yafs.topology import Topology

from yafs.stats import Stats
from yafs.distribution import deterministic_distribution
from yafs.application import fractional_selectivity

from yafs.placement import Placement
from yafs.selection import Selection

# ILDE: added as part of the new agent management network 
from yafs.management_network import ManagementAgent, ManagementAgentNetwork, DiscreteNodeIPTInterventions
import numpy as np

#ILDE: PRAISE related example
from yafs.distribution import gamma_distribution

# Custom agent classes
class CloudAgent(ManagementAgent):
    def __custom_init__(self):
        self.state_id = 0


    def agent_behavior(self, collected_metrics):
        """Retrieve and log incoming messages to cloud (node_id)."""

        # filtered = [obj for obj in collected_metrics if obj["metric"] == "ServiceNodeUtilization"]
        # print("COLECTED_METRICS:", collected_metrics)
        # print("ALL ServiceNodeUtilization in Cloud Agent:",filtered)

        #print("CloudAgent.get_management_action()")
        #myactions = self.actions['msg_instructions_pctl']

        myactions2 = self.actions['discrete_node_ipt']
        
        #myactions2(action_id=2, node_id=self.node_id)

        #get the des_id of the service running in the same node of the agent
        # def get_key_by_value(d, x):
        #     for k, v in d.items():
        #         if v == x:
        #             return k
        #     raise ValueError(f"Value {x} not found in dictionary")
        # service_des_id = get_key_by_value(self.sim.alloc_DES, self.node_id)

        if self.sim.env.now >= 2000 and self.state_id == 0:
            self.state_id = 1
            myactions2(action_id=1, node_id=self.node_id)
        elif self.sim.env.now >= 4000 and self.state_id == 1:
            self.state_id = 2
            myactions2(action_id=0, node_id=self.node_id)
        elif self.state_id == 2:
            sublist_metrics = [item for item in collected_metrics if item['metric'] == 'NodeAverageWaitingTime' and item['node_id'] == self.node_id]
            if sublist_metrics[0]['value'] > 550:
                myactions2(action_id=1, node_id=self.node_id)  #We move to high performance
            if sublist_metrics[0]['value'] < 200:
                myactions2(action_id=0, node_id=self.node_id)  #We move to low performance          


        #print(collected_metrics)

        #apply action to service with id = service_des_id
        #myactions(self.action_id, service_des_id = service_des_id)
        #rotate action for next time
        # self.action_id = self.action_id + 1
        # if self.action_id >= len(myactions.pctls):
        #     self.action_id = 0


class SensorAgent(ManagementAgent):
    def agent_behavior(self, collected_metrics):
        """Sensor monitors metrics (no actions for now)."""

        #print("SensorAgent.get_management_action()")

        return []  # Extensible for future logic

class ActuatorAgent(ManagementAgent):
    def agent_behavior(self, collected_metrics):
        """Actuator monitors metrics (no actions for now)."""

        #print("ActuatorAgent.get_management_action()")

        return []  # Extensible for future logic

class MinimunPath(Selection):

    def get_path(self, sim, app_name, message, topology_src, alloc_DES, alloc_module, traffic,from_des):

        """
        Computes the minimun path among the source elemento of the topology and the localizations of the module

        Return the path and the identifier of the module deployed in the last element of that path
        """
        node_src = topology_src
        DES_dst = alloc_module[app_name][message.dst]

        # print(("GET PATH"))
        # print(("\tNode _ src (id_topology): %i" %node_src))
        # print(("\tRequest service: %s " %message.dst))
        # print(("\tProcess serving that service: %s " %DES_dst))

        #ILDE PRAISE DEBUGGING
        print(
            "PATH_PROBE",
            "time=", sim.env.now,
            "message=", message.name,
            "id=", message.id,
            "composition_path=", message.composition_path
        )

        bestPath = []
        bestDES = []

        for des in DES_dst: ## In this case, there are only one deployment
            dst_node = alloc_DES[des]
            #print(("\t\t Looking the path to id_node: %i" %dst_node))

            path = list(nx.shortest_path(sim.topology.G, source=node_src, target=dst_node))

            bestPath = [path]
            bestDES = [des]

        return bestPath, bestDES



class MinPath_RoundRobin(Selection):

    def __init__(self):
        self.rr = {} #for a each type of service, we have a mod-counter

    def get_path(self, sim, app_name, message, topology_src, alloc_DES, alloc_module, traffic,from_des):
        """
        Computes the minimun path among the source elemento of the topology and the localizations of the module

        Return the path and the identifier of the module deployed in the last element of that path
        """
        node_src = topology_src
        DES_dst = alloc_module[app_name][message.dst] #returns an array with all DES process serving


        if message.dst not in self.rr.keys():
            self.rr[message.dst] = 0


        print(("GET PATH"))
        print(("\tNode _ src (id_topology): %i" %node_src))
        print(("\tRequest service: %s " %(message.dst)))
        print(("\tProcess serving that service: %s (pos ID: %i)" %(DES_dst,self.rr[message.dst])))

        bestPath = []
        bestDES = []

        for ix,des in enumerate(DES_dst):
            if message.name == "M.A":
                if self.rr[message.dst]==ix:
                    dst_node = alloc_DES[des]

                    path = list(nx.shortest_path(sim.topology.G, source=node_src, target=dst_node))

                    bestPath = [path]
                    bestDES = [des]

                    self.rr[message.dst] = (self.rr[message.dst]+ 1) % len(DES_dst)
                    break
            else: #message.name == "M.B"

                dst_node = alloc_DES[des]

                path = list(nx.shortest_path(sim.topology.G, source=node_src, target=dst_node))
                if message.broadcasting:
                    bestPath.append(path)
                    bestDES.append(des)
                else:
                    bestPath = [path]
                    bestDES = [des]

        return bestPath, bestDES


class ForkPlacement(Placement):
    """
    Fixed deployment for the fork probe.

    Camera source: node 1
    ServiceA:      node 0
    ServiceB:      node 2
    ServiceC:      node 3
    """

    def initial_allocation(self, sim, app_name):

        app = sim.apps[app_name]
        services = app.services

        deployment = {
            "ServiceA": 0,
            "ServiceB": 2,
            "ServiceC": 3,
            "ServiceD": 4,
        }

        for module, node_id in deployment.items():
            sim.deploy_module(
                app_name,
                module,
                services[module],
                [node_id]
            )


RANDOM_SEED = 1

def create_application():

    a = Application(name="PraiseCompositionProbe")

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
    ])

    # Camera -> ServiceA
    m_a = Message(
        "M.A",
        "Camera",
        "ServiceA",
        instructions=20 * 10**6,
        bytes=1000
    )

    # ServiceA -> ServiceB
    m_b = Message(
        "M.B",
        "ServiceA",
        "ServiceB",
        instructions=30 * 10**6,
        bytes=500_000
    )

    # ServiceA -> ServiceC
    m_c = Message(
        "M.C",
        "ServiceA",
        "ServiceC",
        instructions=40 * 10**6,
        bytes=500_000
    )

    a.add_source_messages(m_a)

    # -------------------------------------------------
    # FORK PROBE
    # Same module + same input + two different outputs
    # -------------------------------------------------

    a.add_service_module_praise(
        "ServiceA",
        m_a,
        m_b,
        fractional_selectivity,
        composition_id="F1",
        branch_id=0,
        depends_on=(),
        threshold=1.0
    )

    a.add_service_module_praise(
        "ServiceA",
        m_a,
        m_c,
        fractional_selectivity,
        composition_id="F1",
        branch_id=1,
        depends_on=(0,),
        threshold=1.0
    )

    m_d = Message(
        "M.D",
        a.compositions["F1"]["controller_name"],
        "ServiceD",
        instructions=0,
        bytes=1000
    )

    a.set_composition_output_praise(
        composition_id="F1",
        message_out=m_d
    )

    composition = a.compositions["F1"]

    print(
        "COMPOSITION_OUTPUT_PROBE",
        "composition=", "F1",
        "message_out=", composition["message_out"].name,
        "src=", composition["message_out"].src,
        "dst=", composition["message_out"].dst
    )

    print(
        "COMPOSITION_PROBE",
        "composition=", "F1",
        "origin_module=", composition["origin_module"],
        "message_in=", composition["message_in"].name,
        "controller_name=", composition["controller_name"],
        "branches=", sorted(composition["branches"].keys())
    )

    for branch_id, registration in composition["branches"].items():
        print(
            "BRANCH_PROBE",
            "branch=", branch_id,
            "depends_on=", registration["depends_on"],
            "message_out=", registration["message_out"].name
        )


    a.add_service_module("ServiceB", m_b)
    a.add_service_module("ServiceC", m_c)
    a.add_service_module("ServiceD", m_d)

    return a


def create_json_topology():

    topology_json = {}
    topology_json["entity"] = []
    topology_json["link"] = []

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

    service_b_dev = {
        "id": 2,
        "model": "service-b-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    service_c_dev = {
        "id": 3,
        "model": "service-c-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    service_d_dev = {
        "id": 4,
        "model": "service-d-device",
        "IPT": 100 * 10**7,
        "RAM": 4000,
        "COST": 3,
        "WATT": 40.0
    }

    # Camera -> ServiceA
    link_source_a = {
        "s": 1,
        "d": 0,
        "BW": 1,
        "PR": 1
    }

    # ServiceA -> ServiceB
    link_a_b = {
        "s": 0,
        "d": 2,
        "BW": 10,
        "PR": 5
    }

    # ServiceA -> ServiceC
    # Deliberately different network characteristics.
    link_a_c = {
        "s": 0,
        "d": 3,
        "BW": 5,
        "PR": 15
    }

    # PRAISE join controller / ServiceA node -> ServiceD
    link_join_d = {
        "s": 0,
        "d": 4,
        "BW": 10,
        "PR": 5
    }

    topology_json["entity"].extend([
        service_a_dev,
        sensor_dev,
        service_b_dev,
        service_c_dev,
        service_d_dev
    ])

    topology_json["link"].extend([
        link_source_a,
        link_a_b,
        link_a_c,
        link_join_d
    ])

    return topology_json



def main(simulated_time):

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    folder_results = Path("results/")
    folder_results.mkdir(parents=True, exist_ok=True)
    folder_results = str(folder_results)+"/"

    """
    TOPOLOGY from a json
    """
    t = Topology()
    t_json = create_json_topology()
    t.load(t_json)
    nx.write_gexf(t.G,folder_results+"graph_main1") # you can export the Graph in multiples format to view in tools like Gephi, and so on.

    """qos=LinearQoS(L=0.05,R=1.0))
    APPLICATION
    """
    app = create_application()

    """
    PLACEMENT algorithm
    """

    # ILDEBEGIN PRAISE
    #placement = CloudPlacement("onCloud") # it defines the deployed rules: module-device
    #placement.scaleService({"ServiceA": 1}) 

    placement = ForkPlacement("fork-placement")

    # ILDEEND

    #In their case, the use a statical assignment.management_network.N[0][0] = (["utilization", "latency", "instructions"], ["instructions"])  # Cloud: ServiceA
    #pop = Statical("Statical")
    #For each type of sink modules we set a deployment on some type of devices
    #A control sink consists on:
    #  args:
    #     model (str): identifies the device or devices where the sink is linked
    #     number (int): quantity of sinks linked in each device
    #     module (str): identifies the module from the app who r

    """
    POPULATION algorithm
    """
    #In ifogsim, during the creation of the application, the Sensors are assigned to the topology, in this case no. 
    # As mentioned, YAFS differentiates the adaptive sensors and their topological assignment.
    #In their case, the use a statical assignment.management_network.N[0][0] = (["utilization", "latency", "instructions"], ["instructions"])  # Cloud: ServiceA
    pop = Statical("Statical")
    #For each type of sink modules we set a deployment on some type of devices
    #A control sink consists on:
    #  args:
    #     model (str): identifies the device or devices where the sink is linked
    #     number (int): quantity of sinks linked in each device
    #     module (str): identifies the module from the app who receives the messages
    
    # ILDEBEGIN PRAISE
    # pop.set_sink_control({"model": "actuator-device",
    #                       "number":1,
    #                       "module": "Dashboard"}) # ILDE  app.get_sink_modules()})
    # ILDEEND

    #In addition, a source includes a distribution function:
    
    # ILDEBegin

    # dDistribution = deterministic_distribution(name="Deterministic",time=1)
    # pop.set_src_control({"model": "sensor-device", 
    #                      "number":1,
    #                      "message": app.get_message("M.A"), 
    #                      "distribution": dDistribution})
    
    dDistribution = deterministic_distribution(
    name="Deterministic",
    time=10
    )

    pop.set_src_control({
        "model": "sensor-device",
        "number": 1,
        "message": app.get_message("M.A"),
        "distribution": dDistribution
    })

    # ILDEEND

    """--
    SELECTOR algorithm
    """
    #Their "selector" is actually the shortest way, there is not type of orchestration algorithm.
    #This implementation is already created in selector.class,called: First_ShortestPath
    selectorPath = MinimunPath()

    """
    SIMULATION ENGINE
    """

    stop_time = simulated_time
    sim = Sim(t, default_results_path=folder_results+"sim_trace")

    agent_configs_json = [
                {
            "node_id": 3,
            "agent_type": ActuatorAgent,
            "sleep_time": 500,
            "instructions_per_wakeup": 10*10*10**6,
            "agent_ipt_percentage": 0.5,
            "observable_node_ids": [3,0],
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

    management_network = ManagementAgentNetwork("management_network", agent_configs_json, sim)

    sim.deploy_app_agentic(app, placement, pop, selectorPath, management_network)

    """
    RUNNING - last step
    """
    sim.run(stop_time, show_progress_monitor=False)  # To test deployments put test_initial_deploy a TRUE
    sim.print_debug_assignaments()

    #time_loops = [["M.A", "M.B"]]

    from yafs.stats import Stats
    mypath = folder_results + "sim_trace"
 

    m = Stats(defaultPath=mypath)
    #m.showResults2(simulated_time, time_loops=time_loops)
    
    print("\t- Network saturation -")
    print("\t\tAverage waiting messages : %i" % m.average_messages_not_transmitted())
    print("\t\tPeak of waiting messages : %i" % m.peak_messages_not_transmitted())
    print("\t\tTOTAL messages not transmitted: %i" % m.messages_not_transmitted())

    print("\n\t- Stats of each service deployed -")
    print(m.get_df_modules())
    print(m.get_df_service_utilization("ServiceA",simulated_time))
    # print(m.get_df_service_utilization("Camera",simulated_time))
    # print(m.get_df_service_utilization("Dashboard",simulated_time))

    print("\n\t- Stats of each DEVICE -")

    app_name = "PraiseCompositionProbe"
    app = sim.apps[app_name]
    services = app.services
    
    print("\n\t- Stats of each module deployed (except sources) -")
    print(m.get_df_modules())

    print("\n\t- Stats of each management agent deployed -")
    print(m.get_df_agent_modules())

    # for i in sim.management_network['management_network']['management_network'].agents.keys():
    #     agent_name = sim.management_network['management_network']['management_network'].agents[i].agent_name
    #     print("---------------------\n",agent_name)
    #     print(m.get_df_agent_utilization(agent_name,simulated_time))
    #     print(m.get_df_agent_sleeping_percentage(agent_name,simulated_time))
        
    #print(m.get_df_service_utilization("ServiceA",simulated_time))

    # s.draw_allocated_topology() # for debugging



if __name__ == '__main__':
    import logging.config
    import os

    logging.config.fileConfig(os.getcwd()+'/logging.ini')

    start_time = time.time()
    main(simulated_time=100)

    print("\n--- %s seconds ---" % (time.time() - start_time))
