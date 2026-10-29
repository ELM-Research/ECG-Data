"""Plot statement edit distributions from pairs.jsonl or annotation analysis JSON."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from ecg_data.analysis.software_v_human.plot_edits import SOURCE_NAMES

CATEGORIES = ("preferential", "factual")
COLORS = ("#386b96", "#c17735")


def pair_id(record):
    return record["source"], record["file"], record["pair_index"]


def load_pairs(paths):
    records = {}
    for path in paths:
        with path.open() as file:
            for line in file:
                if not line.strip():
                    continue
                record = json.loads(line)
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
    groups = defaultdict(lambda: {statement: [] for statement in statements})
    selected = set(statements)
    for record in records:
        source = groups[record["source"]]
        changed = set(record["added"] or []) | set(record["deleted"] or [])
        for statement in changed & selected:
            source[statement].append(record)
    if not groups:
        raise ValueError("No report pairs found.")
    return groups


def summarize(records, field, model):
    counts = Counter(record.get(field) for record in records)
    total = sum(counts[category] for category in CATEGORIES)
    compared = [record for record in records
                if record.get(field) is not None and record.get(model) is not None]
    return {
        "counts": counts, "total": total, "excluded": len(records) - total,
        "aligned": sum(record[field] == record[model] for record in compared),
        "compared": len(compared),
    }


def plot_statements(groups, labels, output):
    annotated = len(labels) > 1
    model = next(iter(labels.values()))
    order = {source: index for index, source in enumerate(SOURCE_NAMES)}
    sources = sorted(groups, key=lambda source: (order.get(source, len(order)), source))
    statements = list(next(iter(groups.values())))
    heights = [max(len(labels) + 0.5, (fill(statement, 30).count("\n") + 1) * 0.3)
               for statement in statements]
    width = 3.2 + 4.5 * len(sources)
    note = ("Exact statements, ignoring case; added/deleted only. Bars use preferential/factual labels; "
            "other or missing labels are excluded (counts shown). Labels describe whole report pairs; groups overlap.")
    if annotated:
        note += (" Agreement = identical labels / pairs with both labels present, including uncertain. "
                 "Percentages describe the annotation sample.")
    note = fill(note, int(width * 13))
    footer = 0.3 + 0.18 * (note.count("\n") + 1)
    height = 1.3 + 0.7 * sum(heights) + footer
    fig, axes = plt.subplots(1, len(sources), figsize=(width, height), squeeze=False)
    fig.subplots_adjust(left=3 / width, right=1 - 0.25 / width,
                        top=1 - 1.3 / height, bottom=footer / height, wspace=0.15)
    title = "Annotation categories and agreement" if annotated else "LLM edit categories"
    fig.text(0.25 / width, 1 - 0.2 / height, title + " by statement",
             fontsize=17, fontweight="bold", va="top", color="#253449")
    fig.legend(handles=[Patch(color=color, label=category.title()) for category, color in zip(CATEGORIES, COLORS)],
               loc="upper left", bbox_to_anchor=(0.25 / width, 1 - 0.55 / height), ncol=2, frameon=False)
    for ax, source in zip(axes[0], sources):
        ax.set(xlim=(0, 100), ylim=(sum(heights), 0))
        ax.set_axis_off()
        ax.set_title(SOURCE_NAMES.get(source, source), loc="left", fontsize=12, fontweight="bold", pad=14)
        top = 0
        for statement, group_height in zip(statements, heights):
            records = groups[source][statement]
            if ax is axes[0][0]:
                ax.text(-0.05, top + (group_height - 0.5) / 2, fill(statement, 30),
                        transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=11)
            for index, (name, field) in enumerate(labels.items()):
                row = summarize(records, field, model)
                y = top + index
                ax.text(0, y, name, fontsize=9, va="top", color="#64748b")
                detail = f"n={row['total']:,}"
                if field != model:
                    n, d = row["aligned"], row["compared"]
                    detail = f"Agreement {n:,}/{d:,} ({n / d:.0%})" if d else "Agreement unavailable"
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
            top += group_height
            ax.axhline(top - 0.2, color="#e2e8f0", linewidth=0.7)
    fig.text(0.25 / width, 0.15 / height, note, va="bottom", fontsize=9, color="#64748b")
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)
    print(f"Saved: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, nargs="+", help="Saved pairs.jsonl files.")
    parser.add_argument("--annotations", type=Path, nargs="+", help="Analysis JSON files, in annotator order.")
    parser.add_argument("--statements", nargs="+", required=True, help="Exact list items, ignoring case.")
    parser.add_argument("--output", type=Path, required=True, help="Figure directory.")
    args = parser.parse_args()
    if not (args.pairs or args.annotations):
        parser.error("Provide --pairs, --annotations, or both.")
    statements = list(dict.fromkeys(statement.lower() for statement in args.statements))
    if any(not statement.strip() for statement in statements):
        parser.error("Statements must be nonblank.")
    args.output.mkdir(parents=True, exist_ok=True)
    for paths, loader, filename in (
        (args.pairs, load_pairs, "llm_statements.png"),
        (args.annotations, load_annotations, "annotation_statements.png"),
    ):
        if paths:
            records, labels = loader(paths)
            plot_statements(group_statements(records, statements), labels, args.output / filename)
