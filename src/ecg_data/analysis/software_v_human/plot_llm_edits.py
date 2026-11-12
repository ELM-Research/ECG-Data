"""Plot LLM report edits and statement groups in one pass over saved pairs."""

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from itertools import combinations
from os.path import relpath
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter
from tqdm import tqdm

from ecg_data.analysis.software_v_human.llm_edits import CATEGORIES, SOURCES, STATUSES, _count, summarize
from ecg_data.analysis.software_v_human.terms import TERMS
from ecg_data.preprocess.config.load import load_config

SOURCE_NAMES = {"agh": "AGH", "heedb_old": "HEEDB (old software)"}
CHANGE_NAMES = {
    "unchanged": "Unchanged", "added_only": "Physician added only",
    "deleted_only": "Physician deleted only", "both": "Physician added and deleted",
}
INPUT_NAMES = {
    "software_empty": "Software empty only", "physician_empty": "Physician empty only",
    "both_empty": "Both reports empty", "missing": "Missing report", "invalid": "Malformed report",
}
RED, DARK_RED, BLACK, GRAY = "#B12929", "#8C1A11", "#000000", "#636466"
LIGHT_RED, GRID = "#EA4238", "#E8E8E8"
CATEGORY_COLORS = {"preferential": DARK_RED, "factual": LIGHT_RED, "uncertain": GRAY}
SOURCE_COLORS = {"agh": RED, "heedb_old": GRAY}
STATEMENT_CATEGORIES = ("preferential", "factual")
STYLE = {
    "font.family": "DejaVu Sans", "font.size": 12, "axes.titlesize": 16,
    "axes.labelsize": 12, "xtick.labelsize": 11, "ytick.labelsize": 11,
    "legend.fontsize": 11, "text.color": BLACK, "axes.labelcolor": BLACK,
    "axes.spines.top": False, "axes.spines.right": False,
    "savefig.dpi": 200, "figure.facecolor": "white", "axes.facecolor": "white",
}


@dataclass
class StatementCounts:
    total: int = 0
    labels: dict = field(default_factory=lambda: defaultdict(Counter))
    agreements: dict = field(default_factory=dict)
    examples: dict = field(default_factory=lambda: defaultdict(list))


def count_statements(record, groups, labels, statements, examples=0):
    """Count each pair once per changed statement; retained statements do not qualify."""
    source = record["source"]
    if source not in SOURCE_NAMES:
        return
    group = groups.setdefault(source, {})
    changed = {statement.lower() for key in ("added", "deleted") for statement in record.get(key) or []}
    for statement in changed & statements:
        if statement not in group:
            group[statement] = StatementCounts()
        current = group[statement]
        current.total += 1
        for key in labels.values():
            current.labels[key][record.get(key)] += 1
        for first, second in combinations(labels, 2):
            a, b = record.get(labels[first]), record.get(labels[second])
            if a is None or b is None:
                continue
            agreement = current.agreements.setdefault((first, second), [0, 0])
            agreement[0] += a == b
            agreement[1] += 1
        category = record.get(next(iter(labels.values())))
        if examples and category in CATEGORIES and len(current.examples[category]) < examples:
            current.examples[category].append(record)


def read_pairs(path, consume, *, sources=SOURCE_NAMES):
    """Read a fixed file snapshot; ignore an unfinished final record, as the run writer does."""
    incomplete, ignored = False, 0
    with path.open("rb") as file:
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        with tqdm(total=size, desc=f"Reading {path.parent.name}", unit="B", unit_scale=True) as progress:
            number = 0
            while file.tell() < size:
                line = file.readline(size - file.tell())
                progress.update(len(line))
                number += 1
                if not line.endswith(b"\n"):
                    incomplete = True
                    break
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except ValueError as error:
                    raise ValueError(f"Invalid JSON in {path}:{number}") from error
                if record["source"] not in sources:
                    ignored += 1
                    continue
                consume(record)
    if ignored:
        tqdm.write(f"{path}: excluded {ignored:,} pairs outside the AGH / old-HEEDB study.")
    if incomplete:
        tqdm.write(f"{path}: ignored the unfinished final record.")
    return incomplete


