import argparse
import csv
import json
from pathlib import Path
import re
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator, PercentFormatter

GROUPS = ("group_1_retained", "group_2_deleted", "group_3_added", "group_4_never_present")
METRICS = {
    "edits": (
        ("added_report_ratio", "Added by physician", "% of reports without the term in software"),
        ("deleted_report_ratio", "Removed by physician", "% of reports with the term in software"),
    ),
    "error_rates": (
        ("false_negative_rate", "Added by physician (false negative rate)", "% of reports with the term in physician report"),
        ("false_positive_rate", "Removed by physician (false positive rate)", "% of reports without the term in physician report"),
    ),
    "disagreement": (
        ("missed_ratio", "Software missed (physician added)", "% of reports with the term in either report"),
        ("extra_ratio", "Software extra (physician removed)", "% of reports with the term in either report"),
    ),
}


def plot_changes(path, summary, rows, title, metric="edits", *, cohort="modified", sharex=False):
    metrics = METRICS[metric]
    count = summary["analyzed_reports"] if cohort == "all" else summary[f"{cohort}_reports"]
    cohort_label = "all analyzed" if cohort == "all" else cohort
    figure = Figure(figsize=(14, max(3.2, 2.1 + len(rows) * 0.4)), layout="constrained")
    FigureCanvasAgg(figure)
    figure.suptitle(
        f"{path.name} | {title}\n"
        f"{count:,} {cohort_label} reports · N = reports with that edit",
        fontsize=11,
    )
    axes = figure.subplots(1, 2, sharey=True, sharex=sharex)
    y = list(range(len(rows)))
    shared_peak = max((row[key] or 0 for row in rows for key, _, _ in metrics), default=0)

    for axis, (ratio, axis_title, denominator), count, color in zip(
        axes, metrics,
        ("group_3_added", "group_2_deleted"), ("#288274", "#bb643f"),
    ):
        values = [row[ratio] if row[ratio] is not None else 0 for row in rows]
        bars = axis.barh(y, values, height=0.6, color=color)
        labels = []
        for row in rows:
            value = row[ratio]
            percent = "n/a"
            if value is not None:
                percent = f"{value:.1%}" if value >= 0.01 else f"{100 * value:.2g}%"
            labels.append(f"{percent} · N={row[count]:,}")
        axis.bar_label(bars, labels=labels, padding=5, fontsize=9)
        axis.set_title(axis_title, loc="left", fontsize=12, weight="bold")
        axis.set_xlabel(denominator, fontsize=9)
        peak = (shared_peak if sharex else max(values, default=0)) or 1
        ticks = MaxNLocator(nbins=3).tick_values(0, peak)
        ticks = [tick for tick in ticks if 0 <= tick <= 1]
        axis.set_xticks(ticks)
        axis.set_xlim(0, max(peak, ticks[-1]) * 1.55)
        axis.xaxis.set_major_formatter(PercentFormatter(1))
        axis.set_axisbelow(True)
        axis.grid(axis="x", color="#e6e9ec", linewidth=0.6)
        axis.tick_params(axis="both", length=0, labelsize=9)
        for spine in axis.spines.values():
            spine.set_visible(False)
        if not rows:
            axis.text(0.5, 0.5, "No terms were added or removed.", transform=axis.transAxes, ha="center")

    axes[0].set_yticks(y, [row["term"] for row in rows])
    axes[0].set_ylim(max(1, len(rows)) - 0.5, -0.5)
    if any(row[key] is None for row in rows for key, _, _ in metrics):
        figure.supxlabel("n/a = no eligible reports", fontsize=9, color="#58616b")
    return figure


def render_results(path):
    summary = json.loads((path / "summary.json").read_text())
    with (path / "changes.csv").open() as file:
        rows = [row for row in csv.DictReader(file) if row["cohort"] in ("all", "modified")]
    for row in rows:
        for key in GROUPS:
            row[key] = int(row[key])
        for key in ("added_report_ratio", "deleted_report_ratio"):
            row[key] = float(row[key]) if row[key] else None
        present = row["group_1_retained"] + row["group_3_added"]
        absent = row["group_2_deleted"] + row["group_4_never_present"]
        row["false_negative_rate"] = row["group_3_added"] / present if present else None
        row["false_positive_rate"] = row["group_2_deleted"] / absent if absent else None
        denominator = present + row["group_2_deleted"]
        row["report_count"] = present + absent
        row["either_report_count"] = denominator
        row["missed_ratio"] = row["group_3_added"] / denominator if denominator else None
        row["extra_ratio"] = row["group_2_deleted"] / denominator if denominator else None
        row["disagreement_ratio"] = (
            (row["group_3_added"] + row["group_2_deleted"]) / denominator if denominator else None
        )
    rows.sort(key=lambda row: (-(row["group_2_deleted"] + row["group_3_added"]), row["term"]))
    cohorts = {cohort: [row for row in rows if row["cohort"] == cohort] for cohort in ("all", "modified")}
    for cohort, cohort_rows in cohorts.items():
        if not cohort_rows:
            raise ValueError(f"No '{cohort}' cohort in {path / 'changes.csv'}; rerun analysis.")

    output = path / "all_reports"
    output.mkdir(exist_ok=True)
    fields = (
        "cohort", "category", "term", "report_count", *GROUPS,
        "either_report_count", "missed_ratio", "extra_ratio", "disagreement_ratio",
    )
    with (output / "disagreement.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cohorts["all"])

    for metric in METRICS:
        cohort = "all" if metric == "disagreement" else "modified"
        rows = cohorts[cohort]
        changed = [row for row in rows if row["group_2_deleted"] + row["group_3_added"]]
        output = path / "all_reports" if cohort == "all" else path
        suffix = "_error_rates" if metric == "error_rates" else ""
        title = "Term disagreement" if cohort == "all" else "Physician edits"
        figure = plot_changes(path, summary, changed, title, metric, cohort=cohort, sharex=cohort == "all")
        figure.savefig(output / f"overview{suffix}.png", dpi=180)
        for category in dict.fromkeys(row["category"] for row in rows):
            terms = [row for row in rows if row["category"] == category]
            figure = plot_changes(path, summary, terms, category, metric, cohort=cohort, sharex=cohort == "all")
            filename = re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_")
            figure.savefig(output / f"terms_{filename}{suffix}.png", dpi=180)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths", nargs="*", type=Path, default=[Path(__file__).parent / "results"],
        help="Comparison directories or a parent containing them (default: results beside this script).",
    )
    args = parser.parse_args()
    for path in args.paths:
        directories = [path] if (path / "changes.csv").is_file() else sorted(
            file.parent for file in path.glob("*/changes.csv")
        )
        if not directories:
            parser.error(f"No changes.csv found in {path} or its immediate subdirectories.")
        for directory in directories:
            render_results(directory)
            print(f"Saved all three analyses: {directory}")
