"""Optional removal records for inspecting software/physician report pairs."""

import json

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
    name, cohort, matches = result
    if name != comparison or cohort != "modified":
        return result, None

    removed = [term for _, term, before, after in matches if term in terms and before and not after]
    if not removed:
        return result, None

    _, software, physician = report
    return result, {"terms": removed, "software": software, "physician": physician}


def save_examples(reports, path):
    """Stream records to disk while forwarding normal analysis results."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as file:
        for result, record in reports:
            if record is not None:
                file.write(json.dumps(record) + "\n")
            yield result


def print_examples(path, terms, limit):
    terms = validate_terms(terms)
    if limit < 1:
        raise ValueError("limit must be at least 1.")
    examples = {term: [] for term in terms}
    with path.open() as file:
        for line in file:
            record = json.loads(line)
            for term in record["terms"]:
                if term in examples and len(examples[term]) < limit:
                    examples[term].append(record)
            if all(len(records) == limit for records in examples.values()):
                break

    for term, records in examples.items():
        print(f"\n{term}")
        if not records:
            print("  No saved removal examples.")
        for index, record in enumerate(records, 1):
            print(f"  Pair {index}")
            for field in ("software", "physician"):
                text = record[field]
                if isinstance(text, list):
                    text = " ".join(text)
                print(f"  {field.capitalize()}: {text}")
