"""Plot saved edits-study counts without rereading the ECG dataset."""

import json
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator, PercentFormatter

from ecg_data.preprocess.config.load import get_config

SOURCE_NAMES = {"agh": "AGH", "heedb_old": "HEEDB old software", "heedb_new": "HEEDB new software"}
CHANGE_NAMES = {
    "unchanged": "Unchanged",
    "added_only": "Physician added only",
    "deleted_only": "Physician deleted only",
    "both": "Physician added and deleted",
}
INPUT_NAMES = {
    "software_empty": "Software empty only",
    "physician_empty": "Physician empty only",
    "both_empty": "Both reports empty",
    "missing": "Missing report",
    "invalid": "Malformed report",
}
TERM_METRICS = {
    "sensitivity": (
        "retained", ("retained", "added"), "Sensitivity: G1 / (G1 + G3)",
        "When the physician includes a statement, how often does software include it?",
        "G1: statement present in both software and physician reports.",
        "G1 + G3: statement present in the physician report.",
    ),
    "specificity": (
        "absent_from_both", ("deleted", "absent_from_both"), "Specificity: G4 / (G2 + G4)",
        "When the physician excludes a statement, how often does software exclude it?",
        "G4: statement absent from both software and physician reports.",
        "G2 + G4: statement absent from the physician report.",
    ),
    "ppv": (
        "retained", ("retained", "deleted"), "Positive predictive value (PPV): G1 / (G1 + G2)",
        "When software includes a statement, how often does the physician retain it?",
        "G1: statement present in both software and physician reports.",
        "G1 + G2: statement present in the software report.",
    ),
    "npv": (
        "absent_from_both", ("added", "absent_from_both"), "Negative predictive value (NPV): G4 / (G3 + G4)",
        "When software excludes a statement, how often does the physician also exclude it?",
        "G4: statement absent from both software and physician reports.",
        "G3 + G4: statement absent from the software report.",
    ),
}
COLORS = ("#386b96", "#c17735", "#43816c")


def _percentage(numerator, denominator):
    if not denominator:
        return "Undefined"
    value = numerator / denominator
    if 0.999 < value < 1:
        return ">99.9%"
    return "<0.1%" if 0 < value < 0.001 else f"{value:.1%}"


def _plot_rates(results, rows, values, *, title, numerator, denominator, cohort, output, note, interpretation=None):
    """Keep definitions, chart rows, and notes in separate layout regions."""
    sources = list(results)
    labels = [fill(label, width=43) for _, label in rows]
    row_heights = [max(len(sources) * 0.37 + 0.28, (label.count("\n") + 1) * 0.2 + 0.28) for label in labels]
    body_height = max(1.25, sum(row_heights))
    blocks = [(title, 18, "bold")]
    if interpretation:
        blocks.append((fill(interpretation, 125), 11, "normal"))
    blocks.extend([
        (fill(f"Numerator: {numerator}", 125), 10.5, "normal"),
        (fill(f"Denominator: {denominator}", 125), 10.5, "normal"),
        (fill(cohort, 125), 10.5, "normal"),
    ])
    block_heights = [(text.count("\n") + 1) * size / 72 * 1.5 + 0.1 for text, size, _ in blocks]
    header_height = sum(block_heights) + 0.4
    footer = fill(note, 145)
    footer_height = 0.4 + (footer.count("\n") + 1) * 0.18
    height = header_height + 0.35 + body_height + footer_height + 0.4
    fig = plt.figure(figsize=(15, height), facecolor="white")
    grid = fig.add_gridspec(
        4, 3, height_ratios=(header_height, 0.35, body_height, footer_height),
        width_ratios=(4.4, 5.3, 3.6), hspace=0, wspace=0.08,
        left=0.035, right=0.98, top=1 - 0.2 / height, bottom=0.2 / height,
    )

    header = fig.add_subplot(grid[0, :])
    header.set_axis_off()
    y = 1
    for (text, size, weight), block_height in zip(blocks, block_heights):
        header.text(0, y, text, va="top", fontsize=size, fontweight=weight, color="#253449")
        y -= block_height / header_height
    header.legend(
        handles=[Patch(color=COLORS[index % len(COLORS)], label=SOURCE_NAMES.get(source, source))
                 for index, source in enumerate(sources)],
        loc="lower left", ncol=len(sources), frameon=False, borderaxespad=0, fontsize=10,
    )
    for column, text in enumerate(("REPORT CATEGORY / STATEMENT", "RATE", "PERCENT")):
        heading = fig.add_subplot(grid[1, column])
        heading.set_axis_off()
        heading.text(0, 0.25, text, fontsize=8.5, fontweight="bold", color="#64748b")
        if column == 2:
            heading.text(1, 0.25, "NUMERATOR / DENOMINATOR", ha="right",
                         fontsize=8.5, fontweight="bold", color="#64748b")

    label_ax, rate_ax, count_ax = [fig.add_subplot(grid[2, column]) for column in range(3)]
    for ax in (label_ax, rate_ax, count_ax):
        ax.set(xlim=(0, 1), ylim=(body_height, 0), yticks=[])
    label_ax.set_axis_off()
    count_ax.set_axis_off()
    rate_ax.spines[["top", "right", "left"]].set_visible(False)
    rate_ax.spines["bottom"].set_color("#cbd5e1")
    rate_ax.xaxis.set_major_locator(MultipleLocator(0.25))
    rate_ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    rate_ax.tick_params(axis="x", labelsize=9, colors="#64748b", length=0, pad=8)
    rate_ax.grid(axis="x", color="#e2e8f0", linewidth=0.7)
    rate_ax.set_axisbelow(True)
    position = 0
    for index, ((key, _), label, row_height) in enumerate(zip(rows, labels, row_heights)):
        center = position + row_height / 2
        if index % 2 == 0:
            for ax in (label_ax, rate_ax, count_ax):
                ax.axhspan(position, position + row_height, color="#f5f7fa", zorder=0)
        label_ax.text(0, center, label, va="center", fontsize=10.5, color="#253449")
        for source_index, source in enumerate(sources):
            n, d = values(results[source], key)
            y = center + (source_index - (len(sources) - 1) / 2) * 0.37
            color = COLORS[source_index % len(COLORS)]
            rate_ax.barh(y, n / d if d else 0, height=0.23, color=color)
            count_ax.text(0, y, _percentage(n, d), va="center", fontsize=10.5, fontweight="bold", color=color)
            count_ax.text(1, y, f"{n:,} / {d:,}", ha="right", va="center", fontsize=10, color=color)
        position += row_height

    footer_ax = fig.add_subplot(grid[3, :])
    footer_ax.set_axis_off()
    footer_ax.text(0, 0, footer, va="bottom", fontsize=9, color="#64748b")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)


