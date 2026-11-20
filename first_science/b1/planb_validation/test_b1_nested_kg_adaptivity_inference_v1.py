"""Synthetic, read-only tests for nested adaptive-versus-uniform KG inference."""
from __future__ import annotations

import unittest

import numpy as np

import b1_nested_kg_adaptivity_inference_v1 as analysis
import b1_nested_kg_vs_frozen_top2_inference_v1 as common


def fake_episodes(policy: str, intercept: float) -> list[dict]:
    result = []
    for budget in analysis.BUDGETS:
        for start in range(analysis.NSTART):
            for rep in range(analysis.REPEATS):
                result.append(dict(
                    policy=policy, budget=budget, start_index=start,
                    replicate=rep, simple_regret=(intercept + start * .00002
                                                   + rep * .00001 + (80-budget) * .00001),
                    correct=0,
                ))
    return result


class NestedKgAdaptivityTests(unittest.TestCase):
    def setUp(self):
        self.rows = (fake_episodes(analysis.ADAPTIVE, .002)
                     + fake_episodes(analysis.UNIFORM, .004))

    def test_policies_archive_count_and_budget_sets(self):
        self.assertEqual(analysis.POLICIES,
                         ("kg_two_stage_adaptive", "kg_two_stage_uniform"))
        self.assertEqual(len(analysis.BUDGETS), 13)
        self.assertEqual(set(analysis.ARCHIVES), {"historical", "fresh_reference"})
        self.assertEqual(len(analysis.AGGREGATIONS), 2)

    def test_complete_unique_episode_keys_required(self):
        self.assertEqual(len(common.normalize_rows(
            self.rows, analysis.POLICIES, analysis.BUDGETS, "synthetic")), 6240)
        with self.assertRaises(ValueError):
            common.normalize_rows(self.rows[:-1], analysis.POLICIES,
                                  analysis.BUDGETS, "missing")
        with self.assertRaises(ValueError):
            common.normalize_rows(self.rows[:-1] + self.rows[:1], analysis.POLICIES,
                                  analysis.BUDGETS, "duplicate")

    def test_obvious_adaptive_advantage_detected(self):
        per_budget, aggregate = analysis.infer(
            self.rows, "historical", nboot=1200, seed=1000
        )
        self.assertEqual(len(per_budget), 13)
        self.assertEqual(len(aggregate), 2)
        for record in per_budget + aggregate:
            self.assertAlmostEqual(record["mean_regret_diff"], -.002, places=12)
            self.assertLess(record["high95"], 0)
        for record in aggregate:
            self.assertLess(record["high_familywise95"], 0)
            self.assertLessEqual(record["low_familywise95"], record["low95"])
            self.assertLessEqual(record["high95"], record["high_familywise95"])

    def test_exact_seed_reproducibility(self):
        a = analysis.infer(self.rows, "fresh_reference", 1200, 9901)
        b = analysis.infer(self.rows, "fresh_reference", 1200, 9901)
        self.assertEqual(a, b)

    def test_each_policy_retains_its_budget_correlation(self):
        arr = np.arange(analysis.NSTART * analysis.REPEATS, dtype=float).reshape(
            analysis.NSTART, analysis.REPEATS
        )
        identical_budgets = {b: arr for b in analysis.BUDGETS}
        draws = np.random.default_rng(11).integers(
            analysis.REPEATS, size=(1100, analysis.NSTART, analysis.REPEATS)
        )
        boot = analysis.bootstrap_policy_path(identical_budgets, draws)
        self.assertTrue(all(np.array_equal(boot[analysis.BUDGETS[0]], boot[b])
                            for b in analysis.BUDGETS[1:]))

    def test_missing_outcome_cannot_become_zero(self):
        with self.assertRaises(ValueError):
            common.matrix_by_budget(self.rows[:-1], analysis.UNIFORM)


if __name__ == "__main__":
    unittest.main()