def _snapshot(root, *, consume=None, keep_pairs=True, path=None, totals=None):
    root = Path(root)
    path = path or root / "pairs.jsonl"
    metadata = root / "run.json"
    run = json.loads(metadata.read_text()) if metadata.exists() else {
        "empty_reports": "unspecified", "undefined_ratio": None,
    }
    pairs, counts = [], {}

    def collect(record):
        _count(counts, record)
        if keep_pairs:
            pairs.append(record)
        if consume is not None:
            consume(record)

    incomplete = read_pairs(path, collect, sources=SOURCES.get(run.get("data_name"), SOURCE_NAMES))
    if totals is not None:
        for source, current in counts.items():
            total = totals.setdefault(source, {key: Counter() for key in current})
            for key, counter in current.items():
                total[key].update(counter)
    return {
        "run": run, "pairs": pairs, "incomplete_tail": incomplete,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "summary": summarize(counts, empty_reports=run["empty_reports"],
                             undefined_ratio=run["undefined_ratio"],
                             **{key: run.get(key, ()) for key in ("truncate", "remove", "skip")}),
        "names": {"source": SOURCE_NAMES, "change": CHANGE_NAMES, "input": INPUT_NAMES},
    }


def load_annotations(paths):
    results = []
    for path in tqdm(paths, desc="Reading annotations", unit="file"):
        data = json.loads(path.read_text())
        results.extend(data["annotators"] if "annotators" in data else [data])
    records, labels = {}, {"LLM": "model_category"}
    for number, result in enumerate(results, 1):
        name = f"Annotator {number}"
        labels[name] = name
        seen = set()
        for record in result["records"]:
            if record["source"] not in SOURCE_NAMES:
                continue
            key = record["source"], record["file"], record["pair_index"]
            if key in seen:
                raise ValueError(f"Duplicate pair in {name}: {key}")
            seen.add(key)
            saved = records.setdefault(key, dict(record))
            if any(saved.get(field) != record.get(field) for field in (
                "model_category", "software_report", "physician_report", "added", "deleted",
            )):
                raise ValueError(f"Reports or LLM labels differ for {key} in {name}.")
            saved[name] = record.get("human_category")
    return records.values(), labels


def percentage(n, d):
    if not d:
        return "N/A"
    if 0 < n / d < 0.001:
        return "<0.1%"
    if 0.999 < n / d < 1:
        return ">99.9%"
    return f"{n / d:.1%}"


