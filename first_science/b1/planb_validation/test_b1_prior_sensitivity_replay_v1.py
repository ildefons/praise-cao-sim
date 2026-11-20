"""Synthetic-only and archival-protocol checks for the prior-sensitivity replay."""
from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

import numpy as np

import b1_prior_sensitivity_replay_v1 as audit


class PriorSensitivityTests(unittest.TestCase):
    @staticmethod
    def synthetic():
        return np.array([[.025 + .011 * a + .002 * (c % 4) + .004 * (c // 4)
                          for c in range(12)] for a in range(7)], dtype=float)

    def test_design_has_fourteen_frozen_cases_and_original_nine_policies(self):
        self.assertEqual(len(audit.SCENARIOS), 14)
        self.assertEqual(audit.SCENARIOS["base"], audit.BASE)
        self.assertEqual(len(audit.POLICIES), 9)
        self.assertEqual(len(set(audit.POLICIES)), 9)
        self.assertEqual(audit.TOP2,
                         ("budgeted_top2", "top2_two_stage_adaptive", "top2_two_stage_uniform"))
        self.assertEqual(audit.BUDGETS, (10, 15, 20, 25, 30, 35, 40, 45, 55, 65, 70, 75, 80))
        self.assertTrue(all(min(params[:4]) > 0 for params in audit.SCENARIOS.values()))

    def test_prior_configuration_changes_values_and_restores_exactly(self):
        original = (audit.frozen.PRIOR_VAR.copy(), audit.frozen.PRIOR_MEAN.copy(),
                    audit.frozen.NOISE, audit.frozen.balanced_score)
        with audit.prior_configuration("world_graph_swap"):
            self.assertAlmostEqual(audit.frozen.PRIOR_VAR[1], .045 ** 2)
            self.assertAlmostEqual(audit.frozen.PRIOR_VAR[4], .07 ** 2)
        np.testing.assert_array_equal(audit.frozen.PRIOR_VAR, original[0])
        np.testing.assert_array_equal(audit.frozen.PRIOR_MEAN, original[1])
        self.assertEqual(audit.frozen.NOISE, original[2])
        self.assertIs(audit.frozen.balanced_score, original[3])
        with self.assertRaisesRegex(RuntimeError, "restore"):
            with audit.prior_configuration("all_prior_double"):
                raise RuntimeError("restore")
        np.testing.assert_array_equal(audit.frozen.PRIOR_VAR, original[0])

    def test_posterior_is_actually_recomputed_under_prior(self):
        seen = [(a, 0, float(self.synthetic()[a, 0])) for a in range(7)]
        with audit.prior_configuration("intercept_half"):
            low = audit.frozen.posterior(seen, 7)[0]
        with audit.prior_configuration("intercept_double"):
            high = audit.frozen.posterior(seen, 7)[0]
        self.assertGreater(np.max(np.abs(low - high)), 1e-5)

    def test_acquisition_cannot_query_hidden_reference_cells(self):
        y = self.synthetic()
        seen = [(a, 0, float(y[a, 0])) for a in range(7)]
        with audit.prior_configuration("graph_double"):
            a = audit.nested.select_action("kg_two_stage_adaptive", seen,
                    audit.nested.make_streams(audit.SEED, 0, 3, "kg_two_stage_adaptive"))
            # The selector sees precisely the same observations, regardless
            # of how every unobserved cell in the full matrix is modified.
            altered = y.copy()
            altered[:, 1:] = 1 - altered[:, 1:]
            identical_seen = [(method, 0, float(altered[method, 0])) for method in range(7)]
            b = audit.nested.select_action("kg_two_stage_adaptive", identical_seen,
                    audit.nested.make_streams(audit.SEED, 0, 3, "kg_two_stage_adaptive"))
        self.assertEqual(a, b)

    def test_nested_and_budget_specific_policy_paths(self):
        y = self.synthetic()
        with audit.prior_configuration("base"):
            scored, trace = audit.nested.episode(
                y, "historical", "kg_two_stage_adaptive", 1, 0,
                checkpoints=(10, 15))
            self.assertEqual([x["budget"] for x in scored], [10, 15])
            self.assertEqual(len(trace), 15)
            top2_joint, _ = audit.frozen.evaluate_episode(
                y, "budgeted_top2", 15, 1, 0, audit.SEED)
            top2_adaptive, _ = audit.controlled.episode(
                y, "top2_two_stage_adaptive", 15, 1, 0, audit.frozen, audit.kg)
        self.assertEqual(top2_joint["evaluations"], 15)
        self.assertEqual(top2_adaptive["evaluations"], 15)

    def test_complete_stratification_rejects_duplicates_and_missing(self):
        rows = []
        for archive in audit.ARCHIVES:
            for policy in audit.POLICIES:
                for budget in audit.BUDGETS:
                    for start in range(12):
                        for rep in range(2):
                            rows.append(dict(scenario="base", archive=archive,
                                             policy=policy, budget=budget,
                                             start_index=start, replicate=rep,
                                             recommended="M1", correct=1,
                                             simple_regret=0.01))
        matrices, _ = audit.normalized_matrices(rows, "base", 2)
        self.assertAlmostEqual(matrices["historical", "random", 10].mean(), 0.01)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit.normalized_matrices(rows[:-1] + [rows[0]], "base", 2)
        with self.assertRaisesRegex(ValueError, "Incorrect terminal count"):
            audit.normalized_matrices(rows[:-1], "base", 2)

    def test_published_baseline_comparison_requires_all_234_keys(self):
        rows = [dict(archive=a, policy=p, budget=b, mean_regret=0.25)
                for a in audit.ARCHIVES for p in audit.POLICIES for b in audit.BUDGETS]
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "reference.csv"
            with file.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            audit.compare_base(rows, file)
            with self.assertRaisesRegex(ValueError, "disagrees"):
                audit.compare_base([dict(rows[0], mean_regret=0.24), *rows[1:]], file)
            with file.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows[:-1])
            with self.assertRaisesRegex(ValueError, "incomplete"):
                audit.compare_base(rows, file)

    def test_independent_bootstraps_and_zero_regret_contrast(self):
        matrices = {(a, p, b): np.full((12, 2), 0.012)
                    for a in audit.ARCHIVES for p in audit.POLICIES for b in audit.BUDGETS}
        contrasts, robustness = audit.scenario_inference("base", matrices, 2, 1000)
        self.assertEqual(len(contrasts), 2 * (len(audit.POLICIES) - 1))
        self.assertEqual(len(robustness), 2)
        self.assertTrue(all(abs(x["mean_regret_diff"]) < 1e-12
                            and abs(x["low95"]) < 1e-12
                            and abs(x["high95"]) < 1e-12 for x in contrasts))


if __name__ == "__main__":
    unittest.main()
