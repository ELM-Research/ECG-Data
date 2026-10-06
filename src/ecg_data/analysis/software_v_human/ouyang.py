"""Study ztaf119: term changes within modified reports.

Groups: 1 retained, 2 deleted, 3 added, 4 absent from both reports.
Deduplication makes term frequencies equal report counts.
"""

from collections import Counter

from ecg_data.analysis.software_v_human.reports import normalize_report
from ecg_data.analysis.software_v_human.terms import TERMS

NORMALIZATION = {"case": "lower", "duplicates": "collapse", "order": "ignore"}
TERM_COUNTS = ("unchanged_terms", "group_1", "group_2", "group_3")


def _categories(terms):
    categories = {
        term.lower(): category
        for category, values in terms.items()
        for term in values
    }
    return categories


def empty_counts():
    return {
        "unchanged_reports": 0,
        "modified_reports": 0,
        **{name: Counter() for name in TERM_COUNTS},
    }


def count_reports(reports, terms=TERMS):
    """Return additive counts; defer ratios until all batches are merged."""
    selected = _categories(terms).keys()
    results = {}
    for source, software, physician in reports:
        original = normalize_report(software, **NORMALIZATION)
        final = normalize_report(physician, **NORMALIZATION)
        if source not in results:
            results[source] = empty_counts()
        counts = results[source]
        if original == final:
            counts["unchanged_reports"] += 1
            counts["unchanged_terms"].update(set(original) & selected)
            continue

        counts["modified_reports"] += 1
        original = set(original) & selected
        final = set(final) & selected
        counts["group_1"].update(original & final)
        counts["group_2"].update(original - final)
        counts["group_3"].update(final - original)
    return results


def merge_counts(total, partial):
    for source, incoming in partial.items():
        if source not in total:
            total[source] = empty_counts()
        counts = total[source]
        counts["unchanged_reports"] += incoming["unchanged_reports"]
        counts["modified_reports"] += incoming["modified_reports"]
        for name in TERM_COUNTS:
            counts[name].update(incoming[name])


def summarize(totals, terms=TERMS, *, undefined_ratio):
    """Return per-source metrics; zero denominators use undefined_ratio."""
    categories = _categories(terms)
    results = {}
    for source, counts in totals.items():
        unchanged = counts["unchanged_reports"]
        modified = counts["modified_reports"]
        metrics = {}
        for term, category in categories.items():
            group_1 = counts["group_1"][term]
            group_2 = counts["group_2"][term]
            group_3 = counts["group_3"][term]
            group_4 = modified - group_1 - group_2 - group_3
            original = group_1 + group_2
            final = group_1 + group_3
            absent = group_3 + group_4
            unchanged_count = counts["unchanged_terms"][term]
            metrics[term] = {
                "category": category,
                "unchanged_report_count": unchanged_count,
                "group_1": group_1,
                "group_2": group_2,
                "group_3": group_3,
                "group_4": group_4,
                "original_term_frequency": original,
                "original_report_count": original,
                "final_term_frequency": final,
                "final_report_count": final,
                "unchanged_report_proportion": unchanged_count / unchanged if unchanged else undefined_ratio,
                "modified_original_report_proportion": original / modified if modified else undefined_ratio,
                "modified_final_report_proportion": final / modified if modified else undefined_ratio,
                "added_report_ratio": group_3 / absent if absent else undefined_ratio,
                "deleted_report_ratio": group_2 / original if original else undefined_ratio,
            }
        results[source] = {
            "unchanged_reports": unchanged,
            "modified_reports": modified,
            "terms": metrics,
        }
    return results


def ouyang(reports, terms=TERMS, *, undefined_ratio):
    """Calculate study metrics from (source, software, physician) triples."""
    return summarize(count_reports(reports, terms), terms, undefined_ratio=undefined_ratio)