def clean_ax(ax, axis="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.grid(axis=axis, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, pad=8)


def save_figure(fig, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def plot_rates(results, rows, values, *, title, denominator, output):
    """Ordinary grouped bars; every percentage keeps its numerator and denominator."""
    sources = list(results)
    fig, ax = plt.subplots(figsize=(max(7, len(rows) * 2.3), 5.3))
    width = 0.68 / len(sources)
    single_rate = len(rows) == 1
    for index, source in enumerate(sources):
        for position, (key, _) in enumerate(rows):
            n, d = values(results[source], key)
            x = index if single_rate else position + (index - (len(sources) - 1) / 2) * width
            rate = 100 * n / d if d else 0
            ax.bar(x, rate, 0.55 if single_rate else width * 0.9, color=SOURCE_COLORS[source], edgecolor="white",
                   label=SOURCE_NAMES[source] if position == 0 else None)
            ax.text(x, rate + 2, percentage(n, d), ha="center", va="bottom", fontweight="bold")
            ax.text(x, rate + 8, f"{n:,} / {d:,}", ha="center", va="bottom", fontsize=9, color=GRAY)
    tick_labels = [SOURCE_NAMES[source] for source in sources] if single_rate else [fill(label, 23) for _, label in rows]
    ax.set(ylim=(0, 118), ylabel="Report pairs (%)", xticks=range(len(tick_labels)), xticklabels=tick_labels,
           xlim=(-0.65, len(tick_labels) - 0.35))
    ax.set_yticks(range(0, 101, 20))
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.set_title(title, loc="left", fontweight="bold", pad=42)
    ax.text(0, 1.04, fill(denominator, 100), transform=ax.transAxes, fontsize=10, color=GRAY, va="bottom")
    if len(sources) > 1 and not single_rate:
        ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=len(sources))
    elif not single_rate:
        ax.set_xlabel(SOURCE_NAMES[sources[0]], labelpad=16)
    clean_ax(ax)
    save_figure(fig, output)


def plot_distribution(results, rows, denominator, *, title, note, output):
    """A 100% stack per dataset; the same label always has the same color."""
    fig, ax = plt.subplots(figsize=(max(7, 3 * len(results)), 5.4))
    for position, (source, metrics) in enumerate(results.items()):
        total = metrics[denominator]
        bottom = 0
        for key, label, color, field in rows:
            count = metrics[field].get(key, 0)
            height = 100 * count / total if total else 0
            ax.bar(position, height, 0.58, bottom=bottom, color=color,
                   edgecolor="white", linewidth=1.1)
            if height >= 8:
                ax.text(position, bottom + height / 2, percentage(count, total),
                        ha="center", va="center", color="white", fontweight="bold")
            bottom += height
        ax.text(position, 103, f"n={total:,}" if total else "No eligible pairs",
                ha="center", va="bottom", fontsize=11, color=GRAY)
    ax.set(ylim=(0, 112), ylabel="Report pairs (%)", xticks=range(len(results)),
           xticklabels=[SOURCE_NAMES[source] for source in results])
    ax.set_yticks(range(0, 101, 20))
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.set_title(title, loc="left", fontweight="bold", pad=42)
    ax.text(0, 1.04, fill(note, 100), transform=ax.transAxes, fontsize=10, color=GRAY, va="bottom")
    ax.legend(handles=[Patch(facecolor=color, label=label) for _, label, color, _ in rows],
              loc="upper center", bbox_to_anchor=(0.5, -0.15),
              ncol=min(2, len(rows)), frameon=False)
    clean_ax(ax)
    save_figure(fig, output)


def main_plots(results, output):
    jobs = [partial(
        plot_rates, results, [("edited", "Any physician edit")],
        lambda metrics, _: (metrics["edited_reports"], metrics["included_reports"]),
        title="Physician edit rate", denominator="All included report pairs; any statement added or deleted.",
        output=output / "01_edit_rate.png",
    ), partial(
        plot_distribution, results,
        [(key, label, color, "report_counts") for (key, label), color in zip(
            CHANGE_NAMES.items(), (GRAY, LIGHT_RED, DARK_RED, BLACK))],
        "included_reports", title="Types of report changes", note="All included report pairs.",
        output=output / "02_change_types.png",
    ), partial(
        plot_rates, results, list(INPUT_NAMES.items()),
        lambda metrics, key: (metrics["input_status_counts"][key], metrics["input_reports"]),
        title="Input quality", denominator="All saved input pairs, before exclusions; issues do not overlap.",
        output=output / "03_input_quality.png",
    ), partial(
        plot_distribution, results,
        [(key, key.title(), CATEGORY_COLORS[key], "category_counts") for key in CATEGORIES],
        "classified_reports", title="LLM edit categories",
        note="Classified changed pairs. Factual = clinical meaning changed; correction is not verified.",
        output=output / "04_category_rates.png",
    ), partial(
        plot_distribution, results,
        [(key, key.title(), color, "status_counts") for key, color in zip(
            STATUSES, (BLACK, GRAY, RED, LIGHT_RED))],
        "input_reports", title="Processing outcomes", note="All saved input pairs; unchanged pairs need no LLM call.",
        output=output / "05_processing_status.png",
    ), partial(
        plot_rates, results, [("classified_reports", "Successfully classified"), ("skipped_reports", "Skipped")],
        lambda metrics, key: (metrics[key], metrics["edited_reports"]),
        title="Classification coverage", denominator="All included changed pairs, including skipped pairs.",
        output=output / "06_classification_coverage.png",
    )]
    attempts = sorted({number for metrics in results.values() for number in metrics["attempt_counts"]})
    if attempts:
        jobs.append(partial(
            plot_rates, results, [(number, f"{number} attempt{'s' if number != 1 else ''}") for number in attempts],
            lambda metrics, key: (metrics["attempt_counts"].get(key, 0), metrics["edited_reports"]),
            title="LLM attempts per changed pair", denominator="All included changed pairs, including skipped pairs.",
            output=output / "07_attempts.png",
        ))
    return jobs


def _plot_llm(results, output):
    """Keep the annotation export's plotting entry point."""
    with plt.rc_context(STYLE):
        for job in tqdm(main_plots(results, Path(output)), desc="Plotting main figures", unit="figure"):
            job()


def plot_statements(groups, labels, statements, output, category=""):
    sources = [source for source in SOURCE_NAMES if source in groups]
    comparisons = list(combinations(labels, 2))
    row_height = 0.58 * len(labels) + 0.24 * len(comparisons) + 0.25
    label_width, column_width = 3.3, 4.6
    width = label_width + column_width * len(sources) + 0.4
    note = ("Exact added/deleted statements, ignoring case. Bars use preferential/factual pairs only; "
            "other or missing labels are excluded. Labels describe whole report pairs; groups overlap.")
    if comparisons:
        note += " Agreement includes uncertain labels and excludes missing labels. Annotation sample only."
    note = fill(note, int(width * 12))
    footer = 0.45 + 0.15 * (note.count("\n") + 1)
    height = 1.45 + row_height * len(statements) + footer
    fig, axes = plt.subplots(len(statements), len(sources), figsize=(width, height), squeeze=False)
    fig.subplots_adjust(left=label_width / width, right=1 - 0.9 / width,
                        top=1 - 1.45 / height, bottom=footer / height, wspace=0.5, hspace=0.22)
    title = "Annotation categories and agreement" if comparisons else "LLM edit categories by statement"
    fig.text(0.25 / width, 1 - 0.2 / height, title, fontsize=17, fontweight="bold", va="top")
    if category:
        fig.text(0.25 / width, 1 - 0.55 / height, category, fontsize=12, color=GRAY, va="top")
    fig.legend(handles=[Patch(color=CATEGORY_COLORS[key], label=key.title()) for key in STATEMENT_CATEGORIES],
               loc="upper left", bbox_to_anchor=(0.15 / width, 1 - 0.8 / height), ncol=2, frameon=False)
    for column, source in enumerate(sources):
        axes[0, column].set_title(SOURCE_NAMES[source], loc="left", fontsize=12, fontweight="bold", pad=17)
        for row, statement in enumerate(statements):
            ax = axes[row, column]
            current = groups[source].get(statement, StatementCounts())
            ax.set(xlim=(0, 100), ylim=(len(labels) + 0.5 * len(comparisons) - 0.35, -0.6))
            ax.set_xticks((0, 50, 100))
            ax.xaxis.set_major_formatter(PercentFormatter())
            ax.set_yticks([])
            ax.tick_params(axis="x", labelsize=8, labelbottom=row == len(statements) - 1)
            clean_ax(ax, "x")
            ax.spines[["left", "bottom"]].set_visible(False)
            if column == 0:
                fig.text(0.25 / width, (ax.get_position().y0 + ax.get_position().y1) / 2,
                         fill(statement, 30), fontsize=11, va="center")
            for y, (name, key) in enumerate(labels.items()):
                counts = current.labels[key]
                total = sum(counts[category] for category in STATEMENT_CATEGORIES)
                left = 0
                for label in STATEMENT_CATEGORIES:
                    percent = 100 * counts[label] / total if total else 0
                    ax.barh(y, percent, left=left, height=0.5, color=CATEGORY_COLORS[label], edgecolor="white")
                    if percent >= 12:
                        ax.text(left + percent / 2, y, f"{percent:.0f}%", ha="center", va="center",
                                color="white", fontsize=10, fontweight="bold")
                    left += percent
                if len(labels) > 1:
                    ax.text(-0.03, y, name, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=8)
                excluded = current.total - total
                detail = f"n={total:,}" + (f"\n{excluded:,} excluded" if excluded else "")
                ax.text(1.03, y, detail, transform=ax.get_yaxis_transform(), va="center", fontsize=8, color=GRAY)
                if not total:
                    ax.text(1, y, "No eligible edits", va="center", fontsize=9, color=GRAY)
            for index, comparison in enumerate(comparisons):
                n, d = current.agreements.get(comparison, (0, 0))
                detail = f"{' / '.join(comparison)}: {n:,}/{d:,} ({percentage(n, d)})"
                ax.text(0, len(labels) - 0.25 + 0.5 * index, detail, fontsize=8, color=GRAY, va="center")
    fig.text(0.25 / width, 0.15 / height, note, fontsize=9, color=GRAY, va="bottom")
    save_figure(fig, output)


def statement_plots(groups, labels, selections, output):
    if not groups:
        return []
    jobs = []
    for category, statements in selections.items():
        slug = category.lower().replace(" / ", "_").replace(" ", "_") or "selected_statements"
        jobs.append(partial(plot_statements, groups, labels, statements, output / f"{slug}.png", category))
    return jobs


def print_examples(groups):
    for source, statements in groups.items():
        for statement, current in statements.items():
            for category, records in current.examples.items():
                for record in records:
                    print(f"\n{SOURCE_NAMES[source]} | {statement} | {category} | {record['file']} | pair {record['pair_index']}")
                    for name, key in (("Software", "software_report"), ("Physician", "physician_report"),
                                      ("Deleted", "deleted"), ("Added", "added")):
                        print(f"{name}: " + "; ".join(record.get(key) or []))
                    print(f"Explanation: {record.get('explanation') or '(unavailable)'}")


def _write_page(snapshot, page, annotation_script=""):
    template = Path(__file__).with_name("llm_edits.html").read_text()
    payload = json.dumps(snapshot, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")
    page.write_text(template.replace("/* ANNOTATION SCRIPT */", annotation_script)
                   .replace("<!-- SNAPSHOT -->", payload))
    tqdm.write(f"Saved {len(snapshot['pairs']):,} pairs to {page}")
    return page


def export_run(root):
    """Export the existing HTML browser plus both sets of figures."""
    root = Path(root)
    groups = {}
    labels = {"LLM": "category"}
    statements = {statement for terms in TERMS.values() for statement in terms}
    snapshot = _snapshot(root, consume=partial(count_statements, groups=groups,
                                             labels=labels, statements=statements))
    jobs = []
    snapshot["figures"] = {}
    for source, metrics in snapshot["summary"].items():
        output = root / "figures" / source
        jobs.extend(main_plots({source: metrics}, output))
        jobs.extend(statement_plots({source: groups[source]}, labels, TERMS, output / "statements"))
    with plt.rc_context(STYLE):
        for job in tqdm(jobs, desc="Plotting figures", unit="figure"):
            job()
    for source in snapshot["summary"]:
        snapshot["figures"][source] = [str(path.relative_to(root))
                                        for path in sorted((root / "figures" / source).rglob("*.png"))]
    return _write_page(snapshot, root / "index.html")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--config", type=Path, help="Existing llm_edits YAML; use plots.run_id.")
    inputs.add_argument("--runs", type=Path, nargs="+", help="Saved run directories.")
    inputs.add_argument("--pairs", type=Path, nargs="+", help="Saved pairs.jsonl files; read each once.")
    parser.add_argument("--annotations", type=Path, nargs="+", help="Analysis JSONs in annotator order.")
    parser.add_argument("--statements", nargs="+", help="Exact statements, ignoring case; otherwise use terms.py categories.")
    parser.add_argument("--output", type=Path, help="Figure directory; defaults to figures beside the first input.")
    parser.add_argument("--examples", type=int, default=0, help="Printed examples per statement/category (default: 0).")
    args = parser.parse_args()
    if not (args.config or args.runs or args.pairs or args.annotations):
        parser.error("Provide --config, --runs, --pairs, or --annotations.")
    if args.examples < 0:
        parser.error("--examples must be nonnegative.")
    selections = TERMS
    if args.statements:
        statements = list(dict.fromkeys(statement.lower() for statement in args.statements))
        if any(not statement.strip() for statement in statements):
            parser.error("--statements cannot contain blank statements.")
        selections = {"": statements}
    statements = {statement for terms in selections.values() for statement in terms}
    paths = args.pairs or [root / "pairs.jsonl" for root in args.runs or []]
    if args.config:
        cfg = load_config(args.config)
        if cfg["experiment"] != "llm_edits":
            parser.error("These plots require experiment: llm_edits.")
        paths = [Path(cfg["save_path"]) / "llm_edits" / cfg["data_name"] / cfg["plots"]["run_id"] / "pairs.jsonl"]
    if len({path.resolve() for path in paths}) != len(paths):
        parser.error("Input paths must be distinct.")
    output = args.output or (paths or args.annotations)[0].parent / "figures"
    counts, groups, jobs, snapshots = {}, {}, [], []
    labels = {"LLM": "category"}
    consume = partial(count_statements, groups=groups, labels=labels,
                      statements=statements, examples=args.examples)
    for path in paths:
        keep_pairs = bool(args.config or args.runs)
        snapshot = _snapshot(path.parent, path=path, consume=consume, keep_pairs=keep_pairs, totals=counts)
        if keep_pairs:
            snapshots.append((path.parent, snapshot))
    if counts:
        results = summarize(counts, empty_reports="saved pairs", undefined_ratio=None)
        for source, metrics in results.items():
            jobs.extend(main_plots({source: metrics}, output / source))
        if len(results) > 1:
            jobs.extend(main_plots(results, output / "combined"))
        jobs.extend(statement_plots(groups, labels, selections, output / "statements"))
    if args.annotations:
        records, annotation_labels = load_annotations(args.annotations)
        annotation_groups = {}
        for record in tqdm(records, desc="Grouping annotations", unit="pair"):
            count_statements(record, annotation_groups, annotation_labels, statements)
        jobs.extend(statement_plots(annotation_groups, annotation_labels, selections, output / "annotations"))
    if not jobs:
        parser.error("No AGH or old-HEEDB pairs found.")
    with plt.rc_context(STYLE):
        for job in tqdm(jobs, desc="Plotting figures", unit="figure"):
            job()
    for root, snapshot in snapshots:
        snapshot["figures"] = {
            source: [relpath(path, root) for path in sorted((output / source).glob("*.png"))]
            for source in snapshot["summary"]
        }
        _write_page(snapshot, root / "index.html")
    if args.examples:
        print_examples(groups)
    print(f"Saved figures to {output}")


if __name__ == "__main__":
    main()
