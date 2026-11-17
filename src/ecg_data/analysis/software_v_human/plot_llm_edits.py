"""Plot report changes, LLM categories, literal term metrics, and time trends from saved pairs."""

import argparse
import json
import re
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache, partial
from itertools import combinations
from os.path import relpath
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter
from scipy import stats
from tqdm import tqdm

from ecg_data.analysis.software_v_human.llm_edits import CATEGORIES, SOURCES, STATUSES, TERM_METRICS, _count, summarize
from ecg_data.analysis.software_v_human.terms import TERMS
from ecg_data.preprocess.config.load import load_config

SOURCE_NAMES = {"agh": "AGH", "heedb_old": "HEEDB"}
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
METRIC_LABELS = {
    "sensitivity": "Sensitivity",
    "specificity": "Specificity",
    "ppv": "Positive predictive value (PPV)",
    "npv": "Negative predictive value (NPV)",
}
STYLE = {
    "font.family": "DejaVu Sans", "font.size": 18, "axes.titlesize": 24,
    "axes.labelsize": 18, "xtick.labelsize": 16, "ytick.labelsize": 16,
    "legend.fontsize": 16, "text.color": BLACK, "axes.labelcolor": BLACK,
    "axes.spines.top": False, "axes.spines.right": False,
    "savefig.dpi": 200, "figure.facecolor": "white", "axes.facecolor": "white",
}


HEED_ROOT = Path("/p01/whan/data/HEED")  # Metadata location in the reference analysis.
MIN_N = 5
DAYS_PER_YEAR = 365.25



@dataclass
class StatementCounts:
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
        tqdm.write(f"{path}: excluded {ignored:,} pairs outside the AGH / HEEDB study.")
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


def plot_rates(results, rows, values, *, title, output):
    """Compare dataset percentages with grouped bars."""
    sources = list(results)
    fig, ax = plt.subplots(figsize=(max(9, len(rows) * 3.2), 6.5))
    width = 0.68 / len(sources)
    single_rate = len(rows) == 1
    for index, source in enumerate(sources):
        for position, (key, _) in enumerate(rows):
            n, d = values(results[source], key)
            x = index if single_rate else position + (index - (len(sources) - 1) / 2) * width
            rate = 100 * n / d if d else 0
            ax.bar(x, rate, 0.55 if single_rate else width * 0.9, color=SOURCE_COLORS[source], edgecolor="white",
                   label=SOURCE_NAMES[source] if position == 0 else None)
            ax.text(x, rate + 2, percentage(n, d), ha="center", va="bottom", fontsize=20, fontweight="bold")
    tick_labels = [SOURCE_NAMES[source] for source in sources] if single_rate else [fill(label, 23) for _, label in rows]
    ax.set(ylim=(0, 115), ylabel="Report pairs (%)", xticks=range(len(tick_labels)), xticklabels=tick_labels,
           xlim=(-0.65, len(tick_labels) - 0.35))
    ax.set_yticks(range(0, 101, 20))
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.set_title(title, loc="left", fontweight="bold", pad=20)
    if len(sources) > 1 and not single_rate:
        ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=len(sources))
    elif not single_rate:
        ax.set_xlabel(SOURCE_NAMES[sources[0]], labelpad=16)
    clean_ax(ax)
    save_figure(fig, output)


