"""PRAISE I1-M0/M1 implementation Phase 0: white-box provider observation kernel.

Scientific scope:
  periodic source -> one native stochastic provider -> sink

Produces per-trajectory provider ledgers and a smoke-test survival curve.
No provider card, M0, M1, reference-regime search, or calibration is performed.

Expected AICon/YAFS baseline: ildefons/aicon @ 6eabfa7
Expected PRAISE-CAO baseline: ildefons/praise-cao-sim @ fbf722e
"""
from __future__ import annotations

import argparse
import json
import logging.config
import math
import os
import random
import shutil
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from yafs.application import Application, LinearQoS, Message, fractional_selectivity
from yafs.core import Sim
from yafs.distribution import deterministic_distribution, gamma_distribution
from yafs.placement import Placement
from yafs.management_network import ManagementAgentNetwork
from yafs.population import Statical
from yafs.selection import Selection
from yafs.stats import Stats
from yafs.topology import Topology

from survival import (
    AdmissibilityRegion,
    empirical_survival,
    summarize_first_violations,
    trajectory_first_violation,
    validate_ledger,
)

APP = "Phase0Whitebox"
SOURCE_MODULE = "Source"
PROVIDER_MODULE = "Provider"
SINK_MODULE = "Sink"
REQUEST_MSG = "M.REQUEST"
RESPONSE_MSG = "M.RESPONSE"
SOURCE_NODE = 1
PROVIDER_NODE = 0
SINK_NODE = 2


class MinimumPath(Selection):
    def get_path(self, sim, app_name, message, topology_src, alloc_DES, alloc_module, traffic, from_des):
        best_path, best_des = [], []
        for des in alloc_module[app_name][message.dst]:
            dst_node = alloc_DES[des]
            best_path = [list(nx.shortest_path(sim.topology.G, source=topology_src, target=dst_node))]
            best_des = [des]
            break
        return best_path, best_des


class FixedProviderPlacement(Placement):
    def __init__(self, name: str, x: float):
        super().__init__(name)
        self.x = float(x)
        self.provider_des = None

    def initial_allocation(self, sim, app_name):
        services = sim.apps[app_name].services
        des_ids = sim.deploy_module(app_name, PROVIDER_MODULE, services[PROVIDER_MODULE], [PROVIDER_NODE])
        if len(des_ids) != 1:
            raise RuntimeError(f"expected one provider DES, got {des_ids}")
        self.provider_des = des_ids[0]
        sim.des_pct_instructions[self.provider_des] = self.x


def make_application(cfg: dict, seed: int) -> Application:
    app = Application(name=APP)
    app.set_modules([
        {SOURCE_MODULE: {"Type": Application.TYPE_SOURCE}},
        {PROVIDER_MODULE: {"RAM": 10, "Type": Application.TYPE_MODULE}},
        {SINK_MODULE: {"Type": Application.TYPE_SINK}},
    ])

    demand = gamma_distribution(
        mean=float(cfg["instruction_mean"]),
        cv=float(cfg["instruction_cv"]),
        seed=int(seed),
        name=f"phase0_demand_seed_{seed}",
    )
    request = Message(
        REQUEST_MSG,
        SOURCE_MODULE,
        PROVIDER_MODULE,
        instructions=demand,
        bytes=int(cfg["request_bytes"]),
        qos=LinearQoS(L=0.0, R=1.0),  # Q=x exactly
    )
    response = Message(
        RESPONSE_MSG,
        PROVIDER_MODULE,
        SINK_MODULE,
        instructions=0,
        bytes=int(cfg["response_bytes"]),
    )
    app.add_source_messages(request)
    app.add_service_module(PROVIDER_MODULE, request, response, fractional_selectivity, threshold=1.0)
    return app


