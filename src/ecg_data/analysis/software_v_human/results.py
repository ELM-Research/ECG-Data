"""Focused tables and figures for software-versus-physician comparisons."""

import csv
import json
from textwrap import fill

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

from ecg_data.analysis.software_v_human.terms import TERMS


TABLES = {
    "counts": (
        "original_term_frequency",
        "original_report_count",
        "final_term_frequency",
        "final_report_count",
    ),
    "prevalence": (
        "report_count",
        "original_report_proportion",
        "final_report_proportion",
    ),
    "changes": (
        "group_1_retained",
        "group_2_deleted",
        "group_3_added",
        "group_4_never_present",
        "added_report_ratio",
        "deleted_report_ratio",
    ),
}

ADDED = "#288274"
DELETED = "#bb643f"
OVERVIEW_TERMS = 15


def save_results(path, summary, rows):
    (path / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    for name, columns in TABLES.items():
        fields = ("cohort", "category", "term", *columns)
        with (path / f"{name}.csv").open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    modified = [row for row in rows if row["cohort"] == "modified"]
    plot_overview(path, summary, modified)
    with PdfPages(path / "terms.pdf") as pdf:
        for category in TERMS:
            terms = [row for row in modified if row["category"] == category]
            pdf.savefig(plot_category(path.name, category, summary, terms))


def _plot_changes(title, summary, rows):
    figure = Figure(figsize=(max(8, len(rows) * 0.85), 9), facecolor="white", layout="constrained")
    FigureCanvasAgg(figure)
    figure.suptitle(
        f"{title}\nModified reports: {summary['modified_reports']:,} · N = reports with the edit",
        fontsize=12,
    )
    axes = figure.subplots(2, 1, sharex=True)
    x = list(range(len(rows)))

    for axis, ratio, count, title, denominator, color in (
        (axes[0], "added_report_ratio", "group_3_added", "Additions", "Originally absent reports", ADDED),
        (axes[1], "deleted_report_ratio", "group_2_deleted", "Deletions", "Originally present reports", DELETED),
    ):
        values = [row[ratio] if row[ratio] is not None else 0 for row in rows]
        bars = axis.bar(x, values, width=0.65, color=color)
        labels = [
            f"N={row[count]:,}" if row[ratio] is not None else "n/a"
            for row in rows
        ]
        axis.bar_label(bars, labels=labels, padding=4, fontsize=9)
        axis.set_title(title, loc="left", fontsize=12)
        axis.set_ylabel(f"% of {denominator.lower()}", fontsize=10)
        axis.set_ylim(0, 1.12)
        axis.set_yticks([0, 0.25, 0.5, 0.75, 1])
        axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        axis.set_axisbelow(True)
        axis.grid(axis="y", color="#e6e9ec", linewidth=0.6)
        axis.tick_params(axis="both", length=0, labelsize=9)
        for spine in axis.spines.values():
            spine.set_visible(False)

    axes[-1].set_xticks(x, [fill(row["term"], 20) for row in rows])
    if len(rows) > 4:
        for label in axes[-1].get_xticklabels():
            label.set_rotation(45)
            label.set_ha("right")
            label.set_rotation_mode("anchor")
    return figure


def plot_overview(path, summary, rows):
    changed = [row for row in rows if row["group_2_deleted"] + row["group_3_added"]]
    changed.sort(key=lambda row: (-(row["group_2_deleted"] + row["group_3_added"]), row["term"]))
    shown = changed[:OVERVIEW_TERMS]
    figure = _plot_changes(f"{path.name} | Physician edits", summary, shown)
    if not shown:
        for axis in figure.axes:
            axis.text(0.5, 0.5, "No additions or deletions.", transform=axis.transAxes, ha="center")
    figure.savefig(path / "overview.png", dpi=180)


def plot_category(name, category, summary, rows):
    return _plot_changes(f"{name} | {category}", summary, rows)
