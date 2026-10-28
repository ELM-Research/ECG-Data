"""Extract annotated HTML to JSON and print exact label agreement."""

import argparse
import json
from collections import Counter
from html.parser import HTMLParser
from itertools import combinations
from pathlib import Path


class Snapshot(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "data":
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, text):
        if self.active:
            self.parts.append(text)


def extract(path):
    page = Snapshot()
    page.feed(path.read_text(encoding="utf-8"))
    if not page.parts:
        raise ValueError("No embedded JSON found in the HTML.")
    data = json.loads("".join(page.parts))
    pairs = data["pairs"]
    order = data["annotation"].get("display_order", list(range(len(pairs))))
    if sorted(order) != list(range(len(pairs))):
        raise ValueError("Invalid annotation display order.")

    records = []
    for number, index in enumerate(order, 1):
        pair = pairs[index]
        annotation = pair.get("annotation", {})
        records.append({
            "display_number": number, "snapshot_index": index,
            "dataset": pair["source"].split("_", 1)[0],
            **{key: pair[key] for key in (
                "source", "file", "pair_index", "status", "input_status", "change",
                "software_report", "physician_report", "added", "deleted", "retained",
            )},
            "model_category": pair["category"], "model_explanation": pair["explanation"],
            "human_category": annotation.get("category"),
            "human_explanation": annotation.get("explanation"),
            "human_updated_at": annotation.get("updated_at"),
            "human_annotation_source": "embedded_annotation" if annotation else None,
        })
    return {
        "metadata": {
            "source_html": str(path.resolve()), "sample": data["annotation"],
            "run": data["run"], "snapshot_exported_at": data["exported_at"],
            "snapshot_annotation_saved_at": data.get("annotation_saved_at"),
            "missing_annotations": "null means unavailable; an empty explanation was saved blank.",
        },
        "records": records,
    }


def print_reports(record):
    for label, key in (("Software", "software_report"), ("Physician", "physician_report")):
        items = record[key]
        text = "Report not saved." if items is None else "\n".join(items) or "Empty report."
        print(f"{label} report:\n{text}\n")


def report(records):
    compared = [r for r in records if r["model_category"] is not None and r["human_category"] is not None]
    counts = Counter((r["model_category"], r["human_category"]) for r in compared)
    aligned = sum(count for (model, human), count in counts.items() if model == human)
    rate = f"{aligned / len(compared):.1%}" if compared else "undefined"
    print(f"Pairs: {len(records)}")
    print(f"Compared: {len(compared)} (both labels present); excluded: {len(records) - len(compared)}")
    print(f"Exact label agreement: {aligned} / {len(compared)} ({rate})")
    print(f"Disagreed: {len(compared) - aligned} / {len(compared)}")
    print("\nLLM -> Annotator counts:")
    for (model, human), count in sorted(counts.items()):
        print(f"  {model} -> {human}: {count}")

    explained = [r for r in records if (r["human_explanation"] or "").strip()]
    print(f"\nAnnotator explanations: {len(explained)}")
    for record in explained:
        print(f"\nPair {record['display_number']}")
        print_reports(record)
        print(f"LLM [{record['model_category']}]:\n{record['model_explanation']}\n")
        print(f"Annotator [{record['human_category']}]:\n{record['human_explanation']}")
        print("=" * 50)


def print_agreement(label, rows, total):
    aligned = sum(len(set(row)) == 1 for row in rows)
    rate = f"{aligned / len(rows):.1%}" if rows else "undefined"
    print(f"{label}: {aligned} / {len(rows)} ({rate}); excluded: {total - len(rows)}")


def report_annotators(results):
    names = [f"Annotator {i}" for i in range(1, len(results) + 1)]
    indexes = []
    records = {}
    for name, result in zip(names, results):
        index = {}
        for record in result["records"]:
            key = (record["source"], record["file"], record["pair_index"])
            if key in index:
                raise ValueError(f"Duplicate pair in {name}: {key}")
            if key in records and any(record[field] != records[key][field] for field in (
                "model_category", "model_explanation", "software_report", "physician_report",
            )):
                raise ValueError(f"Reports or LLM output differ for {key} in {name}.")
            index[key] = record
            records.setdefault(key, record)
        indexes.append(index)

    for name, result in zip(names, results):
        print(f"{name}: {result['metadata']['source_html']}")
    print(f"Pairs: {len(records)} (union of inputs)")
    labels = [
        [index.get(key, {}).get("human_category") for index in indexes] + [record["model_category"]]
        for key, record in records.items()
    ]
    print("\nExact label agreement (only labels present for the comparison):")
    raters = names + ["LLM"]
    for a, b in combinations(range(len(names) + 1), 2):
        rows = [(row[a], row[b]) for row in labels if row[a] is not None and row[b] is not None]
        print_agreement(f"{raters[a]} vs {raters[b]}", rows, len(records))
    humans = [row[:-1] for row in labels if all(label is not None for label in row[:-1])]
    print_agreement("All annotators agree", humans, len(records))

    complete = [tuple(row) for row in labels if all(label is not None for label in row)]
    print(f"\n{' -> '.join(names + ['LLM'])} counts:")
    print(f"Compared: {len(complete)} (all labels present); excluded: {len(records) - len(complete)}")
    for row, count in sorted(Counter(complete).items()):
        print(f"  {' -> '.join(row)}: {count}")

    explained = [key for key in records if any(
        (index.get(key, {}).get("human_explanation") or "").strip() for index in indexes
    )]
    print(f"\nPairs with annotator explanations: {len(explained)}")
    for key in explained:
        record = records[key]
        print(f"\nPair: source={key[0]}, file={key[1]}, pair_index={key[2]}")
        print_reports(record)
        for name, index in zip(names, indexes):
            annotation = index.get(key, {})
            category = annotation.get("human_category") or "missing"
            explanation = annotation.get("human_explanation") or "(no explanation)"
            print(f"{name} [{category}]:\n{explanation}\n")
        print(f"LLM [{record['model_category']}]:\n{record['model_explanation']}")
        print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, nargs="+", required=True,
                        help="One HTML per annotator, in annotator order.")
    parser.add_argument("--output", type=Path,
                        help="JSON path; defaults to the first HTML path with .json or .comparison.json.")
    args = parser.parse_args()
    results = [extract(path) for path in args.html]
    multiple = len(results) > 1
    result = {"annotators": results} if multiple else results[0]
    output = args.output or args.html[0].with_suffix(".comparison.json" if multiple else ".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved: {output}")
    if multiple:
        report_annotators(results)
    else:
        report(result["records"])
