"""Read-only synthetic and frozen-source tests for B1 world/cost feasibility audit."""
import json
from pathlib import Path
import tempfile
import unittest

import audit_independent_world_cost_v0_1 as audit


class AuditFeasibilityTests(unittest.TestCase):
    def test_frozen_contract_trajectory_accounting(self):
        root=Path(__file__).resolve().parents[3]
        worlds,cost,sources=audit.inspect_contracts(root)
        self.assertEqual([r["id"] for r in worlds["world_rows"]],["P1","P2","P3","P4"])
        self.assertEqual([r["original_eligible"] for r in worlds["world_rows"]],[True,False,True,True])
        self.assertEqual(cost["prediction_trajectories_per_cell"],9800)
        self.assertEqual(cost["total_graph_trajectories_per_complete_12_cell_battery"],129600)
        self.assertEqual(cost["step0_trajectories_for_12_cells_if_every_calibration_passes"],4800)
        self.assertEqual(cost["I1_graph_trajectories_for_three_new_worlds"],600)
        self.assertEqual(cost["original_style_provider_local_candidate_trajectories_for_three_worlds"],43200)
        self.assertEqual(cost["fixed_cv_provider_local_candidate_trajectories_for_three_worlds"],43200)
        self.assertGreater(len(sources),10)

    def test_missing_timing_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/"first_science/phase5/results/04_prediction_v3b_fullsupport/P1__G_PAR"
            base.mkdir(parents=True)
            (base/"prediction_manifest.json").write_text(json.dumps({
                "status":"FROZEN_PHASE5_V3B_FULLSUPPORT_PREDICTION",
                "python_wall_seconds":7200.0,
                "simulation_wall_seconds":6800.0,
            }))
            rows,summary=audit.inventory_manifests(root)
            phase=[v for v in summary if v["stage"]=="PhaseII_M1_M2_M3_combined"][0]
            self.assertEqual(phase["present_manifest_count"],1)
            self.assertEqual(phase["count_with_measured_python_wall_seconds"],1)
            self.assertEqual(phase["sum_python_wall_hours"],2.0)
            self.assertEqual(phase["count_with_simulation_wall_seconds"],1)
            original=[v for v in summary if v["stage"]=="original_Top14_Top1_combined"][0]
            self.assertEqual(original["present_manifest_count"],0)
            self.assertEqual(original["sum_python_wall_hours"],"")
            self.assertEqual(len(rows),3+9+12*6)


if __name__=="__main__":
    unittest.main()
