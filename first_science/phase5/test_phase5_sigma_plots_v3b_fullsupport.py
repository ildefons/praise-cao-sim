from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import run_phase5_sigma_plots_v3b_fullsupport as sp

HERE=Path(__file__).resolve().parent


def _synthetic_queries()->pd.DataFrame:
    rows=[]
    for world in sp.WORLDS:
        for graph in sp.GRAPHS:
            cell=f"{world}__{graph}"
            for regime in sp.REGIMES:
                for k,rho in enumerate([0.95,0.975,0.9833333333333333,0.99,0.995]):
                    rows.append({
                        "physical_cell_id":cell,
                        "query_id":f"{cell}__{regime}__{k}",
                        "provider_world_id":world,
                        "graph_id":graph,
                        "rho_label":f"R{k}",
                        "rho":rho,
                        "regime":regime,
                    })
    return pd.DataFrame(rows)


def test_contract_method_and_panel_sets():
    c=json.loads((HERE/"config_phase5_sigma_plots_v3b_fullsupport.json").read_text())
    assert tuple(c["methods"])==("WB","M0","M1","M2","M3_FULL343")
    assert tuple(c["provider_worlds"])==sp.WORLDS
    assert tuple(c["graph_ids"])==sp.GRAPHS
    assert tuple(c["regimes"])==sp.REGIMES
    assert c["plot"]["total_panels"]==36


def test_representative_query_selection_is_median_rho_and_complete():
    selected=sp.select_representative_queries(_synthetic_queries())
    assert len(selected)==36
    assert selected["query_id"].nunique()==36
    assert np.allclose(
        selected["rho"].astype(float).to_numpy(),
        0.9833333333333333,
        atol=1e-15,rtol=0.0,
    )


def test_lower_median_rule_if_even():
    q=pd.DataFrame([
        {
            "physical_cell_id":"P1__G_PAR",
            "query_id":f"Q{i}",
            "provider_world_id":"P1",
            "graph_id":"G_PAR",
            "rho_label":f"R{i}",
            "rho":rho,
            "regime":"Easy",
        }
        for i,rho in enumerate([0.1,0.2,0.3,0.4])
    ])
    # Exercise the index formula directly because production selection asserts
    # five frozen queries per panel.
    ordered=q.sort_values(["rho","query_id"],kind="mergesort").reset_index(drop=True)
    got=ordered.iloc[(len(ordered)-1)//2]
    assert got["query_id"]=="Q1"


def test_script_is_visualization_only_no_simulator_execution():
    source=Path(sp.__file__).read_text(encoding="utf-8")
    forbidden=(
        "execute_one_phase5_graph_trajectory",
        "phase5_graph_simulator_v2",
        "m1_graph_simulator_v2",
        "run_phase5_step0_v2",
    )
    for token in forbidden:
        assert token not in source


def test_expected_figure_names():
    names=[]
    for graph in sp.GRAPHS:
        names.extend([
            f"phase5_sigma_{graph}.png",
            f"phase5_sigma_{graph}.pdf",
        ])
    assert len(names)==8
    assert "phase5_sigma_G_PAR.png" in names
    assert "phase5_sigma_G_PARSEQ.pdf" in names