def plot_distribution(results, rows, denominator, *, title, output, spacing=1):
    """A 100% stack per dataset; the same label always has the same color."""
    width = max(9, 4 * len(results)) + 4 * (spacing - 1) * (len(results) - 1)
    fig, ax = plt.subplots(figsize=(width, 6.5))
    positions = [index * spacing for index in range(len(results))]
    for position, (source, metrics) in zip(positions, results.items()):
        total = metrics[denominator]
        bottom = 0
        small = []
        for key, label, color, field in rows:
            count = metrics[field].get(key, 0)
            height = 100 * count / total if total else 0
            ax.bar(position, height, 0.58, bottom=bottom, color=color,
                   edgecolor="white", linewidth=1.1)
            if height >= 10:
                ax.text(position, bottom + height / 2, percentage(count, total),
                        ha="center", va="center", color="white", fontsize=20, fontweight="bold")
            elif count:
                small.append((count, color, bottom + height / 2))
            bottom += height
        # Keep small nonzero segments proportional; label them beside the bar.
        label_heights = []
        for _, _, center in small:
            label_heights.append(max(center, label_heights[-1] + 10 if label_heights else 10))
        ceiling = 90
        for (count, color, center), label_height in reversed(list(zip(small, label_heights))):
            label_height = min(label_height, ceiling)
            ax.annotate(f"{percentage(count, total)}\n(n={count:,})",
                        xy=(position + 0.29, center), xytext=(position + 0.38, label_height),
                        ha="left", va="center", color=color, fontsize=14, fontweight="bold",
                        arrowprops={"arrowstyle": "-", "color": color, "linewidth": 1.5})
            ceiling = label_height - 10
        ax.text(position, 103, f"n={total:,}" if total else "No eligible pairs",
                ha="center", va="bottom", fontsize=18, color=GRAY)
    ax.set(ylim=(0, 112), ylabel="Report pairs (%)", xticks=positions,
           xticklabels=[SOURCE_NAMES[source] for source in results])
    ax.set_yticks(range(0, 101, 20))
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.set_title(title, loc="left", fontweight="bold", pad=20)
    ax.legend(handles=[Patch(facecolor=color, label=label) for _, label, color, _ in rows],
              loc="upper center", bbox_to_anchor=(0.5, -0.15),
              ncol=min(2, len(rows)), frameon=False)
    clean_ax(ax)
    save_figure(fig, output)


def main_plots(results, output):
    jobs = [partial(
        plot_rates, results, [("edited", "Any physician edit")],
        lambda metrics, _: (metrics["edited_reports"], metrics["included_reports"]),
        title="Physician edit rate",
        output=output / "01_edit_rate.png",
    ), partial(
        plot_distribution, results,
        [(key, label, color, "report_counts") for (key, label), color in zip(
            CHANGE_NAMES.items(), (GRAY, LIGHT_RED, DARK_RED, BLACK))],
        "included_reports", title="Types of report changes",
        output=output / "02_change_types.png",
        spacing=1.25 if len(results) > 1 else 1,
    ), partial(
        plot_rates, results, list(INPUT_NAMES.items()),
        lambda metrics, key: (metrics["input_status_counts"][key], metrics["input_reports"]),
        title="Input quality",
        output=output / "03_input_quality.png",
    ), partial(
        plot_distribution, results,
        [(key, key.title(), CATEGORY_COLORS[key], "category_counts") for key in CATEGORIES],
        "classified_reports", title="LLM edit categories",
        output=output / "04_category_rates.png",
    ), partial(
        plot_distribution, results,
        [(key, key.title(), color, "status_counts") for key, color in zip(
            STATUSES, (BLACK, GRAY, RED, LIGHT_RED))],
        "input_reports", title="Processing outcomes",
        output=output / "05_processing_status.png",
    ), partial(
        plot_rates, results, [("classified_reports", "Successfully classified"), ("skipped_reports", "Skipped")],
        lambda metrics, key: (metrics[key], metrics["edited_reports"]),
        title="Classification coverage",
        output=output / "06_classification_coverage.png",
    )]
    attempts = sorted({number for metrics in results.values() for number in metrics["attempt_counts"]})
    if attempts:
        jobs.append(partial(
            plot_rates, results, [(number, f"{number} attempt{'s' if number != 1 else ''}") for number in attempts],
            lambda metrics, key: (metrics["attempt_counts"].get(key, 0), metrics["edited_reports"]),
            title="LLM classification attempts",
            output=output / "07_attempts.png",
        ))
    return jobs


def plot_jobs(jobs, desc="Plotting figures"):
    with plt.rc_context(STYLE):
        for job in tqdm(jobs, desc=desc, unit="figure"):
            job()


def _plot_llm(results, output):
    """Keep the annotation export's plotting entry point."""
    plot_jobs(main_plots(results, Path(output)), desc="Plotting main figures")


