#!/usr/bin/env python3
"""Synthetic-only tests for the PRAISE E1a surrogate structure comparison.

Run locally. This file does not read frozen outcomes or invoke simulators.
"""
from __future__ import annotations

import itertools
import math
import unittest

import numpy as np

import b1_budget_comparison_v1 as frozen
import b1_e1a_surrogate_structure_v1 as e1a


class StructuralSurrogateTests(unittest.TestCase):
    def setUp(self):
        self.kernels = e1a.model_kernels()
        # Deterministic synthetic losses with additive and interaction patterns.
        self.matrix = np.array([
            [0.08 + 0.012 * a + 0.011 * (c // 4) + 0.006 * (c % 4)
             + (0.12 if a == 2 and c == 0 else 0.0)
             for c in range(e1a.N_CELLS)]
            for a in range(e1a.N_METHODS)
        ], dtype=float)

    def test_model_scales_and_interaction_shrinkage(self):
        diagonal = np.diag(self.kernels["B_additive"])
        for kernel in self.kernels.values():
            np.testing.assert_allclose(np.diag(kernel), diagonal, atol=1e-14)
            self.assertGreaterEqual(np.linalg.eigvalsh(kernel).min(), -1e-12)
        b = self.kernels["B_additive"]
        a = self.kernels["A_independent"]
        c25 = self.kernels["C_interaction_25"]
        c50 = self.kernels["C_interaction_50"]
        self.assertAlmostEqual(a[0, 1], 0)
        self.assertGreater(b[0, 1], c25[0, 1])
        self.assertGreater(c25[0, 1], c50[0, 1])
        self.assertGreater(c50[0, 1], 0)

    def test_no_hidden_outcome_leakage(self):
        obs = (0, 2, 6)
        for label, kernel in self.kernels.items():
            before = e1a.posterior_predictions(self.matrix, obs, kernel)
            altered = self.matrix.copy()
            altered[:, [c for c in range(12) if c not in obs]] += 0.5
            after = e1a.posterior_predictions(altered, obs, kernel)
            for old, new in zip(before, after):
                np.testing.assert_allclose(old, new, atol=1e-12,
                                           err_msg=f"Hidden leakage in {label}")

    def test_independent_model_has_no_cross_cell_transfer(self):
        pred, _ = e1a.posterior_predictions(self.matrix, (0,),
                                             self.kernels["A_independent"])
        np.testing.assert_allclose(pred[:, 1:],
                                   np.full((7, 11), e1a.PRIOR_MEAN), atol=1e-14)

    def test_additive_matches_original_coefficient_posterior(self):
        mask = (0, 3, 4, 7, 9)
        pred, _ = e1a.posterior_predictions(self.matrix, mask,
                                             self.kernels["B_additive"])
        seen = [(a, c, float(self.matrix[a, c]))
                for a in range(e1a.N_METHODS) for c in mask]
        original_means, _, _ = frozen.posterior(seen, methods=e1a.N_METHODS)
        np.testing.assert_allclose(pred.mean(axis=1), original_means,
                                   atol=1e-11, rtol=1e-11)

    def test_exact_mask_count_and_coverages(self):
        masks = [mask for n in range(1, 12)
                 for mask in itertools.combinations(range(12), n)]
        self.assertEqual(len(masks), 4094)
        for n in range(1, 12):
            level = [m for m in masks if len(m) == n]
            self.assertEqual(len(level), math.comb(12, n))
            seen = [sum(c in mask for mask in level) for c in range(12)]
            self.assertEqual(len(set(seen)), 1)

    def test_prediction_metrics_are_finite(self):
        for label, kernel in self.kernels.items():
            row, heldout, abs_error = e1a.evaluate_mask(self.matrix, (0, 2, 6), kernel)
            self.assertEqual(len(heldout), 9)
            self.assertEqual(abs_error.shape, (7, 9))
            for field in ("heldout_mae", "heldout_rmse", "heldout_gaussian_nll",
                          "domain_mean_mae", "simple_regret"):
                self.assertTrue(np.isfinite(float(row[field])), msg=f"{label}:{field}")
            self.assertGreaterEqual(row["simple_regret"], 0)

    def test_reject_repeated_or_full_mask(self):
        kernel = self.kernels["B_additive"]
        for bad in ((), (0, 0), tuple(range(12)), (12,)):
            with self.assertRaises(ValueError):
                e1a.posterior_predictions(self.matrix, bad, kernel)


if __name__ == "__main__":
    unittest.main()
