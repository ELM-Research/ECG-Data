"""Extract annotated HTML to JSON and print exact label agreement."""

import argparse
import json
from collections import Counter
from html.parser import HTMLParser
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
        for label, key in (("Software", "software_report"), ("Physician", "physician_report")):
            items = record[key]
            text = "Report not saved." if items is None else "\n".join(items) or "Empty report."
            print(f"{label} report:\n{text}")
        print(f"LLM [{record['model_category']}]:\n{record['model_explanation']}")
        print(f"Annotator [{record['human_category']}]:\n{record['human_explanation']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="JSON path; defaults to the HTML path with a .json suffix.")
    args = parser.parse_args()
    result = extract(args.html)
    output = args.output or args.html.with_suffix(".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved: {output}")
    report(result["records"])