def plot_statements(groups, labels, statements, output, category=""):
    sources = [source for source in SOURCE_NAMES if source in groups]
    comparisons = list(combinations(labels, 2))
    row_height = 0.8 * len(labels) + 0.5 * len(comparisons) + 0.35
    label_width = 6 if comparisons else 4.8
    column_width = 8
    width = label_width + column_width * len(sources) + 0.4
    height = 1.9 + row_height * len(statements) + 0.6
    fig, axes = plt.subplots(len(statements), len(sources), figsize=(width, height), squeeze=False)
    fig.subplots_adjust(left=label_width / width, right=1 - 2.5 / width,
                        top=1 - 1.9 / height, bottom=0.6 / height, wspace=1, hspace=0.25)
    title = category or ("Annotation categories and agreement" if comparisons else "LLM edit categories by statement")
    fig.text(0.25 / width, 1 - 0.2 / height, title, fontsize=24, fontweight="bold", va="top")
    fig.legend(handles=[Patch(color=CATEGORY_COLORS[key], label=key.title()) for key in STATEMENT_CATEGORIES],
               loc="upper left", bbox_to_anchor=(0.15 / width, 1 - 0.75 / height), ncol=2, frameon=False)
    for column, source in enumerate(sources):
        axes[0, column].set_title(SOURCE_NAMES[source], loc="left", fontsize=20, fontweight="bold", pad=20)
        for row, statement in enumerate(statements):
            ax = axes[row, column]
            current = groups[source].get(statement, StatementCounts())
            ax.set(xlim=(0, 100), ylim=(len(labels) + 0.5 * len(comparisons) - 0.35, -0.6))
            ax.set_xticks((0, 50, 100))
            ax.xaxis.set_major_formatter(PercentFormatter())
            ax.set_yticks([])
            ax.tick_params(axis="x", labelbottom=row == len(statements) - 1)
            clean_ax(ax, "x")
            ax.spines[["left", "bottom"]].set_visible(False)
            if column == 0:
                fig.text(0.25 / width, (ax.get_position().y0 + ax.get_position().y1) / 2,
                         fill(statement, 27), fontsize=18, va="center")
            for y, (name, key) in enumerate(labels.items()):
                counts = current.labels[key]
                total = sum(counts[category] for category in STATEMENT_CATEGORIES)
                left = 0
                for label in STATEMENT_CATEGORIES:
                    percent = 100 * counts[label] / total if total else 0
                    ax.barh(y, percent, left=left, height=0.5, color=CATEGORY_COLORS[label], edgecolor="white")
                    if percent >= 15:
                        text = ax.text(left + percent / 2, y, f"{percent:.2f}%", ha="center", va="center",
                                       color="white", fontsize=20, fontweight="bold")
                        text_width = text.get_window_extent().width
                        bar_width = ax.get_window_extent().width * percent / 100
                        text.set_fontsize(text.get_fontsize() * min(1, 0.9 * bar_width / text_width))
                    left += percent
                if len(labels) > 1:
                    ax.text(-0.03, y, name, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=16)
                detail = (f"n={total:,}\nPreferential: {counts['preferential']:,}"
                          f"\nFactual: {counts['factual']:,}")
                ax.text(1.03, y, detail, transform=ax.get_yaxis_transform(), va="center", fontsize=16, color=GRAY)
                if not total:
                    ax.text(50, y, "N/A", ha="center", va="center", fontsize=18, color=GRAY)
            for index, comparison in enumerate(comparisons):
                n, d = current.agreements.get(comparison, (0, 0))
                detail = f"{' / '.join(comparison)}: {percentage(n, d)}"
                ax.text(0, len(labels) - 0.25 + 0.5 * index, detail, fontsize=16, color=GRAY, va="center")
    save_figure(fig, output)


def category_slug(category):
    return category.lower().replace(" / ", "_").replace(" ", "_") or "selected_statements"


def statement_plots(groups, labels, selections, output):
    if not groups:
        return []
    return [partial(plot_statements, groups, labels, statements, output / f"{category_slug(category)}.png", category)
            for category, statements in selections.items()]


