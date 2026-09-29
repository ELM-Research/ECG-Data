import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ecg_data.analysis.software_v_human.main import analyze, process_report


class ReportAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.path = Path(cls.directory.name)
        pairs = [
            ("sinus rhythm", "sinus rhythm"),
            ("sinus rhythm sinus rhythm", "sinus rhythm"),
            ("sinus rhythm", "atrial fibrillation"),
            ("normal tracing", "normal ECG"),
            ("", "sinus rhythm"),
            ("ATRIAL FIBRILLATION", "atrial fibrillation"),
            ("normal", "normal"),
            (None, "sinus rhythm"),
        ]
        reports = [("example", *pair) for pair in pairs]
        reports += [("missing", None, "sinus rhythm")]
        reports += [("unchanged", "sinus rhythm", "sinus rhythm")]
        analyze(map(process_report, reports), cls.path)

    def table(self, name, comparison="example"):
        with (self.path / comparison / f"{name}.csv").open() as file:
            return {(r["cohort"], r["term"]): r for r in csv.DictReader(file)}

    def test_report_cohorts_include_term_free_pairs(self):
        summary = json.loads((self.path / "example/summary.json").read_text())
        self.assertEqual(summary["total_reports"], 8)
        self.assertEqual(summary["analyzed_reports"], 7)
        self.assertEqual(summary["modified_reports"], 5)
        self.assertEqual(summary["unchanged_reports"], 2)
        self.assertEqual(summary["excluded_reports"], 1)
        self.assertEqual(summary["reports_without_listed_terms"], 2)

    def test_repeated_mentions_are_not_report_counts(self):
        row = self.table("counts")[("all", "sinus rhythm")]
        self.assertEqual(int(row["original_term_frequency"]), 4)
        self.assertEqual(int(row["original_report_count"]), 3)
        self.assertEqual(int(row["final_term_frequency"]), 3)
        self.assertEqual(int(row["final_report_count"]), 3)

    def test_four_groups_and_ratio_denominators(self):
        rows = self.table("changes")
        row = rows[("modified", "sinus rhythm")]
        self.assertEqual(int(row["group_1_retained"]), 1)
        self.assertEqual(int(row["group_2_deleted"]), 1)
        self.assertEqual(int(row["group_3_added"]), 1)
        self.assertEqual(int(row["group_4_never_present"]), 2)
        self.assertEqual(float(row["added_report_ratio"]), 1 / 3)
        self.assertEqual(float(row["deleted_report_ratio"]), 1 / 2)
        counts = self.table("counts")
        prevalence = self.table("prevalence")
        self.assertEqual(len(rows), 69 * 3)
        self.assertEqual(rows.keys(), counts.keys())
        self.assertEqual(rows.keys(), prevalence.keys())
        for key, row in rows.items():
            retained = int(row["group_1_retained"])
            deleted = int(row["group_2_deleted"])
            added = int(row["group_3_added"])
            absent = int(row["group_4_never_present"])
            total = int(prevalence[key]["report_count"])
            self.assertEqual(retained + deleted + added + absent, total)
            self.assertEqual(retained + deleted, int(counts[key]["original_report_count"]))
            self.assertEqual(retained + added, int(counts[key]["final_report_count"]))
            expected = (retained + deleted) / total
            self.assertEqual(float(prevalence[key]["original_report_proportion"]), expected)

    def test_zero_denominators_and_empty_modified_cohorts(self):
        for comparison in ("missing", "unchanged"):
            changes = self.table("changes", comparison)
            prevalence = self.table("prevalence", comparison)
            for key, row in changes.items():
                if key[0] != "modified":
                    continue
                self.assertEqual(row["added_report_ratio"], "")
                self.assertEqual(row["deleted_report_ratio"], "")
                self.assertEqual(prevalence[key]["original_report_proportion"], "")
        unobserved = self.table("changes")[("modified", "brugada pattern")]
        self.assertEqual(unobserved["added_report_ratio"], "0.0")
        self.assertEqual(unobserved["deleted_report_ratio"], "")

    def test_text_comparison_precedes_term_normalization(self):
        _, cohort, matches = process_report(("example", "SINUS  RHYTHM", "sinus rhythm"))
        self.assertEqual(cohort, "modified")
        self.assertEqual(matches, [("Sinus rhythm", "sinus rhythm", 1, 1)])
        _, cohort, _ = process_report(("example", ["sinus rhythm", "stemi"], "sinus rhythm stemi"))
        self.assertEqual(cohort, "unchanged")
        _, _, matches = process_report(("example", "no stemi; historical stemi", "nonstemi"))
        self.assertEqual(matches, [("Ischemia related", "stemi", 2, 0)])


if __name__ == "__main__":
    unittest.main()
