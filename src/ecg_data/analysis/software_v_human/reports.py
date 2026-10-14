import json
from pathlib import Path

import numpy as np


def normalize_report(report, *, case, duplicates, order, blanks="preserve", truncate=()):
    """Normalize statements without rewriting nonblank whitespace or punctuation."""
    if not isinstance(report, list) or any(not isinstance(s, str) for s in report):
        raise TypeError("Each report must be a list of strings.")
    if case not in ("lower", "preserve"):
        raise ValueError("case must be 'lower' or 'preserve'.")
    if duplicates not in ("collapse", "preserve"):
        raise ValueError("duplicates must be 'collapse' or 'preserve'.")
    if order not in ("ignore", "preserve"):
        raise ValueError("order must be 'ignore' or 'preserve'.")
    if blanks not in ("preserve", "drop"):
        raise ValueError("blanks must be 'preserve' or 'drop'.")
    if not isinstance(truncate, (list, tuple)) or any(
        not isinstance(term, str) or not term.strip() for term in truncate
    ):
        raise ValueError("truncate must be a list of nonblank phrases.")

    markers = [term.lower() for term in truncate]
    for index, statement in enumerate(report):
        if any(marker in statement.lower() for marker in markers):
            report = report[:index]
            break

    statements = [s.lower() for s in report] if case == "lower" else list(report)
    if blanks == "drop":
        statements = [s for s in statements if s.strip()]
    if duplicates == "collapse":
        statements = list(dict.fromkeys(statements))
    if order == "ignore":
        statements.sort()
    return tuple(statements)


def report_files(data_path, data_name):
    patterns = {"agh": "*.json", "heedb": "*/*.npy"}
    if data_name not in patterns:
        raise ValueError(f"Unknown dataset: {data_name}")
    root = Path(data_path)
    if not root.is_dir():
        raise FileNotFoundError(f"Data directory does not exist: {root}")
    return root.glob(patterns[data_name])


def read_reports(paths, data_name):
    """Read one file at a time; each yielded triple represents one report pair."""
    if data_name not in ("agh", "heedb"):
        raise ValueError(f"Unknown dataset: {data_name}")
    for path in paths:
        if data_name == "agh":
            for instance in json.loads(Path(path).read_text()):
                yield "agh", instance.get("OriginalDiagnosis"), instance.get("Diagnosis")
        else:
            instance = np.load(path, allow_pickle=True).item()
            physician = instance.get("reports_physician")
            yield "heedb_old", instance.get("reports_software_old"), physician
            yield "heedb_new", instance.get("reports_software_new"), physician