def plot_term_metrics(results, statements, metric, output, category=""):
    """Compare exact statement presence across all included report pairs."""
    title = METRIC_LABELS[metric]
    label_width, column_width = 5, 6.5
    width = label_width + column_width * len(results) + 0.4
    title = fill(f"{category} — {title}" if category else title, int(width * 4))
    header = 1.2 + 0.4 * title.count("\n")
    height = header + 0.9 * len(statements) + 0.6
    fig, axes = plt.subplots(1, len(results), figsize=(width, height), squeeze=False)
    fig.subplots_adjust(left=label_width / width, right=1 - 1.9 / width,
                        top=1 - header / height, bottom=0.6 / height, wspace=0.8)
    fig.text(0.25 / width, 1 - 0.2 / height, title, fontsize=24, fontweight="bold", va="top")
    numerator, denominator = TERM_METRICS[metric]
    for column, (source, metrics) in enumerate(results.items()):
        ax = axes[0, column]
        ax.set_title(SOURCE_NAMES[source], loc="left", fontsize=20, fontweight="bold", pad=20)
        ax.set(xlim=(0, 100), ylim=(len(statements) - 0.5, -0.5), yticks=[])
        ax.set_xticks((0, 50, 100))
        ax.xaxis.set_major_formatter(PercentFormatter())
        clean_ax(ax, "x")
        ax.spines[["left", "bottom"]].set_visible(False)
        for row, statement in enumerate(statements):
            values = metrics["terms"].get(statement, {
                "retained": 0, "added": 0, "deleted": 0,
                "absent_from_both": metrics["included_reports"],
            })
            n, d = values[numerator], sum(values[key] for key in denominator)
            ax.barh(row, 100 * n / d if d else 0, height=0.5, color=SOURCE_COLORS[source])
            ax.text(1.03, row, f"{percentage(n, d)}\n{n:,} / {d:,}",
                    transform=ax.get_yaxis_transform(), va="center", fontsize=16, color=GRAY)
            if column == 0:
                ax.text(-0.05, row, fill(statement, 27), transform=ax.get_yaxis_transform(),
                        ha="right", va="center", fontsize=18)
    save_figure(fig, output)


def term_plots(results, selections, output):
    return [partial(plot_term_metrics, results, statements, metric,
                    output / category_slug(category) / f"{metric}.png", category)
            for category, statements in selections.items() for metric in TERM_METRICS]


