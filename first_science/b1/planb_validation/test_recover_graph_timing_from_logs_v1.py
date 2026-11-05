"""Synthetic tests for read-only PRAISE B1 archival log-time recovery."""
import json
from pathlib import Path
import tempfile
import unittest

import recover_graph_timing_from_logs_v1 as recover


class RecoveryTests(unittest.TestCase):
    def test_exact_time_parsers(self):
        self.assertAlmostEqual(recover.get_time("real 734m48.127s"),44088.127)
        self.assertAlmostEqual(recover.get_time("real\t81m45.026s"),4905.026)
        self.assertAlmostEqual(recover.get_time("real 1h5m3.2s"),3903.2)
        self.assertAlmostEqual(recover.get_time("real 3600.4"),3600.4)
        self.assertAlmostEqual(recover.get_time(
            "Elapsed (wall clock) time (h:mm:ss or m:ss): 12:14:48.127"),44088.127)
        self.assertIsNone(recover.get_time(
            "GRAPH BENCHMARK PROJECTION: ~120.0 min for remaining trajectories"))
        self.assertIsNone(recover.get_time("estimated remaining=70.4 min"))

    def test_real_fixedcv_log_with_no_clock_cannot_claim_timing(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            p=root/"first_science/b1/local_audit/fixed_cv_top1_top14/run.log"
            p.parent.mkdir(parents=True)
            p.write_text("\n".join([
                "=== FIXED CV 1/12: P1__G_PAR ===",
                "P1__G_PAR: frozen Top14 graph predictions; starting separate Top1",
                "PREDICTED AND FROZEN P1__G_PAR: 735 grid points per method",
                "B1_FIXED_CV_TOP1_TOP14_STAGE_ALL_PASS",
                ""]))
            rows,info=recover.inspect_log(p,root)
            self.assertEqual(info["status"],"READ")
            self.assertTrue(any(row["kind"]=="fixed_cv_finished" for row in rows))
            self.assertEqual([r for r in rows if r["kind"]=="shell_measured_wall"],[])

    def test_actual_shell_time_and_projection_not_confused(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            p=root/"first_science/b1/local_audit/original_top1/run.log"
            p.parent.mkdir(parents=True)
            p.write_text("\n".join([
                "GRAPH BENCHMARK PROJECTION: ~300 min for remaining trajectories",
                "GRAPH BENCHMARK COMPLETE: new=24, cached=0, wall=0.25min",
                "real 734m48.127s",""]))
            rows,_=recover.inspect_log(p,root)
            exact=[r for r in rows if r["kind"]=="shell_measured_wall"]
            self.assertEqual(len(exact),1)
            self.assertEqual(exact[0]["seconds"],44088.127)
            self.assertTrue(any(r["kind"]=="graph_benchmark_projection" for r in rows))

    def test_complete_utc_is_not_execution_time(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            folder=root/"first_science/phase5/results/b1_pilot_m3_retrospective_v1/predictions"
            for i,cell in enumerate(recover.CELLS[:2]):
                p=folder/cell/"prediction_manifest.json"
                p.parent.mkdir(parents=True)
                p.write_text(json.dumps({
                    "status":"B1_RETROSPECTIVE_CELL_PREDICTED",
                    "completed_utc":f"2026-10-19T{13+i:02d}:54:07+00:00",
                }))
            events,gaps,coverage=recover.manifest_events(root)
            self.assertEqual(coverage["original_style"]["frozen_manifests"],2)
            self.assertEqual(coverage["fixed_cv"]["with_completed_utc"],0)
            self.assertEqual(len(gaps),1)
            self.assertEqual(gaps[0]["seconds_between_completions"],3600.)
            self.assertIn("not a measured",gaps[0]["interpretation"])


if __name__=="__main__":
    unittest.main()
