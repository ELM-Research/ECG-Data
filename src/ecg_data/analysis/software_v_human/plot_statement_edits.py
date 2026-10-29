"""Plot statement edit distributions from pairs.jsonl or annotation analysis JSON."""

import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations, islice
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

CATEGORIES = ("preferential", "factual")
COLORS = ("#386b96", "#c17735")
SOURCE_DATASETS = {"agh": "agh", "heedb_old": "heedb"}
DATASET_NAMES = {"agh": "AGH", "heedb": "HEEDB (old software)"}


def pair_id(record):
    return record["source"], record["file"], record["pair_index"]


def load_pairs(path):
    records = {}
    with path.open() as file:
        for line in file:
            if not line.strip():
                continue
            record = json.loads(line)
            if record["source"] not in SOURCE_DATASETS:
                continue
            key = pair_id(record)
            if key in records:
                raise ValueError(f"Duplicate report pair: {key}")
            records[key] = record
    return records.values(), {"LLM": "category"}


def load_annotations(paths):
    results = []
    for path in paths:
        data = json.loads(path.read_text())
        results.extend(data["annotators"] if "annotators" in data else [data])
    records, labels = {}, {"LLM": "model_category"}
    for number, result in enumerate(results, 1):
        name = f"Annotator {number}"
        labels[name] = name
        seen = set()
        for record in result["records"]:
            if record["source"] not in SOURCE_DATASETS:
                continue
            key = pair_id(record)
            if key in seen:
                raise ValueError(f"Duplicate report pair in {name}: {key}")
            seen.add(key)
            saved = records.setdefault(key, dict(record))
            if any(saved[field] != record[field] for field in ("model_category", "added", "deleted")):
                raise ValueError(f"Reports or LLM labels differ between annotators: {key}")
            saved[name] = record.get("human_category")
    return records.values(), labels


def group_statements(records, statements):
    """Group AGH and HEEDB old software pairs by edited statement."""
    groups = defaultdict(lambda: {statement: [] for statement in statements})
    selected = set(statements)
    for record in records:
        dataset = SOURCE_DATASETS[record["source"]]
        group = groups[dataset]
        changed = set(record["added"] or []) | set(record["deleted"] or [])
        for statement in changed & selected:
            group[statement].append(record)
    if not groups:
        raise ValueError("No AGH or HEEDB old software report pairs found.")
    return groups


def print_examples(groups, path, limit=5):
    """Print the first examples of each LLM label for every edited statement."""
    width = 88
    print(f"\nLLM statement examples: {path}")
    print(f"First {limit} per category in JSONL order. Labels apply to whole report pairs.")
    for dataset, statements in groups.items():
        for statement, records in statements.items():
            print(f"\n{'=' * width}\n{DATASET_NAMES[dataset]} | Statement: {statement}\n{'=' * width}")
            counts = Counter(record.get("category") for record in records)
            for category in (*CATEGORIES, "uncertain"):
                total = counts[category]
                print(f"\n{category.upper()} | Showing {min(limit, total)} of {total:,}\n{'-' * width}")
                matches = (record for record in records if record.get("category") == category)
                for number, record in enumerate(islice(matches, limit), 1):
                    print(f"\n  Example {number} | Source: {record['source']} | Pair index: {record['pair_index']}")
                    print(f"  File: {record['file']}")
                    for label, field in (("Software report", "software_report"),
                                         ("Physician report", "physician_report"),
                                         ("Deleted", "deleted"), ("Added", "added")):
                        print(f"\n  {label}:")
                        items = record.get(field) or []
                        if not items:
                            print("    (none)")
                        for item in items:
                            print(fill(item, width, initial_indent="    - ", subsequent_indent="      "))
                    print("\n  LLM explanation:")
                    print(fill(record.get("explanation") or "(unavailable)", width,
                               initial_indent="    ", subsequent_indent="    "))
                    print(f"\n  {'.' * (width - 2)}")


def summarize(records, field, reference):
    counts = Counter(record.get(field) for record in records)
    total = sum(counts[category] for category in CATEGORIES)
    compared = [record for record in records
                if record.get(field) is not None and record.get(reference) is not None]
    return {
        "counts": counts, "total": total, "excluded": len(records) - total,
        "aligned": sum(record[field] == record[reference] for record in compared),
        "compared": len(compared),
    }


def agreement_text(row):
    n, d = row["aligned"], row["compared"]
    return f"{n:,}/{d:,} ({n / d:.0%})" if d else "unavailable"


