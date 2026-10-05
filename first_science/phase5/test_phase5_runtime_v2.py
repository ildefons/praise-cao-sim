from pathlib import Path

import pytest

from phase5_graph_ast_v2 import (
    assert_frozen_graph_compilation,
    compile_graph_ast,
)
from phase5_runtime_v2 import (
    assert_scientific_seed_banks_disjoint,
    assert_v2_final_whitebox_contract,
    canonical_graph_ids,
    canonical_provider_world_ids,
    graph_record,
    load_phase5_contracts,
    physical_cell_id,
)


def test_v2_contracts_load_and_seed_banks_are_disjoint():
    contracts = load_phase5_contracts(Path(__file__).resolve().parent)
    assert canonical_provider_world_ids(contracts) == ("P1", "P2", "P3", "P4")
    assert canonical_graph_ids(contracts) == (
        "G_PAR",
        "G_SEQ",
        "G_SEQPAR",
        "G_PARSEQ",
    )
    assert_scientific_seed_banks_disjoint(contracts)
    assert_v2_final_whitebox_contract(contracts)


@pytest.mark.parametrize(
    "graph_id, expected",
    [
        (
            "G_PAR",
            {
                "ProviderA": (),
                "ProviderB": (),
                "ProviderC": (),
            },
        ),
        (
            "G_SEQ",
            {
                "ProviderA": (),
                "ProviderB": ("ProviderA",),
                "ProviderC": ("ProviderB",),
            },
        ),
        (
            "G_SEQPAR",
            {
                "ProviderA": (),
                "ProviderB": ("ProviderA",),
                "ProviderC": ("ProviderA",),
            },
        ),
        (
            "G_PARSEQ",
            {
                "ProviderA": (),
                "ProviderB": (),
                "ProviderC": ("ProviderB",),
            },
        ),
    ],
)
def test_frozen_graph_asts_compile_to_expected_dependencies(graph_id, expected):
    contracts = load_phase5_contracts(Path(__file__).resolve().parent)
    record = graph_record(contracts, graph_id)
    plan = assert_frozen_graph_compilation(graph_id, record["ast"])
    assert dict(plan.dependencies) == expected


def test_ast_rejects_duplicate_provider_leaf():
    with pytest.raises(ValueError):
        compile_graph_ast(
            {
                "op": "parallel_all",
                "children": [
                    "ProviderA",
                    "ProviderA",
                    "ProviderC",
                ],
            }
        )


def test_all_16_physical_cell_ids_are_unique():
    contracts = load_phase5_contracts(Path(__file__).resolve().parent)
    cells = {
        physical_cell_id(p, g)
        for p in canonical_provider_world_ids(contracts)
        for g in canonical_graph_ids(contracts)
    }
    assert len(cells) == 16
