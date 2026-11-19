#!/usr/bin/env python3
"""Synthetic unit tests of the frozen B0001 seven-method scoring contracts.

No simulator, hidden world, B0001 white-box result, or predictor archive is
loaded. Run: python -m unittest -v test_evaluate_b0001_seven_method_accuracy_v1
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).with_name("evaluate_b0001_seven_method_accuracy_v1.py")
SPEC = importlib.util.spec_from_file_location("b0001_accuracy_under_test", SCRIPT)
score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score)


def fake_reference(cell="P1__G_PAR", level=0.40):
    world, graph = cell.split("__")
    rows = []
    for query in range(15):
        for horizon in range(0, 241, 5):
            rows.append({
                "query_id": f"Q{query:02d}",
                "provider_world_id": world,
                "graph_id": graph,
                "rho_label": "rho_0.8", "rho": 0.8, "regime": "Mid",
                "H": float(horizon), "sigma_wb": level,
                "wb_n": 1000, "wb_successes": int(level * 1000),
                "wb_ci_lower": 0.3, "wb_ci_upper": 0.5,
            })
    return pd.DataFrame(rows)


def fake_prediction(reference, method="M1", offset=0.05):
    pred = reference[list(score.KEYS)].copy()
    pred["sigma_hat"] = reference["sigma_wb"].to_numpy() + offset
    pred["method_id"] = method
    return pred


class AccuracyScoringTests(unittest.TestCase):
    def test_primary_window_555_and_registered_metrics(self):
        ref = fake_reference()
        p = fake_prediction(ref, offset=0.05)
        scored = score.join_primary(p, ref, "M1", "P1__G_PAR")
        self.assertEqual(len(scored), 555)
        self.assertEqual(scored["H"].min(), 60)
        self.assertEqual(scored["H"].max(), 240)
        m = score.metrics(scored)
        self.assertAlmostEqual(m["MAE"], 0.05)
        self.assertAlmostEqual(m["RMSE"], 0.05)
        self.assertAlmostEqual(m["signed_bias"], 0.05)
        self.assertAlmostEqual(m["max_abs_error"], 0.05)
        expected = np.sqrt(0.05**2 - 0.4 * 0.6 / 999)
        self.assertAlmostEqual(m["reference_noise_adjusted_RMSE"], expected)

    def test_incomplete_or_duplicated_predictions_fail_closed(self):
        ref = fake_reference()
        p = fake_prediction(ref)
        with self.assertRaisesRegex(RuntimeError, "incomplete/duplicate"):
            score.join_primary(p.iloc[:-1], ref, "M1", "P1__G_PAR")
        with self.assertRaisesRegex(RuntimeError, "incomplete/duplicate"):
            score.join_primary(pd.concat([p.iloc[:-1], p.iloc[:1]]),
                               ref, "M1", "P1__G_PAR")

    def test_nonmatching_frozen_query_metadata_fail_closed(self):
        ref = fake_reference()
        p = fake_prediction(ref)
        p.loc[p.index[0], "rho"] = 0.81
        with self.assertRaisesRegex(RuntimeError, "mismatched prediction/WB keys"):
            score.join_primary(p, ref, "M1", "P1__G_PAR")

    def test_nonfinite_and_out_of_range_prediction_fail_closed(self):
        ref = fake_reference()
        p = fake_prediction(ref)
        p.loc[p.index[0], "sigma_hat"] = np.nan
        with self.assertRaisesRegex(RuntimeError, "nonfinite/out-of-range"):
            score.join_primary(p, ref, "M1", "P1__G_PAR")
        p.loc[p.index[0], "sigma_hat"] = 1.1
        with self.assertRaisesRegex(RuntimeError, "nonfinite/out-of-range"):
            score.join_primary(p, ref, "M1", "P1__G_PAR")

    def test_original_m3_fullsupport_filters_nested_diagnostics(self):
        ref = fake_reference()
        p = fake_prediction(ref, "M3_FULL343")
        nested = fake_prediction(ref, "M3_TOP14")
        combined = pd.concat([p, nested], ignore_index=True)
        scored = score.join_primary(combined, ref, "M3_FULL343", "P1__G_PAR")
        self.assertEqual(len(scored), 555)
        self.assertEqual(set(scored["method_id"]), {"M3_FULL343"})

    def test_seven_by_twelve_matrix_and_equal_cell_primary_mean(self):
        frames = []
        for i, method in enumerate(score.METHODS):
            for j, cell in enumerate(score.CELLS):
                ref = fake_reference(cell, level=0.35)
                offset = 0.01 + i * 0.005 + j * 0.001
                pred = fake_prediction(ref, method, offset=offset)
                frames.append(score.join_primary(pred, ref, method, cell))
        joined = pd.concat(frames, ignore_index=True)
        out = score.summarize(joined)
        self.assertEqual(len(out["method_cell_metrics"]), 84)
        self.assertEqual(len(out["seven_method_matrix"]), 84)
        self.assertEqual(len(out["overall_accuracy"]), 7)
        self.assertEqual(len(joined), 7 * 12 * 555)
        m1 = out["overall_accuracy"].iloc[0]
        self.assertAlmostEqual(m1["equal_cell_mean_MAE"],
                               0.01 + 5.5 * 0.001)
        self.assertAlmostEqual(m1["MAE"], m1["equal_cell_mean_MAE"])


if __name__ == "__main__":
    unittest.main()