def _quarter(value):
    if not isinstance(value, (str, datetime, np.datetime64)):
        return None
    date = pd.to_datetime(value, format="ISO8601", errors="coerce")
    if pd.isna(date):
        return None
    return datetime(date.year, 3 * ((date.month - 1) // 3) + 1, 1)


@lru_cache(maxsize=1)
def _agh_dates(path):
    dates = pd.to_datetime([row.get("EditDate") for row in json.loads(path.read_text())],
                           format="%m-%d-%Y", errors="coerce")
    # The reference script excludes AGH dates from 2030 onward.
    quarters = dates.where(dates < "2030-01-01").to_period("Q").to_timestamp()
    return [None if pd.isna(date) else date.to_pydatetime() for date in quarters]


def _heed_key(value):
    """Match legacy records to institution metadata, retaining the WFDB relative path."""
    parts = Path(value).parts
    if "WFDB" in parts:
        index = parts.index("WFDB")
        return parts[index - 1], Path(*parts[index + 1:]).as_posix()
    if "HEED" in parts:
        index = parts.index("HEED")
        return parts[index + 1], Path(*parts[index + 2:]).as_posix()
    raise ValueError(f"Cannot identify the HEED institution in {value}")


def _file_name(value):
    return str(value).strip().removeprefix("./").removeprefix("/").removeprefix("WFDB/").removesuffix(".hea")


def _heed_time(path):
    instance = np.load(path, allow_pickle=True).item()
    quarter = _quarter(instance.get("ECGAcquisitionTime"))
    legacy = None
    if quarter is None and instance.get("file_path"):
        institution, name = _heed_key(instance["file_path"])
        legacy = institution, _file_name(name)
    return quarter, legacy


def _metadata_dates(path, names):
    ids = {Path(name).name for name in names}
    dates, key = {}, None
    with pd.read_csv(path, dtype=str, chunksize=100_000,
                     usecols=lambda col: col in ("FileID", "FileName", "ECGAcquisitionTime")) as chunks:
        for chunk in chunks:
            key = "FileName" if "FileName" in chunk else "FileID"
            if key not in chunk or "ECGAcquisitionTime" not in chunk:
                raise ValueError(f"{path} requires FileName or FileID, and ECGAcquisitionTime.")
            chunk[key] = chunk[key].map(_file_name)
            matched = chunk[chunk[key].isin(names if key == "FileName" else ids)]
            for name, date in matched[[key, "ECGAcquisitionTime"]].itertuples(index=False, name=None):
                quarter = _quarter(date)
                if name in dates and dates[name] != quarter:
                    raise ValueError(f"Conflicting acquisition dates for {name} in {path}")
                dates[name] = quarter
    return {name: dates.get(name if key == "FileName" else Path(name).name) for name in names}


class TimeCounts:
    def __init__(self, statements, heed_root=HEED_ROOT, workers=8):
        self.statements = set(statements)
        self.heed_root = Path(heed_root)
        self.counts = defaultdict(lambda: defaultdict(Counter))
        self.coverage = defaultdict(Counter)
        self.pending = defaultdict(list)
        self.workers = workers
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.queue = deque()

    def _add(self, source, quarter, changes):
        self.coverage[source]["dated"] += 1
        for term, edited in changes:
            self.counts[source, term][quarter].update(n=1, edited=int(edited))

    def count(self, record):
        source = record["source"]
        if source not in SOURCE_NAMES or record["change"] is None:
            return
        self.coverage[source]["included"] += 1
        changed = {s.lower() for key in ("added", "deleted") for s in record[key]}
        present = changed | {s.lower() for s in record["retained"]}
        changes = [(None, record["change"] != "unchanged")]
        changes.extend((term, term in changed) for term in present & self.statements)
        path = Path(record["file"])
        if not path.is_file():
            self.coverage[source]["missing_source_file"] += 1
            return
        if source == "heedb_old":
            self.queue.append((changes, self.pool.submit(_heed_time, path)))
            if len(self.queue) >= self.workers:
                self._collect()
            return
        dates = _agh_dates(path)
        index = record["pair_index"]
        if not 0 <= index < len(dates):
            raise ValueError(f"AGH pair index {index} is outside {path}")
        quarter = dates[index]
        if quarter is None:
            self.coverage[source]["invalid_or_missing_date"] += 1
            return
        self._add(source, quarter, changes)

    def _collect(self):
        changes, future = self.queue.popleft()
        quarter, legacy = future.result()
        if legacy is not None:
            institution, name = legacy
            self.pending[institution].append((name, changes))
        elif quarter is None:
            self.coverage["heedb_old"]["invalid_or_missing_date"] += 1
        else:
            self._add("heedb_old", quarter, changes)

    def finish(self):
        """Read each legacy institution CSV once, matching only requested ECGs."""
        with self.pool:
            while self.queue:
                self._collect()
        for institution, records in tqdm(self.pending.items(), desc="Reading HEEDB dates", unit="institution",
                                         disable=not self.pending):
            path = self.heed_root / institution / "metadata/metadata.csv"
            if not path.is_file():
                self.coverage["heedb_old"]["missing_metadata"] += len(records)
                tqdm.write(f"Missing HEEDB metadata: {path}")
                continue
            dates = _metadata_dates(path, {name for name, _ in records})
            for name, changes in records:
                quarter = dates[name]
                if quarter is None:
                    self.coverage["heedb_old"]["unmatched_or_invalid_metadata_date"] += 1
                    continue
                self._add("heedb_old", quarter, changes)
        self.pending.clear()
        for source, counts in self.coverage.items():
            exclusions = {key: n for key, n in counts.items() if key not in ("included", "dated")}
            tqdm.write(f"{source} time coverage: {counts['dated']:,} / {counts['included']:,} included pairs; "
                       f"exclusions: {exclusions}")

    def series(self, source, term):
        bins = [{"quarter": quarter.isoformat(), "n": values["n"], "edited": values["edited"],
                 "rate": values["edited"] / values["n"], "used": values["n"] >= MIN_N}
                for quarter, values in sorted(self.counts[source, term].items())]
        return {"bins": bins, "fit": fit_trend(bins)}


def fit_trend(bins):
    """Equal-weight OLS of eligible quarterly rates; slope is percentage points/year."""
    eligible = [row for row in bins if row["used"]]
    if len(eligible) < 2:
        return None
    dates = pd.to_datetime([row["quarter"] for row in eligible])
    x = (dates - dates[0]).days.to_numpy() / DAYS_PER_YEAR
    y = np.array([100 * row["rate"] for row in eligible])
    result = stats.linregress(x, y)
    fit = {"bins": len(eligible), "origin": dates[0].isoformat(),
           "slope_pp_per_year": float(result.slope), "intercept": float(result.intercept),
           "ci_low": None, "ci_high": None, "p_value": None}
    # Two points have no residual degrees of freedom; constant rates have no variance.
    if len(eligible) >= 3 and np.ptp(y) > 0:
        margin = stats.t.ppf(0.975, len(eligible) - 2) * result.stderr
        fit.update(ci_low=float(result.slope - margin), ci_high=float(result.slope + margin),
                   p_value=float(result.pvalue))
    return fit


def plot_time_trends(results, term, output):
    fig, ax = plt.subplots(figsize=(13, 8))
    missing = []
    for source, series in results.items():
        bins, fit = series["bins"], series["fit"]
        eligible = [row for row in bins if row["used"]]
        if not eligible:
            missing.append(SOURCE_NAMES[source])
            continue
        rates = pd.Series({pd.Timestamp(row["quarter"]): 100 * row["rate"] if row["used"] else float("nan")
                           for row in bins})
        rates = rates.reindex(pd.date_range(rates.index.min(), rates.index.max(), freq="QS"))
        color = SOURCE_COLORS[source]
        n = sum(row["n"] for row in eligible)
        ax.plot(rates.index, rates.values, marker="o", color=color, linewidth=2,
                label=f"{SOURCE_NAMES[source]} (n={n:,}; {len(eligible)} quarters)")
        if fit is None:
            continue
        dates = pd.to_datetime([eligible[0]["quarter"], eligible[-1]["quarter"]])
        years = (dates - pd.Timestamp(fit["origin"])).days / DAYS_PER_YEAR
        detail = "95% CI / p unavailable"
        if fit["ci_low"] is not None:
            detail = f"95% CI [{fit['ci_low']:+.2f}, {fit['ci_high']:+.2f}]; p={fit['p_value']:.3g}"
        ax.plot(dates, fit["intercept"] + fit["slope_pp_per_year"] * years,
                linestyle="--", color=color, linewidth=2,
                label=f"{SOURCE_NAMES[source]} fit: {fit['slope_pp_per_year']:+.2f} pp/year\n{detail}")
    title = "Physician edit rate over time" if term is None else f"{term} — edit rate over time"
    ax.set_title(fill(title, 65), loc="left", fontweight="bold", pad=20)
    ax.set(ylim=(0, 100), ylabel="Edit rate (%)", xlabel="Calendar quarter")
    ax.yaxis.set_major_formatter(PercentFormatter())
    clean_ax(ax)
    if ax.lines:
        locator = AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=len(results),
                  frameon=False, fontsize=13)
    else:
        ax.text(0.5, 0.5, f"No quarters with n ≥ {MIN_N}", transform=ax.transAxes, ha="center", color=GRAY)
        ax.set_xticks([])
    denominator = "all included pairs" if term is None else "pairs retaining, adding, or deleting this exact term"
    coverage = f"No eligible quarters: {', '.join(missing)}.\n" if missing else ""
    fig.text(0.08, 0.01, coverage + f"Denominator: {denominator}.\n"
             f"Minimum n={MIN_N} per quarter; equal-weight linear fit; pp = percentage points.",
             fontsize=13, color=GRAY)
    fig.subplots_adjust(bottom=0.37, top=0.86, left=0.09, right=0.98)
    save_figure(fig, output)


def time_plots(counts, sources, selections, output):
    def series(term):
        return {source: counts.series(source, term) for source in sources}

    overall = series(None)
    terms = {term: series(term) for statements in selections.values() for term in statements}
    output.mkdir(parents=True, exist_ok=True)
    (output / "trends.json").write_text(json.dumps({
        "method": {"bin": "calendar quarter", "min_n": MIN_N, "fit": "equal-weight OLS of quarterly rates",
                   "slope_unit": "percentage points per year", "confidence_level": 0.95,
                   "dates": {"agh": "EditDate (before 2030-01-01)", "heedb_old": "ECGAcquisitionTime"}},
        "coverage": {source: dict(counts.coverage[source]) for source in sources},
        "overall": overall, "terms": terms,
    }, indent=2, allow_nan=False))
    jobs = [partial(plot_time_trends, overall, None, output / "overall.png")]
    for category, statements in selections.items():
        for index, term in enumerate(statements, 1):
            name = re.sub(r"[^a-z0-9]+", "_", term).strip("_")
            jobs.append(partial(plot_time_trends, terms[term], term,
                                output / category_slug(category) / f"{index:02d}_{name}.png"))
    return jobs


def dataset_plots(results, selections, times, output):
    return (main_plots(results, output)
            + term_plots(results, selections, output / "term_metrics")
            + time_plots(times, results, selections, output / "time_trends"))


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


def _write_run(snapshot, root, output):
    snapshot["figures"] = {
        source: [relpath(path, root) for path in sorted((output / source).rglob("*.png"))]
        for source in snapshot["summary"]
    }
    return _write_page(snapshot, root / "index.html")


def export_run(root):
    """Export the HTML browser and figures from saved pairs."""
    root = Path(root)
    groups = {}
    labels = {"LLM": "category"}
    statements = {statement for terms in TERMS.values() for statement in terms}
    times = TimeCounts(statements)

    def consume(record):
        count_statements(record, groups, labels, statements)
        times.count(record)

    snapshot = _snapshot(root, consume=consume)
    times.finish()
    jobs = []
    for source, metrics in snapshot["summary"].items():
        output = root / "figures" / source
        jobs.extend(dataset_plots({source: metrics}, TERMS, times, output))
        jobs.extend(statement_plots({source: groups[source]}, labels, TERMS, output / "statements"))
    plot_jobs(jobs)
    return _write_run(snapshot, root, root / "figures")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--config", type=Path, nargs="+", help="LLM-edit YAMLs; use each plots.run_id.")
    inputs.add_argument("--runs", type=Path, nargs="+", help="Saved run directories.")
    inputs.add_argument("--pairs", type=Path, nargs="+", help="Saved pairs.jsonl files; read each once.")
    parser.add_argument("--annotations", type=Path, nargs="+", help="Analysis JSONs in annotator order.")
    parser.add_argument("--statements", nargs="+", help="Exact statements, ignoring case; otherwise use terms.py categories.")
    parser.add_argument("--output", type=Path, help="Figure directory; defaults to figures beside the first input; combined plots go in combined/.")
    parser.add_argument("--examples", type=int, default=0, help="Printed examples per statement/category (default: 0).")
    parser.add_argument("--heed-root", type=Path, default=HEED_ROOT,
                        help="Legacy HEEDB metadata root; used when NPY files lack ECGAcquisitionTime.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent HEEDB date reads (default: 8).")
    args = parser.parse_args()
    if not (args.config or args.runs or args.pairs or args.annotations):
        parser.error("Provide --config, --runs, --pairs, or --annotations.")
    if args.examples < 0:
        parser.error("--examples must be nonnegative.")
    if args.workers < 1:
        parser.error("--workers must be positive.")
    selections = TERMS
    if args.statements:
        statements = list(dict.fromkeys(statement.lower() for statement in args.statements))
        if any(not statement.strip() for statement in statements):
            parser.error("--statements cannot contain blank statements.")
        selections = {"": statements}
    statements = {statement for terms in selections.values() for statement in terms}
    paths = args.pairs or [root / "pairs.jsonl" for root in args.runs or []]
    for config in args.config or []:
        cfg = load_config(config)
        if cfg["experiment"] != "llm_edits":
            parser.error("These plots require experiment: llm_edits.")
        paths.append(Path(cfg["save_path"]) / "llm_edits" / cfg["data_name"] / cfg["plots"]["run_id"] / "pairs.jsonl")
    if len({path.resolve() for path in paths}) != len(paths):
        parser.error("Input paths must be distinct.")
    output = args.output or (paths or args.annotations)[0].parent / "figures"
    counts, groups, jobs, snapshots = {}, {}, [], []
    labels = {"LLM": "category"}
    times = TimeCounts(statements, args.heed_root, args.workers)

    def consume(record):
        count_statements(record, groups, labels, statements, examples=args.examples)
        times.count(record)

    for path in paths:
        keep_pairs = bool(args.config or args.runs)
        snapshot = _snapshot(path.parent, path=path, consume=consume, keep_pairs=keep_pairs, totals=counts)
        if keep_pairs:
            snapshots.append((path.parent, snapshot))
    if counts:
        times.finish()
        results = summarize(counts, empty_reports="saved pairs", undefined_ratio=None)
        for source, metrics in results.items():
            jobs.extend(dataset_plots({source: metrics}, selections, times, output / source))
        if len(results) > 1:
            jobs.extend(dataset_plots(results, selections, times, output / "combined"))
        jobs.extend(statement_plots(groups, labels, selections, output / "statements"))
    if args.annotations:
        records, annotation_labels = load_annotations(args.annotations)
        annotation_groups = {}
        for record in tqdm(records, desc="Grouping annotations", unit="pair"):
            count_statements(record, annotation_groups, annotation_labels, statements)
        jobs.extend(statement_plots(annotation_groups, annotation_labels, selections, output / "annotations"))
    if not jobs:
        parser.error("No AGH or HEEDB pairs found.")
    plot_jobs(jobs)
    for root, snapshot in snapshots:
        _write_run(snapshot, root, output)
    if args.examples:
        print_examples(groups)
    print(f"Saved figures to {output}")


if __name__ == "__main__":
    main()