def make_topology(cfg: dict, *, network_pr: float | None = None) -> Topology:
    pr = float(cfg["network_pr"] if network_pr is None else network_pr)
    topo_json = {
        "entity": [
            {"id": PROVIDER_NODE, "model": "provider", "mytag": "provider",
             "IPT": float(cfg["provider_ipt"]), "RAM": 40000,
             "COST": float(cfg["provider_cost_rate"]), "WATT": 20.0},
            {"id": SOURCE_NODE, "model": "source", "mytag": "source",
             "IPT": float(cfg["source_ipt"]), "RAM": 4000,
             "COST": 0.0, "WATT": 0.0},
            {"id": SINK_NODE, "model": "sink", "mytag": "sink",
             "IPT": float(cfg["sink_ipt"]), "RAM": 4000,
             "COST": 0.0, "WATT": 0.0},
        ],
        "link": [
            {"s": SOURCE_NODE, "d": PROVIDER_NODE,
             "BW": float(cfg["network_bw_mbps"]), "PR": pr},
            {"s": PROVIDER_NODE, "d": SINK_NODE,
             "BW": float(cfg["network_bw_mbps"]), "PR": pr},
        ],
    }
    t = Topology()
    t.load(topo_json)
    return t


def _safe_float(v):
    if v is None or pd.isna(v):
        return None
    return float(v)


def build_provider_ledger(sim: Sim, placement: FixedProviderPlacement, trace_base: str, cfg: dict) -> pd.DataFrame:
    stop_time = float(cfg["stop_time"])
    provider_des = placement.provider_des
    if provider_des is None:
        raise RuntimeError("provider DES was not recorded by placement")

    stats = Stats(defaultPath=trace_base)
    df = stats.df.copy()
    if not df.empty:
        stats.compute_times_df()
        df = stats.df.copy()

    rows = []
    provider_rows = df[df["module"] == PROVIDER_MODULE].copy() if not df.empty else pd.DataFrame()
    cost_rate = float(sim.topology.get_info()[PROVIDER_NODE]["COST"])
    x = float(cfg["x"])
    provider_ipt = float(cfg["provider_ipt"])

    for _, r in provider_rows.iterrows():
        arrival = float(r["time_reception"])
        start = float(r["time_in"])
        completion = float(r["time_out"])
        # Use the native service duration recorded directly by YAFS, rather
        # than Stats.time_service (= time_out - time_in).  The latter can pick
        # up tiny floating-point cancellation differences when absolute event
        # timestamps are shifted (e.g. by changing only network propagation).
        service = float(r["service"])
        wait = float(r["time_in"] - r["time_reception"])
        local_latency = wait + service
        network_latency = float(r["time_reception"] - r["time_emit"])
        q = float(r["qos"])
        status = "completed" if completion <= stop_time + 1e-12 else "in_service"

        if x > 0:
            nominal_float = service * provider_ipt / x
            nominal_reconstructed = int(round(nominal_float))
            if abs(nominal_float - nominal_reconstructed) > 1e-4:
                raise AssertionError(
                    "native service duration does not reconstruct an effectively "
                    f"integer nominal instruction count: {nominal_float}"
                )
        else:
            nominal_reconstructed = math.nan
        rows.append({
            "request_id": int(r["id"]),
            "emission": float(r["time_emit"]),
            "arrival": arrival,
            "service_start": start,
            "completion": completion,
            "completed_by_stop": status == "completed",
            "status": status,
            "service": service,
            "wait": wait,
            "L": local_latency,
            "cost_rate": cost_rate,
            "C": cost_rate * service,
            "x": x,
            "Q": q,
            "network_latency": network_latency,
            "nominal_instructions_reconstructed": nominal_reconstructed,
            "stop_time": stop_time,
        })

    # Requests that reached the provider but are still waiting at stop have no
    # COMP_M metric row because YAFS records that row when service starts.
    pipe_key = f"{APP}{PROVIDER_MODULE}{provider_des}"
    queued_items = list(sim.consumer_pipes[pipe_key].items)
    existing_ids = {r["request_id"] for r in rows}
    for msg in queued_items:
        if int(msg.id) in existing_ids:
            raise RuntimeError(f"queued request {msg.id} already has a provider metric row")
        rows.append({
            "request_id": int(msg.id),
            "emission": float(msg.timestamp),
            "arrival": float(msg.timestamp_rec),
            "service_start": None,
            "completion": None,
            "completed_by_stop": False,
            "status": "queued",
            "service": None,
            "wait": None,
            "L": None,
            "cost_rate": cost_rate,
            "C": None,
            "x": x,
            "Q": x,
            "network_latency": float(msg.timestamp_rec - msg.timestamp),
            "nominal_instructions_reconstructed": None,
            "stop_time": stop_time,
        })

    ledger = pd.DataFrame(rows).sort_values(["arrival", "request_id"]).reset_index(drop=True)
    validate_ledger(ledger, stop_time=stop_time)
    return ledger