def plot_statements(groups, labels, output):
    annotated = len(labels) > 1
    model = next(iter(labels.values()))
    comparisons = list(combinations(list(labels)[1:], 2))
    order = {dataset: index for index, dataset in enumerate(DATASET_NAMES)}
    datasets = sorted(groups, key=lambda dataset: (order.get(dataset, len(order)), dataset))
    statements = list(next(iter(groups.values())))
    heights = [max(len(labels) + 0.45 * len(comparisons) + 0.5, (fill(statement, 30).count("\n") + 1) * 0.3)
               for statement in statements]
    width = 3.2 + 4.5 * len(datasets)
    note = ("Exact statements, ignoring case; added/deleted only. Bars use preferential/factual labels; "
            "other or missing labels are excluded (counts shown). Labels describe whole report pairs; groups overlap.")
    if annotated:
        note += (" Agreement = identical labels / pairs with both labels present, including uncertain. "
                 "Percentages describe the annotation sample.")
    note = fill(note, int(width * 13))
    footer = 0.3 + 0.18 * (note.count("\n") + 1)
    height = 1.3 + 0.7 * sum(heights) + footer
    fig, axes = plt.subplots(1, len(datasets), figsize=(width, height), squeeze=False)
    fig.subplots_adjust(left=3 / width, right=1 - 0.25 / width,
                        top=1 - 1.3 / height, bottom=footer / height, wspace=0.15)
    title = "Annotation categories and agreement" if annotated else "LLM edit categories"
    fig.text(0.25 / width, 1 - 0.2 / height, title + " by statement",
             fontsize=17, fontweight="bold", va="top", color="#253449")
    fig.legend(handles=[Patch(color=color, label=category.title()) for category, color in zip(CATEGORIES, COLORS)],
               loc="upper left", bbox_to_anchor=(0.25 / width, 1 - 0.55 / height), ncol=2, frameon=False)
    for ax, dataset in zip(axes[0], datasets):
        ax.set(xlim=(0, 100), ylim=(sum(heights), 0))
        ax.set_axis_off()
        ax.set_title(DATASET_NAMES.get(dataset, dataset), loc="left", fontsize=12, fontweight="bold", pad=14)
        top = 0
        for statement, group_height in zip(statements, heights):
            records = groups[dataset][statement]
            if ax is axes[0][0]:
                ax.text(-0.05, top + (group_height - 0.5) / 2, fill(statement, 30),
                        transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=11)
            for index, (name, field) in enumerate(labels.items()):
                row = summarize(records, field, model)
                y = top + index
                ax.text(0, y, name, fontsize=9, va="top", color="#64748b")
                detail = f"n={row['total']:,}"
                if field != model:
                    detail = f"LLM agreement {agreement_text(row)}"
                ax.text(100, y, detail, ha="right", va="top", fontsize=8, color="#64748b")
                left = 0
                for category, color in zip(CATEGORIES, COLORS):
                    percent = 100 * row["counts"][category] / row["total"] if row["total"] else 0
                    ax.barh(y + 0.36, percent, left=left, height=0.3, color=color, edgecolor="white")
                    if percent >= 14:
                        ax.text(left + percent / 2, y + 0.36, f"{percent:.0f}%",
                                ha="center", va="center", color="white", fontsize=9)
                    left += percent
                counts = " · ".join(f"{row['counts'][category]:,} {category}" for category in CATEGORIES)
                if row["excluded"]:
                    counts += f" · {row['excluded']:,} excluded"
                if not row["total"]:
                    ax.text(0, y + 0.36, "No preferential/factual edits", va="center", fontsize=9, color="#64748b")
                ax.text(0, y + 0.6, fill(counts, 54), va="top", fontsize=8, color="#475569")
            for index, (first, second) in enumerate(comparisons):
                row = summarize(records, labels[first], labels[second])
                y = top + len(labels) + 0.1 + 0.45 * index
                ax.text(0, y, f"{first} vs {second}", va="top", fontsize=8, color="#64748b")
                ax.text(100, y, f"Agreement {agreement_text(row)}",
                        ha="right", va="top", fontsize=8, color="#64748b")
            top += group_height
            ax.axhline(top - 0.2, color="#e2e8f0", linewidth=0.7)
    fig.text(0.25 / width, 0.15 / height, note, va="bottom", fontsize=9, color="#64748b")
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)
    print(f"Saved: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, nargs="+", help="One dataset per JSONL; save each figure beside its input.")
    parser.add_argument("--annotations", type=Path, nargs="+",
                        help="Analysis JSONs in annotator order; save the combined figure beside the first.")
    parser.add_argument("--statements", nargs="+", required=True, help="Exact list items, ignoring case.")
    parser.add_argument("--examples", type=int, default=5,
                        help="Printed examples per statement and LLM category for each JSONL (default: 5).")
    args = parser.parse_args()
    if not (args.pairs or args.annotations):
        parser.error("Provide --pairs, --annotations, or both.")
    if args.examples < 1:
        parser.error("--examples must be positive.")
    statements = list(dict.fromkeys(statement.lower() for statement in args.statements))
    if any(not statement.strip() for statement in statements):
        parser.error("Statements must be nonblank.")
    for path in args.pairs or []:
        records, labels = load_pairs(path)
        groups = group_statements(records, statements)
        if len(groups) != 1:
            raise ValueError(f"Expected one dataset in {path}.")
        plot_statements(groups, labels, path.with_name("llm_statements.png"))
        print_examples(groups, path, args.examples)
    if args.annotations:
        records, labels = load_annotations(args.annotations)
        plot_statements(group_statements(records, statements), labels,
                        args.annotations[0].with_name("annotation_statements.png"))
