from pathlib import Path

import pytest

from m0_analytic_composition import AdmissibilityBoundary

from phase5_runtime_v2 import (
    inclusive_seed_range,
    load_phase5_contracts,
)
from run_phase5_step0_v2 import (
    _compose_ast_boundary,
    _diagnostic_horizons,
    _regimes,
    _rho_values,
    _scale_grid,
)


HERE=Path(__file__).resolve().parent


@pytest.fixture
def contracts():
    return load_phase5_contracts(HERE)


def test_step0_frozen_design_constants(contracts):
    scales=_scale_grid(contracts.battery["step0"]["scale_grid"])
    assert len(scales)==151
    assert scales[0]==pytest.approx(0.5)
    assert scales[-1]==pytest.approx(2.0)
    assert _diagnostic_horizons(contracts)==[
        float(x) for x in range(60,241,5)
    ]
    assert _regimes(contracts)=={
        "Easy":(0.95,1.0,0.975),
        "Mid":(0.75,0.90,0.825),
        "Stress":(0.40,0.75,0.575),
    }
    assert len(_rho_values(contracts))==5


def test_step0_seed_banks_exact_and_disjoint(contracts):
    cal=inclusive_seed_range(contracts.seeds["step0"]["calibration_WB"])
    con=inclusive_seed_range(contracts.seeds["step0"]["confirmation_WB"])
    assert (cal[0],cal[-1],len(cal))==(51000,51199,200)
    assert (con[0],con[-1],len(con))==(51200,51399,200)
    assert not set(cal).intersection(con)


def _locals():
    return {
        "ProviderA":AdmissibilityBoundary(l_max=1.0,c_max=10.0,q_min=0.9),
        "ProviderB":AdmissibilityBoundary(l_max=2.0,c_max=20.0,q_min=0.8),
        "ProviderC":AdmissibilityBoundary(l_max=3.0,c_max=30.0,q_min=0.7),
    }


@pytest.mark.parametrize(
    "ast,expected_latency",
    [
        (
            {"op":"parallel_all","children":["ProviderA","ProviderB","ProviderC"]},
            3.2,
        ),
        (
            {"op":"sequence","children":["ProviderA","ProviderB","ProviderC"]},
            6.6,
        ),
        (
            {
                "op":"sequence",
                "children":[
                    "ProviderA",
                    {"op":"parallel_all","children":["ProviderB","ProviderC"]},
                ],
            },
            4.4,
        ),
        (
            {
                "op":"parallel_all",
                "children":[
                    "ProviderA",
                    {"op":"sequence","children":["ProviderB","ProviderC"]},
                ],
            },
            5.4,
        ),
    ],
)
def test_ast_forward_boundary_uses_native_branch_and_completion_overheads(
    ast,expected_latency
):
    # Each provider leaf receives 0.1 data-hop + 0.1 completion-control latency.
    b=_compose_ast_boundary(
        ast,_locals(),branch_data_delay=0.1,completion_control_delay=0.1
    )
    assert b.l_max==pytest.approx(expected_latency)
    # Both supported operators have additive execution cost.
    assert b.c_max==pytest.approx(60.0)
    assert b.q_min==pytest.approx(0.7)
