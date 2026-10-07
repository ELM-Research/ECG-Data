"""Plot saved edits-study counts without rereading the ECG dataset."""

import json
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ecg_data.analysis.software_v_human.terms import TERMS
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


def _plot_rates(results, rows, values, *, title, numerator, denominator, output, note, interpretation=None):
    """Compare sources in compact columns with inline bars on a shared 0–100% scale."""
    sources = list(results)
    # Layout dimensions are inches, so text and row spacing stay consistent.
    label_width, source_width, margin = 3.5, 2.8, 0.25
    content_width = label_width + len(sources) * source_width
    width = content_width + 2 * margin
    labels = [fill(label, width=40) for _, label in rows]
    row_heights = [max(0.46, (label.count("\n") + 1) * 0.17 + 0.16) for label in labels]
    body_height = sum(row_heights)
    wrap_width = int(content_width * 12)
    heading, _, detail = title.partition(": ")
    context = " · ".join(text for text in (detail, interpretation) if text)
    blocks = [(fill(heading, int(content_width * 7)), 16, "bold")]
    if context:
        blocks.append((fill(context, wrap_width), 10, "normal"))
    blocks.extend([
        (fill(f"Numerator: {numerator}", wrap_width), 9, "normal"),
        (fill(f"Denominator: {denominator}", wrap_width), 9, "normal"),
    ])
    block_heights = [(text.count("\n") + 1) * size / 72 * 1.35 + 0.06 for text, size, _ in blocks]
    header_height = sum(block_heights) + 0.03
    source_labels = [fill(SOURCE_NAMES.get(source, source), width=28) for source in sources]
    heading_height = max(label.count("\n") + 1 for label in source_labels) * 0.18 + 0.12
    footer = fill("Bars: 0–100%. Counts: numerator / denominator. " + note, int(content_width * 16))
    footer_height = 0.14 + (footer.count("\n") + 1) * 0.15
    height = header_height + heading_height + body_height + footer_height + 2 * margin
    fig = plt.figure(figsize=(width, height), facecolor="white")
    grid = fig.add_gridspec(
        4, 1, height_ratios=(header_height, heading_height, body_height, footer_height),
        hspace=0, left=margin / width, right=1 - margin / width,
        top=1 - margin / height, bottom=margin / height,
    )

    header = fig.add_subplot(grid[0])
    header.set_axis_off()
    y = 1
    for index, ((text, size, weight), block_height) in enumerate(zip(blocks, block_heights)):
        header.text(0, y, text, va="top", fontsize=size, fontweight=weight,
                    color="#253449" if index == 0 else "#64748b")
        y -= block_height / header_height

    heading = fig.add_subplot(grid[1])
    heading.set(xlim=(0, content_width), ylim=(heading_height, 0))
    heading.set_axis_off()
    heading.text(0, heading_height - 0.1, "CATEGORY / STATEMENT", va="bottom",
                 fontsize=8, fontweight="bold", color="#64748b")
    for index, label in enumerate(source_labels):
        x = label_width + index * source_width + 0.14
        heading.text(x, heading_height - 0.1, label, va="bottom", fontsize=10,
                     fontweight="bold", color=COLORS[index % len(COLORS)])
    heading.axhline(heading_height - 0.04, color="#cbd5e1", linewidth=0.8)

    body = fig.add_subplot(grid[2])
    body.set(xlim=(0, content_width), ylim=(body_height, 0))
    body.set_axis_off()
    position = 0
    for (key, _), label, row_height in zip(rows, labels, row_heights):
        center = position + row_height / 2
        body.text(0, center, label, va="center", fontsize=9.5, color="#253449")
        for source_index, source in enumerate(sources):
            n, d = values(results[source], key)
            left = label_width + source_index * source_width + 0.14
            right = label_width + (source_index + 1) * source_width - 0.14
            color = COLORS[source_index % len(COLORS)]
            body.text(left, center - 0.06, _percentage(n, d), va="center", fontsize=10,
                      fontweight="bold", color=color if d else "#64748b")
            body.text(right, center - 0.06, f"{n:,} / {d:,}", ha="right", va="center",
                      fontsize=8, color="#64748b")
            if d:
                body.barh(center + 0.11, right - left, left=left, height=0.045, color="#edf1f5")
                body.barh(center + 0.11, (right - left) * n / d, left=left, height=0.045, color=color)
        position += row_height
        body.axhline(position, color="#edf1f5", linewidth=0.6)

    footer_ax = fig.add_subplot(grid[3])
    footer_ax.set_axis_off()
    footer_ax.text(0, 0, footer, va="bottom", fontsize=8, color="#64748b")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)


def plot_results(results, output, *, top_terms):
    """Plot top-K statements and exact matches from terms.py."""
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
    counts = " | ".join(
        f"{SOURCE_NAMES.get(source, source)}: {metrics['included_reports']:,} included / {metrics['input_reports']:,} input pairs"
        for source, metrics in results.items()
    )
    _plot_rates(
        results, [("edited", "Any physician edit")],
        lambda metrics, _: (metrics["edited_reports"], metrics["included_reports"]),
        title="Report edit rate", numerator="Included pairs with any statement added or deleted.",
        denominator="All included report pairs.",
        output=output / "01_edit_rate.png", note=counts,
    )
    _plot_rates(
        results, list(CHANGE_NAMES.items()),
        lambda metrics, key: (metrics["report_counts"][key], metrics["included_reports"]),
        title="Types of report changes", numerator="Included pairs in the stated change category.",
        denominator="All included report pairs.",
        output=output / "02_change_types.png",
        note="Each included pair belongs to exactly one category. " + counts,
    )
    _plot_rates(
        results, list(INPUT_NAMES.items()),
        lambda metrics, key: (metrics["input_status_counts"][key], metrics["input_reports"]),
        title="Input quality: empty, missing, and malformed reports",
        numerator="Input pairs with the stated issue. Each pair belongs to at most one issue category.",
        denominator="All input report pairs read by this analysis, before exclusions.",
        output=output / "03_input_quality.png",
        note="Missing takes priority over malformed; empty counts require two valid lists. Records removed by upstream preprocessing are not counted.",
    )
    vocabulary = set().union(*(metrics["terms"] for metrics in results.values()))
    edits = {
        term: sum(metrics["terms"][term]["edited_report_count"] for metrics in results.values())
        for term in vocabulary
    }
    ranked = sorted(vocabulary, key=lambda term: (-edits[term], term))
    reference_terms = {term for terms in TERMS.values() for term in terms}
    selections = (
        (output / "statements", ranked[:top_terms], "with the most additions + deletions across sources"),
        (output / "statements" / "terms", [term for term in ranked if term in reference_terms],
         "matching terms.py exactly"),
    )
    for directory, selected, description in selections:
        if not selected:
            continue
        rows = [(term, term) for term in sorted(selected)]
        note = (f"Showing {len(selected)} statements {description}, in alphabetical order on all statement plots. "
                "All statements remain in the saved analysis. Each source uses its own report pairs. "
                "Undefined means the denominator is zero. " + counts)

        for name, (numerator, denominator, title, interpretation, numerator_meaning, denominator_meaning) in TERM_METRICS.items():
            _plot_rates(
                results, rows,
                lambda metrics, term: (metrics["terms"][term][numerator], sum(metrics["terms"][term][key] for key in denominator)),
                title=title, numerator=numerator_meaning, denominator=denominator_meaning,
                interpretation=interpretation,
                output=directory / f"{name}.png", note=note,
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
