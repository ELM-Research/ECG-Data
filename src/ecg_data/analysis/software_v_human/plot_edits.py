"""Plot saved edits-study counts without rereading the ECG dataset."""

import json
from pathlib import Path
from textwrap import fill

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

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
    "disagreement": (
        "edited_report_count", "mentioned_report_count", "Statement disagreement",
        "Pairs where this statement was added or deleted / pairs mentioning it in either report.",
    ),
    "additions": (
        "added", "software_absent_report_count", "Physician additions",
        "Pairs where the physician added this statement / eligible pairs where software omitted it.",
    ),
    "deletions": (
        "deleted", "software_report_count", "Physician deletions",
        "Pairs where the physician deleted this statement / eligible pairs where software included it.",
    ),
}
COLORS = ("#28649b", "#c46b25", "#43816c")


def _fraction_label(numerator, denominator):
    if not denominator:
        return f"Undefined ({numerator:,} / 0)"
    value = numerator / denominator
    percentage = "<0.1%" if 0 < value < 0.001 else f"{value:.1%}"
    return f"{percentage}  ({numerator:,} / {denominator:,})"


def _plot_rates(results, rows, values, *, title, meaning, output, note=""):
    """Group sources on identical rows; label each bar with its exact fraction."""
    sources = list(results)
    labels = [fill(label, width=42) for _, label in rows]
    steps = [max(len(sources) + 0.8, (label.count("\n") + 1) * 0.7) for label in labels]
    height = max(4.2, 2.5 + sum(steps) * 0.36)
    fig, ax = plt.subplots(figsize=(15, height))
    positions = []
    position = 0
    for step in steps:
        positions.append(position)
        position += step
    for source_index, source in enumerate(sources):
        metrics = results[source]
        for index, (key, _) in enumerate(rows):
            numerator, denominator = values(metrics, key)
            value = numerator / denominator if denominator else 0
            y = positions[index] + source_index
            ax.barh(
                y, value, height=0.72, color=COLORS[source_index % len(COLORS)],
                label=SOURCE_NAMES.get(source, source) if index == 0 else None,
            )
            ax.text(1.025, y, _fraction_label(numerator, denominator),
                    transform=ax.get_yaxis_transform(), va="center", fontsize=10, clip_on=False)

    ax.set_yticks([position + (len(sources) - 1) / 2 for position in positions], labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlabel("Percentage of the stated denominator")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=12)
    ax.grid(axis="x", alpha=0.2)
    ax.set_axisbelow(True)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.025), frameon=False, ncol=len(sources))
    fig.suptitle(title, x=0.035, y=0.98, ha="left", fontsize=17, fontweight="bold")
    fig.text(0.035, 0.925, fill(meaning, 135), ha="left", va="top", fontsize=11)
    fig.text(0.035, 0.025, fill(note or "Labels show percentage (numerator / denominator).", 150),
             fontsize=10, va="bottom")
    fig.subplots_adjust(left=0.31, right=0.76, top=1 - 1.5 / height, bottom=0.85 / height)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)


def plot_results(results, output, *, top_terms, terms_per_page):
    """Keep the full saved analysis; limit only the statement plots."""
    if not results or any(metrics.get("study") != "edits" for metrics in results.values()):
        raise ValueError("Expected saved results from experiment: edits.")
    if not isinstance(top_terms, int) or top_terms < 1:
        raise ValueError("plots.top_terms must be a positive integer.")
    if not isinstance(terms_per_page, int) or terms_per_page < 1:
        raise ValueError("plots.terms_per_page must be a positive integer.")
    order = {source: index for index, source in enumerate(SOURCE_NAMES)}
    results = {source: results[source] for source in sorted(results, key=lambda source: (order.get(source, len(order)), source))}
    output = Path(output)
    cohort = " | ".join(
        f"{SOURCE_NAMES.get(source, source)}: {metrics['included_reports']:,} eligible / {metrics['input_reports']:,} input pairs"
        for source, metrics in results.items()
    )
    _plot_rates(
        results, [("edited", "Any physician edit")],
        lambda metrics, _: (metrics["edited_reports"], metrics["included_reports"]),
        title="Report edit rate", meaning="Pairs with any statement difference / all eligible report pairs.",
        output=output / "01_edit_rate.png", note=cohort,
    )
    _plot_rates(
        results, list(CHANGE_NAMES.items()),
        lambda metrics, key: (metrics["report_counts"][key], metrics["included_reports"]),
        title="Types of report changes", meaning="Pairs in each change category / all eligible report pairs.",
        output=output / "02_change_types.png",
        note="Each eligible pair belongs to exactly one category. " + cohort,
    )
    _plot_rates(
        results, list(INPUT_NAMES.items()),
        lambda metrics, key: (metrics["input_status_counts"][key], metrics["input_reports"]),
        title="Input quality: empty, missing, and malformed reports",
        meaning="Pairs with each input issue / all input pairs, counted before exclusions. Categories are mutually exclusive.",
        output=output / "03_input_quality.png",
        note="Empty counts follow report normalization. These logs cannot recover records removed by upstream preprocessing.",
    )
    vocabulary = set().union(*(metrics["terms"] for metrics in results.values()))
    edits = {
        term: sum(metrics["terms"][term]["edited_report_count"] for metrics in results.values())
        for term in vocabulary
    }
    selected = sorted((term for term in vocabulary if edits[term]), key=lambda term: (-edits[term], term))[:top_terms]
    for offset in range(0, len(selected), terms_per_page):
        page = offset // terms_per_page + 1
        rows = [(term, term) for term in selected[offset:offset + terms_per_page]]
        note = (
            f"Statements {offset + 1}–{offset + len(rows)} of {len(selected)} shown; ranked by total added + deleted counts across sources. "
            "All statements remain in the saved analysis. Sources use their own eligible denominators."
        )
        for name, (numerator, denominator, title, meaning) in TERM_METRICS.items():
            _plot_rates(
                results, rows,
                lambda metrics, term: (metrics["terms"][term][numerator], metrics["terms"][term][denominator]),
                title=title, meaning=meaning,
                output=output / "statements" / f"page_{page:02d}" / f"{name}.png", note=note,
            )
    print(f"Saved edits-study figures to {output}")


if __name__ == "__main__":
    cfg = get_config()
    if cfg["experiment"] != "edits":
        raise ValueError("These plots require experiment: edits.")
    root = Path(cfg["save_path"]) / "edits"
    results = json.loads((root / f"{cfg['data_name']}.json").read_text())
    plot_results(results, root / "figures" / cfg["data_name"], **cfg["plots"])
