"""Literal report comparison shared by LLM analysis and cost estimation."""

from ecg_data.analysis.software_v_human.reports import normalize_report

NORMALIZATION = {"case": "lower", "duplicates": "collapse", "order": "ignore", "blanks": "drop"}
INPUTS = ("nonempty", "software_empty", "physician_empty", "both_empty", "missing", "invalid", "skip_statement")
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


def compare_reports(software, physician, *, empty_reports, truncate=(), remove=(), skip=()):
    """Return literal changes; missing or excluded inputs have no change label."""
    if empty_reports not in ("exclude", "compare"):
        raise ValueError("Choose empty_reports: 'exclude' or 'compare'.")
    if not isinstance(skip, (list, tuple)) or any(
        not isinstance(term, str) or not term.strip() for term in skip
    ):
        raise ValueError("skip must be a list of nonblank phrases.")

    result = {"input_status": "missing", "change": None, **{key: None for key in STATEMENTS}}
    if software is None or physician is None:
        return result

    try:
        original = set(normalize_report(software, **NORMALIZATION, truncate=truncate, remove=remove))
        final = set(normalize_report(physician, **NORMALIZATION, truncate=truncate, remove=remove))
    except TypeError:
        result["input_status"] = "invalid"
        return result

    if any(term.lower() in statement.lower()
           for report in (software, physician) for statement in report for term in skip):
        result["input_status"] = "skip_statement"
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
