import csv
import json
import re
from pathlib import Path

import numpy as np

from ecg_data.analysis.software_v_human.terms import TERMS
from ecg_data.preprocess.config.load import get_config


def _text(report):
    if isinstance(report, list):
        report = " ".join(report)
    return " ".join(report.lower().split())


def _read_reports(data_path, data_name):
    if data_name == "agh":
        for path in sorted(Path(data_path).glob("*.json")):
            for instance in json.loads(path.read_text()):
                yield "agh", instance.get("OriginalDiagnosis"), instance.get("Diagnosis")
        return

    if data_name == "heedb":
        for path in sorted(Path(data_path).glob("*/*.npy")):
            instance = np.load(path, allow_pickle=True).item()
            physician = instance.get("reports_physician")
            yield "heedb_old", instance.get("reports_software_old"), physician
            yield "heedb_new", instance.get("reports_software_new"), physician
        return

    raise ValueError(f"Unknown dataset: {data_name}")


def _analyze(reports, save_path):
    summaries = {}
    rows = {}
    patterns = {term: re.compile(rf"\b{re.escape(term)}\b") for terms in TERMS.values() for term in terms}

    for name, original, final in reports:
        summary = summaries.setdefault(name, {
            "total_reports": 0,
            "analyzed_reports": 0,
            "excluded_reports": 0,
            "skipped_no_terms": 0,
            "unchanged_reports": 0,
            "modified_reports": 0,
        })
        summary["total_reports"] += 1
        if original is None or final is None:
            summary["excluded_reports"] += 1
            continue
        original, final = _text(original), _text(final)

        matches = []
        cohort = "unchanged"
        for category, terms in TERMS.items():
            for term in terms:
                before = len(patterns[term].findall(original))
                after = len(patterns[term].findall(final))
                if not before and not after:
                    continue
                matches.append((category, term, before, after))
                if not before or not after:
                    cohort = "modified"

        if not matches:
            summary["skipped_no_terms"] += 1
            continue

        summary["analyzed_reports"] += 1
        summary[f"{cohort}_reports"] += 1

        for category, term, before, after in matches:
            for group in ("all", cohort):
                row = rows.setdefault((name, group, term), {
                    "cohort": group,
                    "category": category,
                    "term": term,
                    "original_term_frequency": 0,
                    "original_report_count": 0,
                    "final_term_frequency": 0,
                    "final_report_count": 0,
                    "group_1_retained": 0,
                    "group_2_deleted": 0,
                    "group_3_added": 0,
                })
                row["original_term_frequency"] += before
                row["original_report_count"] += int(before > 0)
                row["final_term_frequency"] += after
                row["final_report_count"] += int(after > 0)
                if before and after:
                    row["group_1_retained"] += 1
                elif before:
                    row["group_2_deleted"] += 1
                else:
                    row["group_3_added"] += 1

    if not summaries:
        raise ValueError("No reports found.")

    for name, summary in summaries.items():
        total = summary["analyzed_reports"]
        summary["skipped_reports"] = summary["excluded_reports"] + summary["skipped_no_terms"]
        summary["unchanged_proportion"] = summary["unchanged_reports"] / total if total else None
        summary["modified_proportion"] = summary["modified_reports"] / total if total else None
        result = []
        for (comparison, cohort, term), row in rows.items():
            if comparison != name:
                continue
            count = total if cohort == "all" else summary[f"{cohort}_reports"]
            row["report_count"] = count
            row["original_report_proportion"] = row["original_report_count"] / count
            row["final_report_proportion"] = row["final_report_count"] / count
            result.append(row)

        path = Path(save_path) / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        with (path / "terms.csv").open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=[
                "cohort", "category", "term", "report_count",
                "original_term_frequency", "original_report_count", "original_report_proportion",
                "final_term_frequency", "final_report_count", "final_report_proportion",
                "group_1_retained", "group_2_deleted", "group_3_added",
            ])
            writer.writeheader()
            writer.writerows(result)
        print(f"{name}: {total} analyzed, {summary['skipped_reports']} skipped "
              f"({summary['skipped_no_terms']} no listed terms, {summary['excluded_reports']} missing reports)")


if __name__ == "__main__":
    cfg = get_config()
    _analyze(_read_reports(cfg["data_path"], cfg["data_name"]), cfg["save_path"])
