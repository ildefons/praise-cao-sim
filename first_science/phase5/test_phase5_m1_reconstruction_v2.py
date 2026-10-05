from pathlib import Path

from phase5_runtime_v2 import load_phase5_contracts
from run_phase5_m1_reconstruction_v2 import (
    _expanded_contract,
    _phase5_contract,
)


HERE=Path(__file__).resolve().parent


def test_phase5_m1_contract_uses_registered_reconstruction_banks():
    contracts=load_phase5_contracts(HERE)
    cfg=_phase5_contract()
    opt=cfg["joint_full_surface_lift"]["optimization"]
    assert opt["calibration_common_random_numbers"]["trajectory_seed_start"]==52000
    assert opt["calibration_common_random_numbers"]["n_trajectories"]==25
    assert opt["shortlist_confirmation"]["trajectory_seed_start"]==52100
    assert opt["shortlist_confirmation"]["n_trajectories"]==100
    assert opt["independent_replay"]["trajectory_seed_start"]==52200
    assert opt["independent_replay"]["n_trajectories"]==100
    assert opt["sampler_seed"]==314159
    assert opt["n_trials"]==100
    assert opt["n_startup_trials"]==20
    assert opt["boundary_fraction"]==0.02


def test_phase5_m1_one_decade_edge_expansion_only_implicated_edges():
    cfg=_phase5_contract()
    base=cfg["joint_full_surface_lift"]["optimization"]["search_space"]
    expanded=_expanded_contract(
        cfg,
        {"mean_service_time":"lower","cost_rate":"upper"},
    )
    got=expanded["joint_full_surface_lift"]["optimization"]["search_space"]
    assert got["mu_over_workload_period_bounds"][0]==base["mu_over_workload_period_bounds"][0]/10
    assert got["mu_over_workload_period_bounds"][1]==base["mu_over_workload_period_bounds"][1]
    assert got["cost_rate_reference_multiplier_bounds"][0]==base["cost_rate_reference_multiplier_bounds"][0]
    assert got["cost_rate_reference_multiplier_bounds"][1]==base["cost_rate_reference_multiplier_bounds"][1]*10
    assert got["cv_bounds"]==base["cv_bounds"]
