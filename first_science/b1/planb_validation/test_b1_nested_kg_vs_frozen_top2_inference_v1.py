"""Read-only regression checks for cross-design nested KG/Top2 bootstrap."""
from __future__ import annotations

from pathlib import Path
import unittest

import b1_nested_kg_vs_frozen_top2_inference_v1 as analysis


def synthetic(policy: str, baseline: float) -> list[dict]:
    rows = []
    for budget in analysis.BUDGETS:
        for start in range(analysis.NSTART):
            for rep in range(analysis.REPEATS):
                # Deliberately shared within-trajectory pattern over budgets.
                regret = baseline + .00003 * start + .00001 * rep + .00002 * (80 - budget)
                rows.append(dict(policy=policy, budget=budget,
                                 start_index=start, replicate=rep,
                                 simple_regret=regret, correct=0))
    return rows


class CrossDesignTests(unittest.TestCase):
    def setUp(self):
        self.kg = synthetic(analysis.KG, .002)
        self.top2 = [r for p in analysis.TOP2 for r in synthetic(p, .004)]

    def test_expected_policies_and_two_archive_protocol(self):
        self.assertEqual(len(analysis.TOP2), 3)
        self.assertEqual(len(analysis.BUDGETS), 13)
        self.assertIn("fresh_reference", analysis.ARCHIVES)
        self.assertEqual(len(analysis.AGGREGATIONS), 2)

    def test_complete_key_and_zero_duplicate_validation(self):
        self.assertEqual(len(analysis.normalize_rows(
            self.kg, (analysis.KG,), analysis.BUDGETS, "synthetic"
        )), 3120)
        with self.assertRaises(ValueError):
            analysis.normalize_rows(self.kg[:-1], (analysis.KG,),
                                    analysis.BUDGETS, "missing")
        with self.assertRaises(ValueError):
            analysis.normalize_rows(self.kg[:-1] + self.kg[:1], (analysis.KG,),
                                    analysis.BUDGETS, "duplicate")

    def test_missing_outcome_is_not_treated_as_zero(self):
        with self.assertRaises(ValueError):
            analysis.matrix_by_budget(self.kg[:-1], analysis.KG)

    def test_bootstrap_finds_clear_effect_with_corrected_intervals(self):
        per_budget, aggregate = analysis.infer(
            self.kg, self.top2, "fresh_reference", nboot=1200, seed=1234
        )
        self.assertEqual(len(per_budget), 3 * 13)
        self.assertEqual(len(aggregate), 3 * 2)
        for row in aggregate:
            self.assertAlmostEqual(row["mean_regret_diff"], -.002, places=12)
            self.assertLess(row["high_familywise95"], 0)
            self.assertLessEqual(row["low_familywise95"], row["low95"])
            self.assertLessEqual(row["high95"], row["high_familywise95"])
        also = analysis.infer(self.kg, self.top2, "fresh_reference", 1200, 1234)
        self.assertEqual((per_budget, aggregate), also)

    def test_real_fresh_archives_match_original_figures(self):
        # Reads tracked immutable episodes only. No policies or simulations run.
        repo = Path(analysis.__file__).resolve().parent
        rows, source = analysis.load_top2("fresh_reference", repo, None, None)
        self.assertEqual(len(rows), 3 * 13 * 12 * 20)
        self.assertIn("old_sha256", source)
        for policy in analysis.TOP2:
            self.assertEqual(len(analysis.matrix_by_budget(rows, policy)), 13)

    def test_historical_requires_frozen_controlled_ledger(self):
        repo = Path(analysis.__file__).resolve().parent
        with self.assertRaises(ValueError):
            analysis.load_top2("historical", repo, None, None)


if __name__ == "__main__":
    unittest.main()
