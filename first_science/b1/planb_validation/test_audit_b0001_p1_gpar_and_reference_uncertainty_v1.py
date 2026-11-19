#!/usr/bin/env python3
"""Synthetic correctness/regression checks; requires no real WB input files."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd

import audit_b0001_p1_gpar_and_reference_uncertainty_v1 as target


def make_ledger() -> pd.DataFrame:
    # All 1,000 complete trajectory ordinals exist, one request per trajectory.
    rows = []
    for i in range(1000):
        rows.append(dict(trajectory=i, trajectory_seed=42_000_000 + i,
                         request_id=i, emission=10.0, completion=12.0,
                         L=2.0, C=1.0, Q=1.0))
    return pd.DataFrame(rows)


class IndependentSlaTests(unittest.TestCase):
    def test_success_and_zero_decision_states(self) -> None:
        frame = make_ledger()
        states, diagnostics = target.independently_reconstruct_query(
            frame, latency_limit=5, cost_limit=2, quality_minimum=.5, rho=.95)
        self.assertEqual(states.shape, (49, 1000))
        self.assertTrue(states.all())
        self.assertEqual(diagnostics["zero_decision_states"], 3 * 1000)  # H=0,5,10

    def test_fail_latency_cost_quality_and_recover(self) -> None:
        frame = make_ledger()
        # On trajectory zero, a deadline-missed request fails at t=15; a
        # compliant later request restores cumulative fraction to rho=.5.
        frame.loc[0, "completion"] = np.nan
        frame = pd.concat([frame, pd.DataFrame([dict(
            trajectory=0, trajectory_seed=42_000_000,
            request_id=1001, emission=20.0, completion=22.0,
            L=2.0, C=1.0, Q=1.0)])], ignore_index=True)
        # One on-time cost failure and one on-time quality failure at t=12.
        frame.loc[1, "C"] = 10.0
        frame.loc[2, "Q"] = 0.0
        states, diagnostics = target.independently_reconstruct_query(
            frame, latency_limit=5, cost_limit=2, quality_minimum=.5, rho=.5)
        self.assertTrue(states[2, 0])   # H=10 before any decisions
        self.assertFalse(states[3, 0])  # H=15 missed deadline counted
        self.assertFalse(states[4, 0])  # H=20 still failing
        self.assertTrue(states[5, 0])   # H=25 recovers to 1/2
        self.assertFalse(states[3, 1])
        self.assertFalse(states[3, 2])
        self.assertTrue(states[3, 3])
        self.assertEqual(diagnostics["latency_deadline_failures_by_stop"], 1)
        self.assertEqual(diagnostics["cost_failures_by_stop"], 1)
        self.assertEqual(diagnostics["quality_failures_by_stop"], 1)
        self.assertEqual(diagnostics["decided_requests_by_stop"], 1001)

    def test_decision_at_deadline_inclusive_and_undecided_beyond_stop(self) -> None:
        frame = make_ledger()
        frame.loc[0, "completion"] = 15.0  # equality to latency deadline: in-time
        frame.loc[1, "completion"] = 16.0  # late: failure at t=15
        frame.loc[2, "emission"] = 239.0
        frame.loc[2, "completion"] = np.nan  # unresolved at stop=240
        states, diag = target.independently_reconstruct_query(
            frame, latency_limit=5, cost_limit=2, quality_minimum=.5, rho=1)
        self.assertTrue(states[3, 0])
        self.assertFalse(states[3, 1])
        self.assertTrue(states[-1, 2])
        self.assertEqual(diag["unresolved_requests_at_stop"], 1)

    def test_tolerance_for_near_deadline_completion(self) -> None:
        frame = make_ledger()
        frame.loc[0, "completion"] = 15.0 + 0.5e-12
        states, _ = target.independently_reconstruct_query(
            frame, latency_limit=5, cost_limit=2, quality_minimum=.5, rho=1)
        self.assertTrue(states[3, 0])

    def test_invalid_query_or_finite_completed_quality_fails_closed(self) -> None:
        frame = make_ledger()
        frame.loc[0, "Q"] = np.nan
        with self.assertRaisesRegex(RuntimeError, "finite C or Q"):
            target.independently_reconstruct_query(
                frame, latency_limit=5, cost_limit=2, quality_minimum=.5, rho=.95)
        with self.assertRaisesRegex(RuntimeError, "invalid frozen query"):
            target.independently_reconstruct_query(
                make_ledger(), latency_limit=-1, cost_limit=2,
                quality_minimum=.5, rho=.95)


class JointBootstrapTests(unittest.TestCase):
    def test_shared_index_weights_and_fixed_prediction_replicates(self) -> None:
        bits = np.zeros((2 * 555, 1000), dtype=np.uint8)
        bits[:, :500] = 1  # common trajectory pattern in both cells
        bits[555:, :] = 1 - bits[555:, :]
        pred = np.full((7, 1110), .5)
        indicator = np.zeros(1110, dtype=bool)
        indicator[:555] = True
        reps, summary = target.bootstrap(pred, bits, indicator, reps=4, seed=4, batch_size=2)
        rng = np.random.default_rng(4)
        for i in range(4):
            draw = rng.integers(0, 1000, size=1000, dtype=np.int32)
            frequency = np.bincount(draw, minlength=1000)
            reconstructed = bits.astype(float) @ frequency / 1000.0
            expected_mae = np.abs(pred[0, :] - reconstructed).mean()
            self.assertAlmostEqual(reps.loc[i, "MAE_M1"], expected_mae, places=7)
            self.assertAlmostEqual(reps.loc[i, "MAE_M3_FULL343"], expected_mae, places=7)
        self.assertEqual(len(summary), 7)
        self.assertEqual(reps["replicate"].tolist(), [1, 2, 3, 4])

    def test_anomaly_report_sign_and_query_support(self) -> None:
        keys = pd.DataFrame(dict(
            physical_cell_id=["P1__G_PAR"] * 555,
            query_id=[f"q{i}" for i in range(15) for _ in range(37)],
            H=list(range(60, 241, 5)) * 15,
        ))
        pred = np.full((7, 555), .8)
        pred[2, :] = .3  # M3
        wb = np.full(555, .9)
        detail = [dict(physical_cell_id="P1__G_PAR", query_id=f"q{i}",
                       rho=.95, rho_label="R0950", regime="Easy") for i in range(15)]
        frame, summary = target.anomaly_report(keys, pred, wb, detail)
        self.assertEqual(len(frame), 15)
        self.assertAlmostEqual(summary["M1_MAE"], .1)
        self.assertAlmostEqual(summary["M3_MAE"], .6)
        self.assertEqual(summary["M3_underprediction_fraction"], 1.)


class FrozenLedgerIntegrationTests(unittest.TestCase):
    def test_all_raw_points_reconstruct_and_tampered_reference_fails(self) -> None:
        with TemporaryDirectory() as root:
            base = Path(root)
            cell = "P1__G_PAR"
            ref_dir = base / "reference" / cell
            query_dir = base / "staging" / "frozen_queries" / cell
            ref_dir.mkdir(parents=True)
            query_dir.mkdir(parents=True)
            ledger = make_ledger()
            ledger.to_csv(ref_dir / "final_wb_ledger.csv", index=False)
            queries = []
            curves = []
            for i in range(15):
                q = dict(query_id=f"Q{i:02d}", provider_world_id="P1", graph_id="G_PAR",
                         rho_label="R0950", rho=.95, regime="Easy",
                         A_G_l_max=5.0, A_G_c_max=2.0, A_G_q_min=.5)
                queries.append(q)
                y, _ = target.independently_reconstruct_query(
                    ledger, latency_limit=5, cost_limit=2, quality_minimum=.5, rho=.95)
                for h, outcome in zip(range(0, 241, 5), y):
                    success = int(outcome.sum())
                    curves.append({**q, "H": h, "wb_successes": success,
                                   "sigma_wb": success / 1000., "wb_n": 1000})
            pd.DataFrame(queries).to_csv(query_dir / "step0_frozen_queries.csv", index=False)
            path = ref_dir / "final_wb_curves.csv"
            pd.DataFrame(curves).to_csv(path, index=False)
            a = SimpleNamespace(reference=base / "reference", staging=base / "staging")
            with mock.patch.object(target.original, "validate_curve", side_effect=lambda x, _cell: x, create=True), \
                    mock.patch.object(target.original, "reference_file", return_value=path, create=True):
                k, bits, detail = target.reconstruct_cell(a, cell)
                self.assertEqual(k.shape, (555, 3))
                self.assertEqual(bits.shape, (555, 1000))
                self.assertEqual(len(detail), 15)
                self.assertTrue(bits.all())
                # No silent acceptance if an original frozen score is different.
                curves[0]["wb_successes"] = 999
                pd.DataFrame(curves).to_csv(path, index=False)
                with self.assertRaisesRegex(RuntimeError, "mismatches frozen WB"):
                    target.reconstruct_cell(a, cell)


if __name__ == "__main__":
    unittest.main()
