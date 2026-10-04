"""Optional removal records for inspecting software/physician report pairs."""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path

from ecg_data.analysis.software_v_human.terms import TERMS


def validate_terms(terms):
    terms = tuple(dict.fromkeys(" ".join(term.lower().split()) for term in terms))
    known = {term for category in TERMS.values() for term in category}
    unknown = set(terms) - known
    if unknown or not terms:
        raise ValueError(f"Provide terms from TERMS; unknown terms: {sorted(unknown)}")
    return terms


def process_with_examples(report, *, processor, terms, comparison):
    result = processor(report)
    name, matching, cohort, matches = result
    if name != comparison or cohort != "modified":
        return result, None

    removed = [term for _, term, before, after in matches if term in terms and before and not after]
    if not removed:
        return result, None

    _, _, software, physician = report
    return result, {"terms": removed, "software": software, "physician": physician}


def save_examples(reports, path):
    """Stream records to disk while forwarding normal analysis results."""
    with ExitStack() as stack:
        files = {}
        for result, record in reports:
            matching = result[1]
            if matching not in files:
                output = path / matching / "removed_examples.jsonl"
                output.parent.mkdir(parents=True, exist_ok=True)
                files[matching] = stack.enter_context(output.open("w"))
            if record is not None:
                files[matching].write(json.dumps(record) + "\n")
            yield result


def print_examples(path, limit):
    if limit < 1:
        raise ValueError("limit must be at least 1.")
    examples = {}
    with path.open() as file:
        for line in file:
            record = json.loads(line)
            for term in record["terms"]:
                records = examples.setdefault(term, [])
                if len(records) < limit:
                    records.append(record)

    if not examples:
        print("No saved removal examples.")
        return

    for term, records in examples.items():
        print(f"\n{term}")
        for index, record in enumerate(records, 1):
            print(f"  Pair {index}")
            for field in ("software", "physician"):
                text = record[field]
                if isinstance(text, list):
                    text = " ".join(text)
                print(f"  {field.capitalize()}: {text}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Saved JSONL file or its comparison directory.")
    parser.add_argument("--limit", type=int, default=3, help="Maximum pairs per term (default: 3).")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1.")
    path = args.path / "removed_examples.jsonl" if args.path.is_dir() else args.path
    if not path.is_file():
        parser.error(f"No saved records found at {path}.")
    print_examples(path, args.limit)
