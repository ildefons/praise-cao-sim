"""Regression checks: overlay only three frozen Top2 curves onto nested six."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

import plot_b1_nested_with_frozen_top2_v1 as plot


def fake_row(policy, budget, archive=None, regret=.004):
    row = dict(
        budget=budget, policy=policy, episodes=240, mean_regret=regret,
        regret_low=regret * .8, regret_high=regret * 1.2,
        p_correct=.6, p_low=.5, p_high=.7, regret_p90=regret * 1.5,
    )
    if archive is not None:
        row["archive"] = archive
    return row


def save(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class PlotTop2Tests(unittest.TestCase):
    def test_policy_partition_is_exact(self):
        self.assertEqual(len(plot.NESTED), 6)
        self.assertEqual(len(plot.TOP2), 3)
        self.assertEqual(len(set(plot.NESTED + plot.TOP2)), 9)
        self.assertFalse(set(plot.NESTED) & set(plot.TOP2))
        self.assertEqual(len(plot.BUDGETS), 13)

    def test_overlay_retains_nested_six_and_imports_only_top2(self):
        n = [fake_row(p, b, "historical", .001)
             for p in plot.NESTED for b in plot.BUDGETS]
        original = [fake_row(p, b, regret=.009)
                    for p in plot.POLICIES for b in plot.BUDGETS]
        overlay = plot.combine(n, [r for r in original if r["policy"] in plot.TOP2],
                               "historical")
        self.assertEqual(len(overlay), 117)
        for row in overlay:
            if row["policy"] in plot.TOP2:
                self.assertEqual(row["source_design"], "budget_specific_frozen")
                self.assertEqual(row["mean_regret"], .009)
            else:
                self.assertEqual(row["source_design"], "nested_80_step_prefix")
                self.assertEqual(row["mean_regret"], .001)

    def test_rejects_duplicate_and_missing_top2_budgets(self):
        rows = [fake_row(p, b) for p in plot.TOP2 for b in plot.BUDGETS]
        with self.assertRaises(ValueError):
            plot.validated_rows(rows[:-1] + rows[:1], "bad", plot.TOP2, "historical")
        with self.assertRaises(ValueError):
            plot.validated_rows(rows[:-1], "bad", plot.TOP2, "historical")

    def test_rejects_wrong_archive_and_bad_intervals(self):
        rows = [fake_row(p, b, "fresh_reference")
                for p in plot.TOP2 for b in plot.BUDGETS]
        with self.assertRaises(ValueError):
            plot.validated_rows(rows, "bad", plot.TOP2, "historical")
        rows[0]["regret_low"] = .9
        with self.assertRaises(ValueError):
            plot.validated_rows(rows, "bad", plot.TOP2, "fresh_reference")

    def test_y_axis_never_clips_95_percent_interval(self):
        data = [dict(regret_high=.011), dict(regret_high=.009)]
        self.assertAlmostEqual(plot.axis_max(data, .012), .012)
        data[0]["regret_high"] = .014
        self.assertGreaterEqual(plot.axis_max(data, .012), .014)

    def test_manifest_verified_read_of_both_archives(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            nested = root / "nested"
            old = root / "original"
            nested.mkdir()
            old.mkdir()
            old_tables = old / "tables"
            old_tables.mkdir()
            all_nested = [fake_row(p, b, a, .001) for a in plot.ARCHIVES
                          for p in plot.NESTED for b in plot.BUDGETS]
            save(nested / "nested_budget_summary.csv", all_nested)
            nm = dict(
                status="B1_NESTED_BUDGET_REPLAY_V1_COMPLETE",
                budgets=plot.BUDGETS, policies=plot.NESTED,
                budget_in_seed=False, repeats_per_start=20,
                archive_sources={a: dict(sha256=plot.EXPECTED_MATRIX_SHA[a])
                                 for a in plot.ARCHIVES},
                outputs_sha256={"nested_budget_summary.csv":
                                plot.digest(nested / "nested_budget_summary.csv")},
            )
            (nested / "nested_manifest.json").write_text(json.dumps(nm))
            old_hashes = {}
            for archive in plot.ARCHIVES:
                old_name = plot.OLD_ARCHIVE[archive]
                path = old_tables / f"{old_name}_nine_policy_13_budget_regret.csv"
                save(path, [fake_row(p, b, regret=.009) for p in plot.POLICIES
                            for b in plot.BUDGETS])
                old_hashes[path.name] = plot.digest(path)
            om = dict(
                status="B1_HISTORICAL_AND_B0001_NINE_POLICY_13_BUDGET_COMMON_AXIS_PASS",
                budgets=plot.BUDGETS, policies=plot.POLICIES,
                per_policy_budget_episodes=240, bootstrap_draws=2000,
                source_sha256={f"{label}_frozen": sha
                               for label, sha in plot.EXPECTED_FROZEN_FIVE_BUDGET_SHA.items()},
                output_sha256=old_hashes,
            )
            (old / "plot_manifest.json").write_text(json.dumps(om))
            series, source_files = plot.load_checked_sources(
                nested, old, Path(plot.__file__).resolve().parent
            )
            self.assertEqual({a: len(rows) for a, rows in series.items()},
                             {a: 117 for a in plot.ARCHIVES})
            self.assertIn("original_plot_manifest.json", source_files)
            # Accept both the archived root and its tables/ subdirectory.
            via_tables, _ = plot.load_checked_sources(
                nested, old_tables, Path(plot.__file__).resolve().parent
            )
            self.assertEqual(series, via_tables)


if __name__ == "__main__":
    unittest.main()