def run_trajectory(cfg: dict, seed: int, output_dir: Path, *, network_pr: float | None = None) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)

    output_dir.mkdir(parents=True, exist_ok=True)
    trace_base = str(output_dir / "sim_trace")
    topology = make_topology(cfg, network_pr=network_pr)
    app = make_application(cfg, seed)
    placement = FixedProviderPlacement("phase0_fixed_provider", x=float(cfg["x"]))

    pop = Statical("phase0_periodic_population")
    pop.set_sink_control({"model": "sink", "number": 1, "module": SINK_MODULE})
    pop.set_src_control({
        "model": "source",
        "number": 1,
        "message": app.get_message(REQUEST_MSG),
        "distribution": deterministic_distribution(
            name=f"period_{cfg['workload_period']}",
            time=float(cfg["workload_period"]),
        ),
    })

    sim = Sim(topology, default_results_path=trace_base)
    # Current AICon core has a legacy sink-path lookup that expects the
    # management_network registry to exist.  Use an EMPTY network solely as a
    # compatibility scaffold: it contains no agents, actions, monitoring, or
    # interventions, so Phase 0 remains physically non-adaptive.
    empty_management = ManagementAgentNetwork("management_network", [], sim)
    sim.deploy_app_agentic(app, placement, pop, MinimumPath(), empty_management)
    sim.run(float(cfg["stop_time"]), show_progress_monitor=False)

    ledger = build_provider_ledger(sim, placement, trace_base, cfg)
    ledger.insert(0, "seed", int(seed))
    ledger.to_csv(output_dir / "provider_ledger.csv", index=False)
    return ledger


