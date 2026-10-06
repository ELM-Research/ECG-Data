"""Whole-report and statement changes across all included report pairs."""

from collections import Counter

from ecg_data.analysis.software_v_human.reports import normalize_report

NORMALIZATION = {"case": "lower", "duplicates": "collapse", "order": "ignore", "blanks": "drop"}
INPUTS = ("nonempty", "software_empty", "physician_empty", "both_empty", "missing", "invalid")
CHANGES = ("unchanged", "added_only", "deleted_only", "both")
STATEMENTS = ("retained", "added", "deleted")


def classify_change(added, deleted):
    if added and deleted:
        return "both"
    if added:
        return "added_only"
    if deleted:
        return "deleted_only"
    return "unchanged"


def compare_reports(software, physician, *, empty_reports):
    """Return literal changes; missing or excluded inputs have no change label."""
    if empty_reports not in ("exclude", "compare"):
        raise ValueError("Choose empty_reports: 'exclude' or 'compare'.")

    result = {"input_status": "missing", "change": None, **{key: None for key in STATEMENTS}}
    if software is None or physician is None:
        return result

    try:
        original = set(normalize_report(software, **NORMALIZATION))
        final = set(normalize_report(physician, **NORMALIZATION))
    except TypeError:
        result["input_status"] = "invalid"
        return result

    status = "nonempty"
    if not original and not final:
        status = "both_empty"
    elif not original:
        status = "software_empty"
    elif not final:
        status = "physician_empty"
    result["input_status"] = status
    if status != "nonempty" and empty_reports == "exclude":
        return result

    added = final - original
    deleted = original - final
    result.update(
        change=classify_change(added, deleted),
        retained=sorted(original & final), added=sorted(added), deleted=sorted(deleted),
    )
    return result


def empty_counts():
    return {key: Counter() for key in ("inputs", "changes", *STATEMENTS)}


def count_reports(reports, *, empty_reports):
    """Count each statement once per pair, including unchanged reports."""
    results = {}
    for source, software, physician in reports:
        pair = compare_reports(software, physician, empty_reports=empty_reports)
        if source not in results:
            results[source] = empty_counts()
        counts = results[source]
        counts["inputs"][pair["input_status"]] += 1
        if pair["change"] is None:
            continue
        counts["changes"][pair["change"]] += 1
        for name in STATEMENTS:
            counts[name].update(pair[name])
    return results


def merge_counts(total, partial):
    for source, incoming in partial.items():
        if source not in total:
            total[source] = empty_counts()
        for name, values in incoming.items():
            total[source][name].update(values)


def summarize(totals, *, empty_reports, undefined_ratio):
    """Report every numerator and denominator; ratios are fractions, not percentages."""
    if empty_reports not in ("exclude", "compare"):
        raise ValueError("Choose empty_reports: 'exclude' or 'compare'.")

    def ratio(numerator, denominator):
        return numerator / denominator if denominator else undefined_ratio

    results = {}
    vocabulary = sorted(set().union(*(counts[name] for counts in totals.values() for name in STATEMENTS)))
    for source, counts in totals.items():
        total = sum(counts["inputs"].values())
        included = sum(counts["changes"].values())
        edited = included - counts["changes"]["unchanged"]
        terms = {}
        for term in vocabulary:
            retained, added, deleted = (counts[name][term] for name in STATEMENTS)
            software = retained + deleted
            physician = retained + added
            mentioned = retained + added + deleted
            terms[term] = {
                "retained": retained,
                "added": added,
                "deleted": deleted,
                "absent_from_both": included - mentioned,
                "software_report_count": software,
                "software_absent_report_count": included - software,
                "physician_report_count": physician,
                "mentioned_report_count": mentioned,
                "edited_report_count": added + deleted,
                "disagreement_rate": ratio(added + deleted, mentioned),
                "added_report_ratio": ratio(added, included - software),
                "deleted_report_ratio": ratio(deleted, software),
            }
        results[source] = {
            "study": "edits",
            "normalization": NORMALIZATION,
            "empty_reports": empty_reports,
            "input_reports": total,
            "included_reports": included,
            "excluded_reports": total - included,
            "input_status_counts": {status: counts["inputs"][status] for status in INPUTS},
            "report_counts": {change: counts["changes"][change] for change in CHANGES},
            "report_rates": {change: ratio(counts["changes"][change], included) for change in CHANGES},
            "edited_reports": edited,
            "edit_rate": ratio(edited, included),
            "terms": terms,
        }
    return results
