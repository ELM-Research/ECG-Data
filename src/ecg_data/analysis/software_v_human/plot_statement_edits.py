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

from ecg_data.analysis.software_v_human.terms import TERMS

CATEGORIES = ("preferential", "factual")
COLORS = ("#386b96", "#c17735")
SOURCE_DATASETS = {"agh": "agh", "heedb_old": "heedb"}
DATASET_NAMES = {"agh": "AGH", "heedb": "HEEDB (old software)"}


def load_pairs(path):
    with path.open() as file:
        records = [json.loads(line) for line in file if line.strip()]
    return records, {"LLM": "category"}


def load_annotations(paths):
    results = []
    for path in paths:
        data = json.loads(path.read_text())
        results.extend(data["annotators"] if "annotators" in data else [data])
    records, labels = {}, {"LLM": "model_category"}
    for number, result in enumerate(results, 1):
        name = f"Annotator {number}"
        labels[name] = name
        for record in result["records"]:
            key = record["source"], record["file"], record["pair_index"]
            saved = records.setdefault(key, dict(record))
            saved[name] = record.get("human_category")
    return records.values(), labels


def group_statements(records, statements):
    """Group AGH and HEEDB old software pairs by edited statement."""
    groups = defaultdict(lambda: {statement: [] for statement in statements})
    selected = set(statements)
    for record in records:
        if record["source"] not in SOURCE_DATASETS:
            continue
        dataset = SOURCE_DATASETS[record["source"]]
        group = groups[dataset]
        changed = set(record["added"] or []) | set(record["deleted"] or [])
        for statement in changed & selected:
            group[statement].append(record)
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


def agreement_text(records, field, reference):
    compared = [record for record in records
                if record.get(field) is not None and record.get(reference) is not None]
    if not compared:
        return "unavailable"
    aligned = sum(record[field] == record[reference] for record in compared)
    return f"{aligned:,}/{len(compared):,} ({aligned / len(compared):.0%})"


def plot_statement(ax, records, labels, comparisons):
    model = next(iter(labels.values()))
    height = len(labels) + 0.45 * len(comparisons) + 0.5
    ax.set(xlim=(0, 100), ylim=(height, 0))
    ax.set_axis_off()
    for y, (name, field) in enumerate(labels.items()):
        counts = Counter(record.get(field) for record in records)
        total = sum(counts[category] for category in CATEGORIES)
        detail = f"n={total:,}" if field == model else f"LLM agreement {agreement_text(records, field, model)}"
        ax.text(0, y, name, fontsize=9, va="top", color="#64748b")
        ax.text(100, y, detail, ha="right", va="top", fontsize=8, color="#64748b")
        left = 0
        for category, color in zip(CATEGORIES, COLORS):
            percent = 100 * counts[category] / total if total else 0
            ax.barh(y + 0.36, percent, left=left, height=0.3, color=color, edgecolor="white")
            if percent >= 14:
                ax.text(left + percent / 2, y + 0.36, f"{percent:.0f}%",
                        ha="center", va="center", color="white", fontsize=9)
            left += percent
        detail = " · ".join(f"{counts[category]:,} {category}" for category in CATEGORIES)
        if len(records) > total:
            detail += f" · {len(records) - total:,} excluded"
        if not total:
            ax.text(0, y + 0.36, "No preferential/factual edits", va="center", fontsize=9, color="#64748b")
        ax.text(0, y + 0.6, fill(detail, 54), va="top", fontsize=8, color="#475569")
    for index, (first, second) in enumerate(comparisons):
        y = len(labels) + 0.1 + 0.45 * index
        ax.text(0, y, f"{first} vs {second}", va="top", fontsize=8, color="#64748b")
        ax.text(100, y, f"Agreement {agreement_text(records, labels[first], labels[second])}",
                ha="right", va="top", fontsize=8, color="#64748b")
    ax.axhline(height - 0.2, color="#e2e8f0", linewidth=0.7)