def plot_results(results, output, *, top_terms):
    """Keep the full saved analysis; limit only the statement plots."""
    if not results or any(metrics.get("study") != "edits" for metrics in results.values()):
        raise ValueError("Expected saved results from experiment: edits.")
    if any(metrics.get("normalization", {}).get("blanks") != "drop" for metrics in results.values()):
        raise ValueError("Rerun the edits analysis first: these results predate blank-statement removal.")
    if not isinstance(top_terms, int) or top_terms < 1:
        raise ValueError("plots.top_terms must be a positive integer.")
    policies = {metrics["empty_reports"] for metrics in results.values()}
    if len(policies) != 1:
        raise ValueError("Compared sources must use the same empty-report policy.")
    order = {source: index for index, source in enumerate(SOURCE_NAMES)}
    results = {source: results[source] for source in sorted(results, key=lambda source: (order.get(source, len(order)), source))}
    output = Path(output)
    cohort = "Included pairs: both reports are present and are lists of strings."
    if policies == {"exclude"}:
        cohort += " Each report must contain at least one nonblank statement."
    else:
        cohort += " Empty reports are included under the configured compare policy."
    counts = " | ".join(
        f"{SOURCE_NAMES.get(source, source)}: {metrics['included_reports']:,} included / {metrics['input_reports']:,} input pairs"
        for source, metrics in results.items()
    )
    _plot_rates(
        results, [("edited", "Any physician edit")],
        lambda metrics, _: (metrics["edited_reports"], metrics["included_reports"]),
        title="Report edit rate", numerator="Included pairs with any statement added or deleted.",
        denominator="All included report pairs.", cohort=cohort,
        output=output / "01_edit_rate.png", note=counts,
    )
    _plot_rates(
        results, list(CHANGE_NAMES.items()),
        lambda metrics, key: (metrics["report_counts"][key], metrics["included_reports"]),
        title="Types of report changes", numerator="Included pairs in the stated change category.",
        denominator="All included report pairs.", cohort=cohort,
        output=output / "02_change_types.png",
        note="Each included pair belongs to exactly one category. " + counts,
    )
    _plot_rates(
        results, list(INPUT_NAMES.items()),
        lambda metrics, key: (metrics["input_status_counts"][key], metrics["input_reports"]),
        title="Input quality: empty, missing, and malformed reports",
        numerator="Input pairs with the stated issue. Each pair belongs to at most one issue category.",
        denominator="All input report pairs read by this analysis, before exclusions.",
        cohort="Empty: no nonblank statements. Missing: either report is null or absent. Malformed: a present report is not a list of strings.",
        output=output / "03_input_quality.png",
        note="Missing takes priority over malformed; empty counts require two valid lists. Records removed by upstream preprocessing are not counted.",
    )
    vocabulary = set().union(*(metrics["terms"] for metrics in results.values()))
    edits = {
        term: sum(metrics["terms"][term]["edited_report_count"] for metrics in results.values())
        for term in vocabulary
    }
    selected = sorted(vocabulary, key=lambda term: (-edits[term], term))[:top_terms]
    if selected:
        rows = [(term, term) for term in selected]
        note = (f"Showing {len(selected)} statements with the most additions + deletions across sources, in the same order on all statement plots. "
                "All statements remain in the saved analysis. Each source uses its own report pairs. "
                "Undefined means the denominator is zero. " + counts)
        statement_cohort = (
            "Reference: physician report. Evaluated: software report. Higher is better. "
            "Includes entirely unchanged reports. " + cohort
        )
        for name, (numerator, denominator, title, interpretation, numerator_meaning, denominator_meaning) in TERM_METRICS.items():
            _plot_rates(
                results, rows,
                lambda metrics, term: (metrics["terms"][term][numerator], sum(metrics["terms"][term][key] for key in denominator)),
                title=title, numerator=numerator_meaning, denominator=denominator_meaning, cohort=statement_cohort,
                interpretation=interpretation,
                output=output / "statements" / f"{name}.png", note=note,
            )
    for name in ("disagreement", "additions", "deletions"):
        (output / "statements" / f"{name}.png").unlink(missing_ok=True)
    print(f"Saved edits-study figures to {output}")


if __name__ == "__main__":
    cfg = get_config()
    if cfg["experiment"] != "edits":
        raise ValueError("These plots require experiment: edits.")
    root = Path(cfg["save_path"]) / "edits"
    results = json.loads((root / f"{cfg['data_name']}.json").read_text())
    plot_results(results, root / "figures" / cfg["data_name"], **cfg["plots"])