def _comparison_frame(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["request_id", "status", "service", "wait", "L", "C", "Q", "nominal_instructions_reconstructed"]
    return df[cols].reset_index(drop=True)


def run_native_self_checks(cfg: dict, root: Path) -> None:
    """Fast native checks before the Monte-Carlo smoke run."""
    seed = int(cfg["seed_base"])

    # Same-seed reproducibility.
    a = run_trajectory(cfg, seed, root / "selfcheck_repro_a")
    b = run_trajectory(cfg, seed, root / "selfcheck_repro_b")
    pd.testing.assert_frame_equal(_comparison_frame(a), _comparison_frame(b), check_exact=True)
    print("PHASE0_REPRODUCIBILITY_PASS")

    # Local provider L excludes network latency.  Change only link propagation.
    net_cfg = dict(cfg)
    changed_pr = float(cfg["network_pr"]) + 0.137
    c = run_trajectory(net_cfg, seed, root / "selfcheck_network", network_pr=changed_pr)
    # A larger propagation delay can move the final arrivals across stop_time,
    # so compare only request IDs observed in both trajectories.  Constant
    # propagation shifts absolute arrivals but must not alter local provider
    # wait/service/L/C/Q for the common requests.
    common_ids = sorted(set(a["request_id"]).intersection(c["request_id"]))
    if len(common_ids) < 5:
        raise AssertionError("too few common requests for network firewall check")
    a_common = _comparison_frame(
        a[a["request_id"].isin(common_ids)].sort_values("request_id")
    ).reset_index(drop=True)
    c_common = _comparison_frame(
        c[c["request_id"].isin(common_ids)].sort_values("request_id")
    ).reset_index(drop=True)

    # Discrete/native physical quantities must be exactly unchanged.  Only
    # wait and L are derived from subtraction of shifted absolute timestamps,
    # so they are allowed a tiny machine-precision tolerance.
    exact_cols = [
        "request_id", "status", "service", "C", "Q",
        "nominal_instructions_reconstructed",
    ]
    pd.testing.assert_frame_equal(
        a_common[exact_cols], c_common[exact_cols], check_exact=True
    )
    pd.testing.assert_frame_equal(
        a_common[["wait", "L"]],
        c_common[["wait", "L"]],
        check_exact=False,
        rtol=0.0,
        atol=1e-12,
    )
    an = a[a["request_id"].isin(common_ids)]["network_latency"].to_numpy()
    cn = c[c["request_id"].isin(common_ids)]["network_latency"].to_numpy()
    if np.allclose(an, cn):
        raise AssertionError("network firewall check did not actually change network latency")
    print(f"PHASE0_NETWORK_FIREWALL_PASS n_common={len(common_ids)}")

    # Force queueing and ensure queued arrivals are preserved at stop.
    overload = dict(cfg)
    overload["workload_period"] = min(float(cfg["workload_period"]), 0.001)
    overload["stop_time"] = 0.08
    q = run_trajectory(overload, seed + 17, root / "selfcheck_overload")
    n_queued = int((q["status"] == "queued").sum())
    if n_queued == 0:
        raise AssertionError("overload self-check produced no queued requests at stop")
    print(f"PHASE0_QUEUE_CAPTURE_PASS n_queued={n_queued}")


def run_experiment(cfg: dict, root: Path, *, self_check: bool) -> None:
    if self_check:
        run_native_self_checks(cfg, root)

    region = AdmissibilityRegion(**cfg["A_test"])
    first_violation_times = []
    ledgers = []
    for j in range(int(cfg["n_trajectories"])):
        seed = int(cfg["seed_base"]) + j
        ledger = run_trajectory(cfg, seed, root / f"trajectory_{j:04d}")
        tviol = trajectory_first_violation(
            ledger.drop(columns=["seed"]),
            region,
            stop_time=float(cfg["stop_time"]),
        )
        first_violation_times.append(tviol)
        tagged = ledger.copy()
        tagged["trajectory"] = j
        tagged["first_violation"] = tviol
        ledgers.append(tagged)

    all_ledger = pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame()
    all_ledger.to_csv(root / "all_provider_ledgers.csv", index=False)

    survival = empirical_survival(
        first_violation_times,
        cfg["horizons"],
        stop_time=float(cfg["stop_time"]),
    )
    survival.to_csv(root / "survival_test.csv", index=False)
    summary = summarize_first_violations(first_violation_times, float(cfg["stop_time"]))
    with open(root / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("PHASE0_NATIVE_SMOKE_PASS")
    print(json.dumps(summary, indent=2))
    print(survival.to_string(index=False))


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not (0.0 < float(cfg["x"]) <= 1.0):
        raise ValueError("x must lie in (0,1]")
    if float(cfg["instruction_mean"]) <= 0 or float(cfg["instruction_cv"]) <= 0:
        raise ValueError("instruction_mean and instruction_cv must be positive")
    if max(map(float, cfg["horizons"])) > float(cfg["stop_time"]):
        raise ValueError("all horizons must be <= stop_time")
    return cfg


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=here / "config_phase0.json")
    parser.add_argument("--output", type=Path, default=here / "results")
    parser.add_argument("--n-trajectories", type=int, default=None)
    parser.add_argument("--stop-time", type=float, default=None)
    parser.add_argument("--skip-self-check", action="store_true")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    logging.config.fileConfig(here / "logging.ini")
    cfg = load_config(args.config)
    if args.n_trajectories is not None:
        cfg["n_trajectories"] = int(args.n_trajectories)
    if args.stop_time is not None:
        cfg["stop_time"] = float(args.stop_time)
        cfg["horizons"] = [h for h in cfg["horizons"] if float(h) <= cfg["stop_time"]]
        if not cfg["horizons"] or cfg["horizons"][-1] < cfg["stop_time"]:
            cfg["horizons"].append(cfg["stop_time"])

    root = args.output.resolve()
    if args.clean and root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "effective_config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    run_experiment(cfg, root, self_check=not args.skip_self_check)


if __name__ == "__main__":
    main()
