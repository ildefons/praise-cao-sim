from pathlib import Path

from run_phase5_i1_v2 import (
    I1_CARD_CONTRACT,
    PHASE1_CONFIG,
    _assert_phase1_matches_phase5,
    _card_contract,
)
from phase5_runtime_v2 import (
    inclusive_seed_range,
    load_phase5_contracts,
    provider_world,
    read_json,
)


HERE = Path(__file__).resolve().parent


def test_phase5_i1_reuses_exact_frozen_acquisition_mechanics():
    contracts = load_phase5_contracts(HERE)
    phase1 = read_json(PHASE1_CONFIG)
    _assert_phase1_matches_phase5(phase1, contracts)


def test_phase5_i1_card_contract_is_frozen_rho_conditioned_interface():
    contract = _card_contract()
    assert contract["status"] == "PHASE2_I1_RHO_CONDITIONED_CONTRACT_V1"
    assert contract["region_rho"]["values"] == contract["query_rho"]["values"]
    assert contract["evidence_partition"]["region_construction"]["n_trajectories"] == 100
    assert contract["evidence_partition"]["sigma_estimation"]["n_trajectories"] == 100
    assert I1_CARD_CONTRACT.is_file()


def test_phase5_i1_world_seed_banks_are_exact_and_disjoint():
    contracts = load_phase5_contracts(HERE)
    expected = {
        "P1": ((50000, 50099), (50100, 50199)),
        "P2": ((50200, 50299), (50300, 50399)),
        "P3": ((50400, 50499), (50500, 50599)),
        "P4": ((50600, 50699), (50700, 50799)),
    }
    for world_id, (region_bounds, sigma_bounds) in expected.items():
        region = inclusive_seed_range(
            contracts.seeds["public_I1"][world_id]["region"]
        )
        sigma = inclusive_seed_range(
            contracts.seeds["public_I1"][world_id]["sigma"]
        )
        assert (region[0], region[-1]) == region_bounds
        assert (sigma[0], sigma[-1]) == sigma_bounds
        assert len(region) == 100
        assert len(sigma) == 100
        assert not set(region).intersection(sigma)


def test_phase5_i1_world_parameters_match_v2_contract():
    contracts = load_phase5_contracts(HERE)
    expected = {
        "P1": (330_000_000, 0.00, (330_000_000, 330_000_000, 330_000_000)),
        "P2": (330_000_000, 0.15, (280_500_000, 330_000_000, 379_500_000)),
        "P3": (360_000_000, 0.00, (360_000_000, 360_000_000, 360_000_000)),
        "P4": (360_000_000, 0.10, (324_000_000, 360_000_000, 396_000_000)),
    }
    for world_id, (D, delta, means) in expected.items():
        world = provider_world(contracts, world_id)
        assert int(world["D_instructions"]) == D
        assert float(world["delta"]) == delta
        actual = tuple(
            int(world["provider_means"][provider])
            for provider in ("ProviderA", "ProviderB", "ProviderC")
        )
        assert actual == means
