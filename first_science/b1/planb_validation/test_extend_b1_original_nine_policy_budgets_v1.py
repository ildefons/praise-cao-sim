"""Regression: generalized 13-budget pipeline preserves all frozen B0001 math."""

from __future__ import annotations

import csv
import io
from pathlib import Path
import sys
import unittest
import zipfile
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b1_budget_comparison_v1 as baseline
import b1_kg_one_step_v1 as kg
import b1_condition_selection_controlled_v1 as controlled
import extend_b1_original_nine_policy_budgets_v1 as ext


ROOT = Path(__file__).resolve().parent
ARCHIVE = (
    ROOT / "results/b0001_original_policies_v1/"
    "b0001_original_policy_replay_v1_complete.zip"
)


class OriginalReplayRegression(unittest.TestCase):
    def test_balanced_compatibility_for_exhausted_last_method(self):
        seen = [(a, c, float(a + c)) for a in range(7) for c in range(12)
                if a == 6 or c < 10]
        visited = {(a, c) for a, c, _ in seen}
        available = [(a, c, 0) for a in range(7) for c in range(12)
                     if (a, c) not in visited]
        self.assertTrue(available)
        self.assertEqual(max(a for a, _, _ in available), 5)
        for seed in range(10):
            pick = ext.balanced_score_full_catalog(
                seen, available, np.random.default_rng(seed)
            )
            self.assertIn(pick, {(a, c) for a, c, _ in available})

        # In the original regime, delegate directly, preserving exact RNG.
        seen = [(a, 0, float(a)) for a in range(7)]
        available = [(a, c, 0) for a in range(7) for c in range(1, 12)]
        for seed in range(10):
            expected = ext.FROZEN_BALANCED_SCORE(
                seen, available, np.random.default_rng(seed)
            )
            observed = ext.balanced_score_full_catalog(
                seen, available, np.random.default_rng(seed)
            )
            self.assertEqual(observed, expected)

    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ARCHIVE) as package:
            cls.rows = {}
            names = (
                "01_baseline/terminal_episodes.csv",
                "01_baseline/budget_summary.csv",
                "01_baseline/paired_regret_contrasts.csv",
                "02_kg/kg_terminal_episodes.csv",
                "02_kg/kg_budget_summary.csv",
                "02_kg/kg_vs_frozen_b1_contrasts.csv",
                "03_controlled/controlled_terminal_episodes.csv",
                "03_controlled/controlled_budget_summary.csv",
                "03_controlled/controlled_paired_contrasts.csv",
            )
            for name in names:
                data = package.read("outputs/b0001_original_scripts/" + name)
                cls.rows[name] = list(csv.DictReader(io.StringIO(data.decode())))

    def assert_same_rows(self, found, expected, keys):
        found = sorted(found, key=lambda r: tuple(str(r[k]) for k in keys))
        expected = sorted(expected, key=lambda r: tuple(str(r[k]) for k in keys))
        self.assertEqual(len(found), len(expected))
        numeric = {
            "mean_regret", "regret_low", "regret_high", "p_correct",
            "p_low", "p_high", "regret_p90", "mean_regret_diff", "low", "high",
        }
        for got, recorded in zip(found, expected):
            self.assertEqual(set(got), set(recorded))
            for key in got:
                if key in numeric:
                    self.assertAlmostEqual(float(got[key]), float(recorded[key]), delta=1e-12)
                else:
                    self.assertEqual(str(got[key]), str(recorded[key]))

    @staticmethod
    def numeric_episodes(rows):
        out = []
        for r in rows:
            converted = dict(r)
            for field in ("budget", "start_index", "replicate", "correct", "evaluations"):
                if field in converted:
                    converted[field] = int(converted[field])
            converted["simple_regret"] = float(converted["simple_regret"])
            out.append(converted)
        return out

    def test_original_source_hashes_unchanged(self):
        expected = {
            baseline: "11c36f80a6fb0faf2a325a590f29ff48b3f08dc80a34a4ba606e0bc268aac2ac",
            kg: "cd79f4b3c87445cdd020d8b8bbd441432f9ccba5960de34ec5bbf4464d68fb94",
            controlled: "78633ab2ff993f967446add90b3efa0d836adf908c5c278d5c82e1efb1dbe39d",
        }
        for module, expected_sha in expected.items():
            self.assertEqual(ext.digest(Path(module.__file__)), expected_sha)

    def test_original_budget_summaries_reproduced_exactly(self):
        self.assertEqual(ext.NEW_BUDGETS, (25, 35, 45, 55, 65, 70, 75, 80))
        self.assertTrue(all(7 <= b < 84 for b in ext.NEW_BUDGETS))
        base_rows = self.numeric_episodes(self.rows["01_baseline/terminal_episodes.csv"])
        kg_rows = self.numeric_episodes(self.rows["02_kg/kg_terminal_episodes.csv"])
        ctrl_rows = self.numeric_episodes(self.rows["03_controlled/controlled_terminal_episodes.csv"])

        bsummary, bcontrasts = baseline.summarize(
            base_rows, ext.HISTORICAL_BUDGETS, ext.REPEATS, ext.BOOTSTRAPS, ext.SEED
        )
        self.assert_same_rows(bsummary, self.rows["01_baseline/budget_summary.csv"],
                              ("budget", "policy"))
        self.assert_same_rows(bcontrasts, self.rows["01_baseline/paired_regret_contrasts.csv"],
                              ("budget", "contrast"))

        ksummary, kcontrasts = ext.kg_statistics(
            kg_rows, base_rows, ext.HISTORICAL_BUDGETS
        )
        self.assert_same_rows(ksummary, self.rows["02_kg/kg_budget_summary.csv"],
                              ("budget", "policy"))
        self.assert_same_rows(kcontrasts, self.rows["02_kg/kg_vs_frozen_b1_contrasts.csv"],
                              ("budget", "contrast"))

        csummary, ccontrasts = controlled.statistics(ctrl_rows)
        self.assert_same_rows(csummary, self.rows["03_controlled/controlled_budget_summary.csv"],
                              ("budget", "policy"))
        self.assert_same_rows(ccontrasts, self.rows["03_controlled/controlled_paired_contrasts.csv"],
                              ("budget", "family", "contrast"))


if __name__ == "__main__":
    unittest.main()
