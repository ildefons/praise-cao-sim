"""Regression checks for budget-independent nested B1 trajectories."""
from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

import numpy as np

import b1_budget_comparison_v1 as frozen
import b1_nested_budget_replay_v1 as nested


def synthetic_matrix() -> np.ndarray:
    # All 84 outcomes are fixed, distinct, finite, and between zero and one.
    return np.array([
        [.09 + .014 * a + .0015 * c + .002 * (c % 4) for c in range(12)]
        for a in range(7)
    ])


class NestedTrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.matrix = synthetic_matrix()

    def test_only_budget_independent_policies_included(self):
        self.assertEqual(len(nested.POLICIES), 6)
        self.assertFalse(any("top2" in p for p in nested.POLICIES))
        self.assertEqual(nested.BUDGETS[-1], 80)
        self.assertEqual(len(nested.BUDGETS), 13)
        with self.assertRaises(ValueError):
            nested.episode(self.matrix, "test", "budgeted_top2", 0, 0)

    def test_every_policy_is_prefix_invariant(self):
        for policy in nested.POLICIES:
            with self.subTest(policy=policy):
                short, short_history = nested.episode(
                    self.matrix, "test", policy, 2, 5,
                    checkpoints=(10, 15),
                )
                long, long_history = nested.episode(
                    self.matrix, "test", policy, 2, 5,
                    checkpoints=(10, 15, 20),
                )
                self.assertEqual(short, long[:2])
                self.assertEqual(short_history, long_history[:15])
                self.assertEqual(len(long_history), 20)
                self.assertEqual([row["evaluations"] for row in long], [10, 15, 20])
                actions = [(r["method"], r["world"], r["graph"])
                           for r in long_history]
                self.assertEqual(len(actions), len(set(actions)))

    def test_reproducible_and_archive_not_in_random_seed(self):
        first = nested.episode(self.matrix, "historical", "kg_two_stage_uniform", 6, 3,
                               checkpoints=(10, 15))
        second = nested.episode(self.matrix.copy(), "fresh_reference",
                                "kg_two_stage_uniform", 6, 3,
                                checkpoints=(10, 15))
        third = nested.episode(self.matrix, "historical", "kg_two_stage_uniform", 6, 3,
                               checkpoints=(10, 15))
        self.assertEqual(first, third)
        # Different archive labels do not change the selected actions or scores.
        self.assertEqual([r["method"] for r in first[1]],
                         [r["method"] for r in second[1]])
        self.assertEqual([r["simple_regret"] for r in first[0]],
                         [r["simple_regret"] for r in second[0]])

    def test_action_selector_does_not_access_hidden_outcomes(self):
        for policy in nested.POLICIES:
            with self.subTest(policy=policy):
                seen = [(a, 0, float(self.matrix[a, 0])) for a in range(7)]
                # All unobserved outcomes can be changed without affecting the
                # next acquisition: only seen observations enter the selector.
                altered = self.matrix.copy()
                altered[:, 1:] = 0.99
                observed_after_change = [(a, 0, float(altered[a, 0]))
                                         for a in range(7)]
                original = nested.select_action(policy, seen,
                    nested.make_streams(nested.SEED, 0, 1, policy))
                changed = nested.select_action(policy, observed_after_change,
                    nested.make_streams(nested.SEED, 0, 1, policy))
                self.assertEqual(original, changed)

    def test_balanced_can_continue_to_eighty_evaluations(self):
        scored, history = nested.episode(
            self.matrix, "test", "balanced", 0, 0,
            checkpoints=(75, 80),
        )
        self.assertEqual(len(history), 80)
        self.assertEqual(len(set((r["method"], r["world"], r["graph"])
                                 for r in history)), 80)
        self.assertEqual([r["budget"] for r in scored], [75, 80])

    def test_terminal_regret_is_finite_and_nonnegative(self):
        for policy in nested.POLICIES:
            scored, _ = nested.episode(
                self.matrix, "test", policy, 0, 0, checkpoints=(10, 15)
            )
            for row in scored:
                self.assertGreaterEqual(row["simple_regret"], 0)
                self.assertTrue(np.isfinite(row["simple_regret"]))
                self.assertIn(row["recommended"], frozen.METHODS)

    def test_matrix_parser_rejects_duplicate_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.csv"
            rows = [dict(method=frozen.METHODS[a], world=w, graph=g,
                         mae=float(self.matrix[a, c]))
                    for a in range(7) for c, (w, g) in enumerate(frozen.CELLS)]
            with path.open("w", newline="") as out:
                writer = csv.DictWriter(out, fieldnames=("method", "world", "graph", "mae"))
                writer.writeheader()
                writer.writerows(rows)
            np.testing.assert_array_equal(nested.parse_matrix(path), self.matrix)
            rows[-1] = rows[0]
            with path.open("w", newline="") as out:
                writer = csv.DictWriter(out, fieldnames=("method", "world", "graph", "mae"))
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(ValueError):
                nested.parse_matrix(path)

    def test_summary_uses_matched_indices_and_13_budget_design(self):
        # Tiny synthetic score table: no expensive simulation required.
        rows = []
        for archive in nested.EXPECTED_SHAS:
            for policy_index, policy in enumerate(nested.POLICIES):
                for budget in (10, 15):
                    for start in range(12):
                        for replicate in range(2):
                            rows.append(dict(
                                archive=archive, policy=policy, budget=budget,
                                start_index=start, replicate=replicate,
                                simple_regret=.01 * policy_index + .001 * replicate,
                                correct=int(policy_index == 0),
                            ))
        summaries, contrasts = nested.statistics(rows, 2, 100, nested.SEED,
                                                  checkpoints=(10, 15))
        self.assertEqual(len(summaries), 2 * 2 * len(nested.POLICIES))
        self.assertEqual(len(contrasts), 2 * 3 * len(nested.CONTRAST_PAIRS))
        one = next(r for r in contrasts if r["archive"] == "historical"
                   and r["budget"] == 10
                   and r["contrast"] == "kg_one_step minus balanced")
        self.assertAlmostEqual(one["mean_regret_diff"], .02, places=12)
        self.assertAlmostEqual(one["low"], .02, places=12)
        self.assertAlmostEqual(one["high"], .02, places=12)


if __name__ == "__main__":
    unittest.main()
