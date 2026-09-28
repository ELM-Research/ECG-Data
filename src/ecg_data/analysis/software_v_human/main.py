import csv
import json
import re
from pathlib import Path
from multiprocessing import Pool

import numpy as np

from ecg_data.analysis.software_v_human.terms import TERMS
from ecg_data.preprocess.config.load import get_config


PATTERNS = {
    term: re.compile(rf"\b{re.escape(term)}\b")
    for terms in TERMS.values()
    for term in terms
}


def to_text(report):
    if isinstance(report, list):
        report = " ".join(report)
    return " ".join(report.lower().split())


def process_report(report):
    name, original, final = report
    if original is None or final is None:
        return name, None, None

    # Compare complete text before normalizing case and whitespace.
    if isinstance(original, list):
        original = " ".join(original)
    if isinstance(final, list):
        final = " ".join(final)

    cohort = "unchanged" if original == final else "modified"
    original, final = to_text(original), to_text(final)
    matches = []

    for category, terms in TERMS.items():
        for term in terms:
            before = len(PATTERNS[term].findall(original))
            after = len(PATTERNS[term].findall(final))
            if not before and not after:
                continue
            matches.append((category, term, before, after))

    return name, cohort, matches


def read_reports(data_path, data_name):
    if data_name == "agh":
        for path in sorted(Path(data_path).glob("*.json")):
            for instance in json.loads(path.read_text()):
                yield (
                    "agh",
                    instance.get("OriginalDiagnosis"),
                    instance.get("Diagnosis"),
                )
        return

    if data_name == "heedb":
        for path in sorted(Path(data_path).glob("*/*.npy")):
            instance = np.load(path, allow_pickle=True).item()
            physician = instance.get("reports_physician")
            yield "heedb_old", instance.get("reports_software_old"), physician
            yield "heedb_new", instance.get("reports_software_new"), physician
        return

    raise ValueError(f"Unknown dataset: {data_name}")


def analyze(reports, save_path):
    summaries = {}
    rows = {}

    for name, cohort, matches in reports:
        if name not in summaries:
            summaries[name] = {
                "total_reports": 0,
                "analyzed_reports": 0,
                "excluded_reports": 0,
                "reports_without_listed_terms": 0,
                "unchanged_reports": 0,
                "modified_reports": 0,
            }

            # Include every term, even when it never appears in a cohort.
            for group in ("all", "unchanged", "modified"):
                for category, terms in TERMS.items():
                    for term in terms:
                        rows[(name, group, term)] = {
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
                        }

        summary = summaries[name]
        summary["total_reports"] += 1

        if matches is None:
            summary["excluded_reports"] += 1
            continue

        # These reports remain in the analysis and its denominators.
        if not matches:
            summary["reports_without_listed_terms"] += 1

        summary["analyzed_reports"] += 1
        summary[f"{cohort}_reports"] += 1

        for category, term, before, after in matches:
            for group in ("all", cohort):
                row = rows[(name, group, term)]
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
        summary["skipped_reports"] = summary["excluded_reports"]
        summary["unchanged_proportion"] = (
            summary["unchanged_reports"] / total if total else None
        )
        summary["modified_proportion"] = (
            summary["modified_reports"] / total if total else None
        )

        result = []
        for (comparison, cohort, term), row in rows.items():
            if comparison != name:
                continue

            count = total if cohort == "all" else summary[f"{cohort}_reports"]
            row["report_count"] = count
            row["original_report_proportion"] = (
                row["original_report_count"] / count if count else None
            )
            row["final_report_proportion"] = (
                row["final_report_count"] / count if count else None
            )

            g1 = row["group_1_retained"]
            g2 = row["group_2_deleted"]
            g3 = row["group_3_added"]
            g4 = count - g1 - g2 - g3

            row["group_4_never_present"] = g4
            row["added_report_ratio"] = (
                g3 / (g3 + g4) if g3 + g4 else None
            )
            row["deleted_report_ratio"] = (
                g2 / (g1 + g2) if g1 + g2 else None
            )
            result.append(row)

        path = Path(save_path) / name
        path.mkdir(parents=True, exist_ok=True)

        (path / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n"
        )

        with (path / "terms.csv").open("w", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "cohort",
                    "category",
                    "term",
                    "report_count",
                    "original_term_frequency",
                    "original_report_count",
                    "original_report_proportion",
                    "final_term_frequency",
                    "final_report_count",
                    "final_report_proportion",
                    "group_1_retained",
                    "group_2_deleted",
                    "group_3_added",
                    "group_4_never_present",
                    "added_report_ratio",
                    "deleted_report_ratio",
                ],
            )
            writer.writeheader()
            writer.writerows(result)

        print(
            f"{name}: {total} analyzed, "
            f"{summary['excluded_reports']} excluded for missing reports "
            f"({summary['reports_without_listed_terms']} analyzed reports "
            f"contained no listed terms)"
        )


if __name__ == "__main__":
    cfg = get_config()

    with Pool() as pool:
        reports = pool.imap_unordered(
            process_report,
            read_reports(cfg["data_path"], cfg["data_name"]),
            chunksize=100,
        )
        analyze(reports, cfg["save_path"])
