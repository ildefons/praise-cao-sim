from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import run_phase5_final_wb_v3b_fullsupport as wb

HERE=Path(__file__).resolve().parent


def test_final_wb_runner_uses_frozen_n1000_bank_and_namespace():
    assert wb._wb_seeds()==list(range(54000,55000))
    assert wb.ROOT==HERE/"results"/"05_final_wb_v3b_fullsupport"
    assert wb._horizons()==[float(x) for x in range(0,241,5)]


def test_hidden_surrogate_materialization_matches_frozen_world_formula():
    contracts=wb.load_phase5_contracts(HERE)
    s=wb._hidden_surrogates(contracts,"P1")
    # P1 provider means are all 330M instructions; x=.5 and IPT=1e9.
    for provider in wb.PROVIDERS:
        assert np.isclose(s[provider].mean_service_time,0.165)
        assert np.isclose(s[provider].cost_rate,3.0)
        assert np.isclose(s[provider].service_cv,0.3)


def test_wilson_reference_interval_contains_empirical_probability():
    lo,hi=wb.wilson_binomial_interval(900,1000)
    assert lo<0.9<hi
    assert 0.0<=lo<=hi<=1.0


def test_final_wb_runner_does_not_load_prediction_values_for_reference_generation():
    source=Path(wb.__file__).read_text(encoding="utf-8")
    # Prediction manifests/hashes are allowed only as the irreversible unlock.
    # Prediction curves themselves must never be inputs to WB generation.
    assert "m0_predictions.csv" not in source
    assert "m1_predictions.csv" not in source
    assert "m2_predictions.csv" not in source
    assert "m3_predictions_full343_and_nested.csv" not in source


def test_final_wb_contract_keeps_p2_excluded():
    c=json.loads((HERE/"config_phase5_final_wb_v3b_fullsupport.json").read_text())
    assert c["scope"]["gate_failed_provider_world"]=="P2"
    assert c["scope"]["eligible_physical_cells"]==12
    assert c["scope"]["gate_failed_physical_cells"]==4
