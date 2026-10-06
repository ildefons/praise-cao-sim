from __future__ import annotations

from pathlib import Path

import run_phase5_provider_reconstruction_v3 as runner
from phase5_runtime_v2 import read_json


def test_v3_scientific_contract_cardinalities():
    cfg=read_json(runner.CFG)
    assert cfg["status"]==runner.EXPECTED_CFG
    rec=cfg["candidate_reconstruction"]
    assert int(rec["candidate_count_per_provider"])==7
    assert int(rec["independent_fit_count"])==7
    assert int(rec["trials_per_fit"])==25
    assert int(rec["startup_trials_per_fit"])==5
    assert len(rec["fit_sampler_seeds"])==7
    assert int(cfg["methods"]["M1"]["members_per_provider"])==1
    assert int(cfg["methods"]["M2"]["members_per_provider"])==3
    assert int(cfg["methods"]["M2"]["joint_models_per_world"])==27
    assert int(cfg["methods"]["M3"]["members_per_provider"])==7
    assert int(cfg["methods"]["M3"]["joint_support_size"])==343


def test_v3_scientific_seed_banks_are_disjoint():
    seeds=read_json(runner.SEEDS)
    assert seeds["status"]==runner.EXPECTED_SEEDS
    seen=set()
    for block in seeds["provider_reconstruction"].values():
        bank=set(runner._seed_tuple(block))
        assert not seen.intersection(bank)
        seen.update(bank)
    wb=set(range(
        int(seeds["final_whitebox"]["start"]),
        int(seeds["final_whitebox"]["end_inclusive"])+1,
    ))
    graph=set(runner._seed_tuple(seeds["graph_prediction"]["M1_M2_common_bank"]))
    assert not seen.intersection(wb)
    assert not seen.intersection(graph)
    assert not wb.intersection(graph)


def test_v3_output_namespace_does_not_overwrite_v2():
    v2=(runner.HERE/"results"/"03_reconstruction").resolve()
    v3=runner.DEFAULT_ROOT.resolve()
    assert v3!=v2
    assert str(v3).endswith("results/03_reconstruction_v3")


def test_v3_has_no_rmse_instantiability_gate():
    cfg=read_json(runner.CFG)
    assert cfg["behavioral_centrality"]["hard_rmse_compatibility_gate"] is False
    assert cfg["methods"]["M2"]["hard_compatibility_gate"] is False