def plot_statements(groups, labels, output, category=""):
    datasets = [dataset for dataset in DATASET_NAMES if dataset in groups]
    statements = list(next(iter(groups.values())))
    comparisons = list(combinations(list(labels)[1:], 2))
    row_height = 0.7 * (len(labels) + 0.45 * len(comparisons) + 0.5)
    width = 3.2 + 4.5 * len(datasets)
    note = ("Exact statements, ignoring case; added/deleted only. Bars use preferential/factual labels; "
            "other or missing labels are excluded (counts shown). Labels describe whole report pairs; groups overlap.")
    if len(labels) > 1:
        note += (" Agreement = identical labels / pairs with both labels present, including uncertain. "
                 "Percentages describe the annotation sample.")
    note = fill(note, int(width * 13))
    footer = 0.3 + 0.18 * (note.count("\n") + 1)
    height = 1.3 + row_height * len(statements) + footer
    fig, axes = plt.subplots(len(statements), len(datasets), figsize=(width, height), squeeze=False)
    fig.subplots_adjust(left=3 / width, right=1 - 0.25 / width,
                        top=1 - 1.3 / height, bottom=footer / height, wspace=0.15, hspace=0)
    title = "Annotation categories and agreement" if len(labels) > 1 else "LLM edit categories"
    title += f": {category}" if category else " by statement"
    fig.text(0.25 / width, 1 - 0.2 / height, title,
             fontsize=17, fontweight="bold", va="top", color="#253449")
    fig.legend(handles=[Patch(color=color, label=category.title()) for category, color in zip(CATEGORIES, COLORS)],
               loc="upper left", bbox_to_anchor=(0.25 / width, 1 - 0.55 / height), ncol=2, frameon=False)
    for column, dataset in enumerate(datasets):
        ax = axes[0, column]
        ax.set_title(DATASET_NAMES[dataset], loc="left", fontsize=12, fontweight="bold", pad=14)
        for row, statement in enumerate(statements):
            ax = axes[row, column]
            plot_statement(ax, groups[dataset][statement], labels, comparisons)
            if column == 0:
                ax.text(-0.05, 0.5, fill(statement, 30), transform=ax.transAxes,
                        ha="right", va="center", fontsize=11)
    fig.text(0.25 / width, 0.15 / height, note, va="bottom", fontsize=9, color="#64748b")
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)
    print(f"Saved: {output}")


def save_plots(groups, labels, output, selections):
    for category, statements in selections.items():
        selected = {dataset: {statement: group[statement] for statement in statements}
                    for dataset, group in groups.items()}
        suffix = category.lower().replace(" / ", "_").replace(" ", "_")
        path = output.with_stem(f"{output.stem}_{suffix}") if suffix else output
        plot_statements(selected, labels, path, category)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, nargs="+", help="One dataset per JSONL; save each figure beside its input.")
    parser.add_argument("--annotations", type=Path, nargs="+",
                        help="Analysis JSONs in annotator order; save the combined figure beside the first.")
    parser.add_argument("--statements", nargs="+",
                        help="Exact list items, ignoring case. Omit to plot all terms.py terms, one figure per category.")
    parser.add_argument("--examples", type=int, default=5,
                        help="Printed examples per statement and LLM category for each JSONL (default: 5).")
    args = parser.parse_args()
    if not (args.pairs or args.annotations):
        parser.error("Provide --pairs, --annotations, or both.")
    selections = TERMS
    if args.statements:
        selections = {"": list(dict.fromkeys(statement.lower() for statement in args.statements))}
    statements = [statement for selected in selections.values() for statement in selected]
    for path in args.pairs or []:
        records, labels = load_pairs(path)
        groups = group_statements(records, statements)
        save_plots(groups, labels, path.with_name("llm_statements.png"), selections)
        print_examples(groups, path, args.examples)
    if args.annotations:
        records, labels = load_annotations(args.annotations)
        save_plots(group_statements(records, statements), labels,
                   args.annotations[0].with_name("annotation_statements.png"), selections)
