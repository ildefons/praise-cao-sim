"""Source-only checks for the paper's frozen nested-six plus Top2 figures."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import unittest
from unittest import mock

import plot_nested_paper_figures_v1 as paper


class PaperFigureSourcesTests(unittest.TestCase):
    def test_all_nine_policies_complete_in_both_archives(self):
        checked = paper.checked_sources()
        self.assertEqual(set(checked), set(paper.plotting.ARCHIVES))
        for rows in checked.values():
            self.assertEqual(len(rows), 9 * 13)
            self.assertEqual({r["policy"] for r in rows}, set(paper.plotting.POLICIES))
            self.assertEqual({r["budget"] for r in rows}, set(paper.plotting.BUDGETS))

    def test_both_figure_axes_include_all_bootstrap_intervals(self):
        checked = paper.checked_sources()
        for archive, rows in checked.items():
            self.assertLessEqual(paper.plotting.axis_max(rows, paper.YMAX[archive]),
                                 paper.YMAX[archive] + 1e-12)

    def test_all_paper_comparison_ledgers_reconcile(self):
        # checked_sources independently verifies each published 13-budget
        # aggregate against the frozen figure summary and source manifests.
        self.assertEqual(sum(len(rows) for rows in paper.checked_sources().values()), 234)

    def test_rejects_tampered_summary(self):
        with tempfile.TemporaryDirectory() as scratch:
            altered = Path(scratch) / paper.SOURCE.name
            shutil.copyfile(paper.SOURCE, altered)
            with altered.open("a", encoding="utf-8") as dst:
                dst.write("\n")
            with mock.patch.object(paper, "SOURCE", altered):
                with self.assertRaises(ValueError):
                    paper.checked_sources()


if __name__ == "__main__":
    unittest.main()
