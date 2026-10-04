import argparse
import csv
import json
from math import isfinite
from pathlib import Path
import re

from ecg_data.analysis.software_v_human.terms import TERMS
from ecg_data.analysis.software_v_human.metrics import Ratio, proportion, term_metrics

GROUPS = ("group_1_retained", "group_2_deleted", "group_3_added", "group_4_never_present")
_TP, _FP, _FN, _TN = GROUPS
_TERM_ORDER = {term: index for index, term in enumerate(term for terms in TERMS.values() for term in terms)}
MATCHING = {
    "exact_statement": (
        "Exact statements",
        "Each complete list item or line must equal a listed term after lowercasing and collapsing whitespace. "
        "Negation, qualifiers, extra punctuation, and combined statements prevent a match.",
    ),
    "phrase": (
        "Whole phrases (non-exact)",
        "Search the lowercased, whitespace-normalized full report for each term with word boundaries, "
        "as in the earlier analysis. Lists are joined with spaces. Qualifiers and negations do not prevent a match: "
        "'no atrial fibrillation' contains 'atrial fibrillation'.",
    ),
}
# Plot definitions contain only the saved metric, title, and axis explanation.
METRICS = {
    "edits": (
        ("added_report_ratio", "Added by physician", "% of software-negative reports"),
        ("deleted_report_ratio", "Removed by physician", "% of software-positive reports"),
    ),
    "error_rates": (
        ("false_negative_rate", "Missed by software (FNR)", "% of physician-positive reports"),
        ("false_positive_rate", "Extra in software (FPR)", "% of physician-negative reports"),
    ),
    "disagreement": (
        ("missed_ratio", "Software missed", "% of reports with the term in either report"),
        ("extra_ratio", "Software extra", "% of reports with the term in either report"),
    ),
    "benchmark": (
        ("precision", "Precision: supported software terms", "TP / (TP + FP); higher is better"),
        ("recall", "Recall: captured physician terms", "TP / (TP + FN); higher is better"),
        ("f1", "F1: precision and recall combined", "2TP / (2TP + FP + FN); higher is better"),
    ),
    "reference": (
        ("missed_per_reference", "Missed / physician-positive", "Misses per 100 physician-positive reports"),
        ("extra_per_reference", "Extra / physician-positive", "Extras per 100 physician-positive reports"),
    ),
    "counts": (
        ("original_term_frequency", "Original term frequency", "Matched occurrences before review"),
        ("final_term_frequency", "Final term frequency", "Matched occurrences after review"),
        ("original_report_count", "Original report count", "Reports containing the term before review"),
        ("final_report_count", "Final report count", "Reports containing the term after review"),
    ),
    "groups": (
        (_TP, "Retained (TP)", "Reports"),
        (_FP, "Deleted (FP)", "Reports"),
        (_FN, "Added (FN)", "Reports"),
        (_TN, "Absent from both (TN)", "Reports"),
    ),
    "prevalence": (
        ("unchanged_original_proportion", "Unchanged: before review", "% of textually unchanged reports"),
        ("modified_original_proportion", "Modified: before review", "% of textually modified reports"),
        ("unchanged_final_proportion", "Unchanged: after review", "% of textually unchanged reports"),
        ("modified_final_proportion", "Modified: after review", "% of textually modified reports"),
    ),
}

def _label(value):
    if not isinstance(value, Ratio):
        return f"{value:,}"
    percent = f"{value.value:.1%}" if value.value is not None else "n/a"
    return f"{percent} ({value.numerator:,} / {value.denominator:,})"


def _comparison_label(path, summary):
    return f"{summary.get('comparison', path.name)} | {MATCHING[summary['term_matching']][0]}"


def _upper(value):
    if not isinstance(value, Ratio):
        return value
    high = value.high if value.high is not None and isfinite(value.high) else 0
    return max(value.value or 0, high)


def _draw_bars(axis, values, *, unit, color, peak):
    from matplotlib.ticker import MaxNLocator, PercentFormatter

    points = [(value.value or 0) if isinstance(value, Ratio) else value for value in values]
    axis.barh(range(len(values)), points, height=0.6, color=color)
    for index, value in enumerate(values):
        if isinstance(value, Ratio) and value.low is not None:
            high = value.high if isfinite(value.high) else peak
            axis.hlines(index, value.low, high, color="#333333", linewidth=1)
            axis.plot([value.low, high], [index, index], "|", color="#333333")
        label = _label(value)
        if isinstance(value, Ratio) and value.high is not None and not isfinite(value.high):
            label += " (CI upper bound unbounded)"
        axis.text(_upper(value) + peak * 0.03, index, label, va="center", fontsize=9)

    axis.set_xlim(0, peak * 1.85)
    ticks = MaxNLocator(nbins=3, integer=unit == "count").tick_values(0, peak)
    axis.set_xticks([tick for tick in ticks if 0 <= tick <= peak])
    if unit == "ratio":
        axis.xaxis.set_major_formatter(PercentFormatter(1))
    axis.set_axisbelow(True)
    axis.grid(axis="x", color="#e6e9ec", linewidth=0.6)
    axis.tick_params(axis="both", length=0, labelsize=9)
    for spine in axis.spines.values():
        spine.set_visible(False)


def plot_changes(path, summary, rows, title, metric="edits", *, cohort="modified", sharex=False):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    metrics = METRICS[metric]
    unit = "count" if metric in ("counts", "groups") else "ratio"
    count = summary["analyzed_reports"] if cohort == "all" else summary[f"{cohort}_reports"]
    cohort_label = "all analyzed" if cohort == "all" else cohort
    figure = Figure(figsize=(8 * len(metrics), max(3.5, 2.5 + len(rows) * 0.45)), layout="constrained")
    FigureCanvasAgg(figure)
    figure.suptitle(f"{_comparison_label(path, summary)} | {title}\n{count:,} {cohort_label} reports", fontsize=12)
    axes = figure.subplots(1, len(metrics), sharey=True, sharex=sharex)
    shared_peak = max((_upper(row[key]) for row in rows for key, _, _ in metrics), default=0) or 1

    for axis, (key, axis_title, axis_label), color in zip(
        axes, metrics, ("#288274", "#bb643f", "#4c78a8", "#8764a0"),
    ):
        values = [row[key] for row in rows]
        peak = shared_peak if sharex else max((_upper(value) for value in values), default=0) or 1
        _draw_bars(axis, values, unit=unit, color=color, peak=peak)
        axis.set_title(axis_title, loc="left", fontsize=12, weight="bold")
        axis.set_xlabel(axis_label, fontsize=10)
        if not rows:
            axis.text(0.5, 0.5, "No terms for this overview.", transform=axis.transAxes, ha="center")

    axes[0].set_yticks(range(len(rows)), [row["term"] for row in rows])
    axes[0].set_ylim(max(1, len(rows)) - 0.5, -0.5)
    note = "Term agreement with physician reports; clinical correctness is not established."
    if unit == "ratio":
        note += "\nLabels: % (numerator / denominator). Lines: pointwise 95% CI, assuming independent ECGs. n/a: zero denominator."
    figure.supxlabel(note, fontsize=9, color="#58616b")
    return figure


def _load_cohorts(path):
    with (path / "counts.csv").open() as file:
        counts = {
            (row["cohort"], row["term"]): {
                key: int(value) for key, value in row.items()
                if key not in ("cohort", "category", "term")
            }
            for row in csv.DictReader(file)
        }
    with (path / "changes.csv").open() as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for key in GROUPS:
            row[key] = int(row[key])
        row.update(counts[(row["cohort"], row["term"])])
        row["report_count"] = sum(row[key] for key in GROUPS)
        row["either_report_count"] = row[_TP] + row[_FP] + row[_FN]
        row["physician_positive_count"] = row[_TP] + row[_FN]
        row.update(term_metrics(row[_TP], row[_FP], row[_FN], row[_TN]))
    rows.sort(key=lambda row: _TERM_ORDER[row["term"]])
    cohorts = {
        cohort: [row for row in rows if row["cohort"] == cohort]
        for cohort in ("all", "unchanged", "modified")
    }
    for cohort, cohort_rows in cohorts.items():
        if not cohort_rows:
            raise ValueError(f"No '{cohort}' cohort in {path / 'changes.csv'}; rerun analysis.")
    return cohorts


def _prevalence_rows(cohorts):
    rows = {row["term"]: row.copy() for row in cohorts["all"]}
    for cohort in ("unchanged", "modified"):
        for row in cohorts[cohort]:
            target = rows[row["term"]]
            target[f"{cohort}_original_proportion"] = proportion(row["original_report_count"], row["report_count"])
            target[f"{cohort}_final_proportion"] = proportion(row["final_report_count"], row["report_count"])
    return list(rows.values())


def _save_term_plots(path, summary, rows, output, metric, cohort, suffix, title):
    output.mkdir(exist_ok=True)
    if metric in ("edits", "disagreement", "reference") or (metric == "error_rates" and cohort == "modified"):
        overview = [row for row in rows if row[_FP] + row[_FN]]
    else:
        overview = [row for row in rows if row["either_report_count"]]
    plots = [("overview", title, overview)]
    for category in dict.fromkeys(row["category"] for row in rows):
        terms = [row for row in rows if row["category"] == category]
        filename = re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_")
        plots.append((f"terms_{filename}", f"{title} | {category}", terms))
    for filename, plot_title, terms in plots:
        figure = plot_changes(
            path, summary, terms, plot_title, metric, cohort=cohort, sharex=cohort == "all",
        )
        figure.savefig(output / f"{filename}{suffix}.png", dpi=180)
        figure.clear()


def _save_csv(path, rows, fields, *, ratios=()):
    fields = (*fields, *(column for key in ratios for column in (key, f"{key}_ci_low", f"{key}_ci_high")))
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            record = row.copy()
            for key in ratios:
                rate = row[key]
                record[key] = rate.value
                record[f"{key}_ci_low"] = rate.low
                record[f"{key}_ci_high"] = rate.high
            writer.writerow(record)


def _plot_reports(path, summary):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    output = path / "reports"
    output.mkdir(exist_ok=True)
    plots = [("text_changes", "Whole-report textual changes", {
        "Unchanged text": summary["unchanged_reports"],
        "Modified text": summary["modified_reports"],
    })]
    counts = summary.get("term_change_reports")
    if counts is None:
        print(f"{path}: rerun analysis for report-level term changes; per-term totals cannot recover them.")
    else:
        plots.append(("term_changes", "Report patterns across the 69 terms", {
            "No term presence change": counts["no_term_change"],
            "Addition only": counts["addition_only"],
            "Deletion only": counts["deletion_only"],
            "Both addition and deletion": counts["both"],
        }))

    total = summary["analyzed_reports"]
    records = []
    for filename, title, counts in plots:
        values = [proportion(count, total) for count in counts.values()]
        figure = Figure(figsize=(12, 4), layout="constrained")
        FigureCanvasAgg(figure)
        axis = figure.subplots()
        _draw_bars(axis, values, unit="ratio", color="#288274", peak=1)
        axis.set_yticks(range(len(counts)), list(counts))
        axis.invert_yaxis()
        axis.set_xlabel("% of all analyzed reports")
        axis.set_title(f"{_comparison_label(path, summary)} | {title}\n{total:,} analyzed reports")
        figure.supxlabel(
            "Lines: pointwise 95% CI, assuming independent ECGs. No term presence change can include textual edits.",
            fontsize=9,
        )
        figure.savefig(output / f"{filename}.png", dpi=180)
        figure.clear()
        records.extend({"analysis": filename, "pattern": label, "count": count,
                        "report_count": total, "proportion": value}
                       for (label, count), value in zip(counts.items(), values))
    _save_csv(output / "metrics.csv", records, ("analysis", "pattern", "count", "report_count"), ratios=("proportion",))


def _write_guide(path, summary, rows):
    review = path / "benchmark" / "clinical_review.csv"
    if not review.exists():
        _save_csv(review, rows, (
            "category", "term", "miss_consequence", "extra_consequence",
            "reference_validation", "evidence", "reviewer",
        ))

    patterns = "[Term-change patterns](reports/term_changes.png)"
    if "term_change_reports" not in summary:
        patterns = "Term-change patterns unavailable: rerun the main analysis."
    matching_label, matching_description = MATCHING[summary["term_matching"]]
    text = f"""# {_comparison_label(path, summary)}: start here

These results measure **term agreement with physician reports**, using **{matching_label.lower()}**.
They do not establish clinical correctness or patient benefit.

{matching_description}

**{summary['analyzed_reports']:,} analyzed reports**; {summary['excluded_reports']:,} excluded for missing reports.
{summary['unchanged_reports']:,} were textually unchanged and {summary['modified_reports']:,} were modified.
{summary['reports_without_listed_terms']:,} contained none of the 69 listed terms in either version; these remain in the denominators.

## Choose the question

| Question | Open | Reports included |
| --- | --- | --- |
| How well does software agree with the physician's terms? | [Precision, recall, F1](benchmark/overview.png) · [miss/extra rates](benchmark/overview_error_rates.png) · [counts and 95% intervals](benchmark/metrics.csv) | All analyzed |
| Which terms need clinical review? | [Finding-specific results](benchmark/metrics.csv) · [clinician review worksheet](benchmark/clinical_review.csv) | All analyzed |
| How often was a report changed? | [Text changes](reports/text_changes.png) · {patterns} · [counts and intervals](reports/metrics.csv) | All analyzed |
| What were the study's modification patterns? | [Added/deleted ratios](overview.png) · [frequencies and report counts](study/overview_counts.png) · [four groups](study/overview_groups.png) | Modified only |
| How does term prevalence differ between report groups? | [Prevalence](study/overview_prevalence.png) | Unchanged and modified, separately |
| What did the advisor's denominator measure? | [Misses/extras per physician-positive](physician_reference/overview.png) · [counts and intervals](physician_reference/metrics.csv) | All analyzed |
| What were the earlier alternative metrics? | [Shared-denominator disagreement](all_reports/overview.png) · [modified-only error rates](overview_error_rates.png) | All analyzed / modified only, respectively |

Every term plot also has category files named `terms_<category>*.png` in the same folder.
Category plots retain all 69 terms, including terms with no observed positives.
Benchmark overviews include every observed term, even when no edits occurred.
Other edit/disagreement overviews show edited terms only.

## Read a result

- **TP / retained:** both reports include the term.
- **FN / added:** only the physician includes it; software missed it.
- **FP / deleted:** only software includes it; software reported an extra term.
- **TN / neither:** neither report includes the term.
- **Precision:** of software's positive statements, how many agree with the reference?
- **Recall:** of physician-positive statements, how many did software capture?
- **F1:** combines precision and recall. Higher is better; inspect each term, including uncommon findings.
- **False negative rate:** missed / physician-positive. Lower is better.
- **False positive rate:** extra / physician-negative. Lower is better.

Labels show the percentage and actual numerator / denominator. A zero denominator is `n/a`, not zero performance.
Lines show pointwise 95% confidence intervals; CSV columns ending `_ci_low` and `_ci_high` contain the limits.
Wide intervals mean greater sampling uncertainty. Zero observed errors do not establish a zero error rate.

The advisor's denominator is `initial presence + added - deleted = TP + FN`.
Both ratios use this denominator. The extra-term ratio is **not** a false positive rate and can exceed 100%.

## Clinical interpretation needs review

Use the clinician worksheet to record each finding's consequences if missed or falsely reported,
the evidence for those judgments, and validation of the reference labels. Its contents are preserved on reruns.
**These judgments are not supplied by the term counts.** The worksheet starts blank; it does not certify validation.
High disagreement does not by itself establish clinical harm, and low disagreement does not establish safety.

There is no synonym expansion in either mode: `AF` is not mapped to `atrial fibrillation`.
Exact matching rejects negated or qualified statements; phrase matching can count those mentions as present.
Only the 69 listed terms are evaluated, under the matching rule above.
An absent physician term is treated as negative for this comparison; clinical absence is not independently verified.
A retained physician term may still be wrong. If physicians edited MUSE output, independent adjudication is needed to assess that dependence.

## Interval assumptions

Intervals assume independent ECG report pairs and are not adjusted for repeated patients, sites, or multiple comparisons.
They measure sampling uncertainty, not reference-label or extraction errors. Patient identifiers are needed for patient-clustered intervals.
For software comparisons, use the same ECGs, reference labels, and matching rules; overlapping intervals are not a paired comparison test.

Proportions use [95% Wilson score intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
F1 uses the monotone transformation `2J/(1+J)` of Wilson limits for `J = TP/(TP+FP+FN)`.
The advisor's extra ratio uses the [odds transformation](https://fingertips.phe.org.uk/static-reports/public-health-technical-guidance/Basic_statistics/Proportions.html)
of Wilson limits for `FP/(TP+FP+FN)`. F1's doubled TP count is not treated as additional independent observations.

See [standard metric definitions](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_fscore_support.html)
and [FDA guidance on agreement versus correctness](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/statistical-guidance-reporting-results-studies-evaluating-diagnostic-tests-guidance-industry-and-fda).
"""
    (path / "START_HERE.md").write_text(text)


def render_results(path):
    summary = json.loads((path / "summary.json").read_text())
    if summary.get("term_matching") not in MATCHING:
        raise ValueError(f"{path}: missing or unknown matching mode; rerun the main analysis.")
    cohorts = _load_cohorts(path)
    prevalence = _prevalence_rows(cohorts)
    views = (
        ("edits", "modified", path, "", "Physician edits"),
        ("error_rates", "modified", path, "_error_rates", "Error rates within modified reports"),
        ("disagreement", "all", path / "all_reports", "", "Term disagreement"),
        ("counts", "modified", path / "study", "_counts", "Study term frequencies and report counts"),
        ("groups", "modified", path / "study", "_groups", "Study term presence groups"),
        ("prevalence", "all", path / "study", "_prevalence", "Term prevalence by textual cohort"),
        ("benchmark", "all", path / "benchmark", "", "Software agreement with physician reports"),
        ("error_rates", "all", path / "benchmark", "_error_rates", "Software error rates"),
        ("groups", "all", path / "benchmark", "_counts", "Software confusion counts"),
        ("reference", "all", path / "physician_reference", "", "Errors per physician-positive report"),
    )
    for metric, cohort, output, suffix, title in views:
        rows = prevalence if metric == "prevalence" else cohorts[cohort]
        _save_term_plots(path, summary, rows, output, metric, cohort, suffix, title)

    fields = (
        "cohort", "category", "term", "report_count", *GROUPS,
        "either_report_count",
    )
    _save_csv(path / "all_reports" / "disagreement.csv", cohorts["all"], fields, ratios=(
        "missed_ratio", "extra_ratio", "disagreement_ratio",
    ))
    fields = ("cohort", "category", "term", "report_count", *GROUPS, "physician_positive_count")
    _save_csv(path / "benchmark" / "metrics.csv", cohorts["all"], fields, ratios=(
        "precision", "recall", "f1", "false_negative_rate", "false_positive_rate",
    ))
    _save_csv(path / "physician_reference" / "metrics.csv", cohorts["all"], fields, ratios=(
        "missed_per_reference", "extra_per_reference",
    ))
    _save_csv(path / "study" / "metrics.csv", cohorts["modified"], fields, ratios=(
        "added_report_ratio", "deleted_report_ratio", "false_negative_rate", "false_positive_rate",
    ))
    _save_csv(path / "study" / "prevalence.csv", prevalence, ("category", "term"), ratios=(
        "unchanged_original_proportion", "modified_original_proportion",
        "unchanged_final_proportion", "modified_final_proportion",
    ))
    _plot_reports(path, summary)
    _write_guide(path, summary, cohorts["all"])


def _compare_matching(path):
    directories = {mode: path / mode for mode in MATCHING}
    if not all((directory / "changes.csv").is_file() for directory in directories.values()):
        return
    summaries = {mode: json.loads((directory / "summary.json").read_text()) for mode, directory in directories.items()}
    for mode, summary in summaries.items():
        if summary.get("term_matching") != mode:
            raise ValueError(f"{path / mode}: matching mode does not match its directory.")
    exact_summary, phrase_summary = summaries["exact_statement"], summaries["phrase"]
    if not exact_summary.get("run_id") or exact_summary["run_id"] != phrase_summary.get("run_id"):
        raise ValueError(f"{path}: matching modes came from different runs; rerun analysis together.")
    for key in ("total_reports", "analyzed_reports", "excluded_reports", "modified_reports", "unchanged_reports"):
        if exact_summary[key] != phrase_summary[key]:
            raise ValueError(f"{path}: matching modes have different {key}; rerun analysis together.")

    cohorts = {mode: _load_cohorts(directory) for mode, directory in directories.items()}
    measures = (
        "original_term_frequency", "final_term_frequency", "original_report_count", "final_report_count",
        *GROUPS, "added_report_ratio", "deleted_report_ratio", "precision", "recall", "f1",
        "false_negative_rate", "false_positive_rate", "missed_per_reference", "extra_per_reference",
        "missed_ratio", "extra_ratio", "disagreement_ratio",
    )
    differences = []
    for cohort in ("all", "unchanged", "modified"):
        phrase_rows = {row["term"]: row for row in cohorts["phrase"][cohort]}
        for exact in cohorts["exact_statement"][cohort]:
            phrase = phrase_rows[exact["term"]]
            for key in measures:
                left, right = exact[key], phrase[key]
                unit = "count"
                if isinstance(left, Ratio):
                    left = 100 * left.value if left.value is not None else None
                    right = 100 * right.value if right.value is not None else None
                    unit = "percent"
                differences.append({
                    "cohort": cohort, "category": exact["category"], "term": exact["term"],
                    "metric": key, "unit": unit, "exact_statement": left, "phrase": right,
                    "phrase_minus_exact": right - left if left is not None and right is not None else None,
                })
    _save_csv(path / "matching_comparison.csv", differences, (
        "cohort", "category", "term", "metric", "unit", "exact_statement", "phrase", "phrase_minus_exact",
    ))

    table = ["| Term | Exact FN / FP | Phrase FN / FP | Exact F1 | Phrase F1 |",
             "| --- | --- | --- | --- | --- |"]
    phrase_rows = {row["term"]: row for row in cohorts["phrase"]["all"]}
    for exact in cohorts["exact_statement"]["all"]:
        phrase = phrase_rows[exact["term"]]
        if not exact["either_report_count"] and not phrase["either_report_count"]:
            continue
        scores = [f"{row['f1'].value:.1%}" if row["f1"].value is not None else "n/a" for row in (exact, phrase)]
        table.append(f"| {exact['term']} | {exact[_FN]} / {exact[_FP]} | {phrase[_FN]} / {phrase[_FP]} | {scores[0]} | {scores[1]} |")
    table_text = "\n".join(table)
    (path / "START_HERE.md").write_text(f"""# {path.name}: compare matching rules

Both modes used the same **{exact_summary['analyzed_reports']:,} analyzed reports**, exclusions, and textual modified/unchanged split.

| Mode | Rule | Open |
| --- | --- | --- |
| Exact statements | The complete statement must equal a listed term. | [Guide](exact_statement/START_HERE.md) · [benchmark](exact_statement/benchmark/overview.png) |
| Whole phrases (non-exact) | A listed term may appear within a longer statement, including a negation. | [Guide](phrase/START_HERE.md) · [benchmark](phrase/benchmark/overview.png) |

Both lowercase and collapse whitespace. Neither expands synonyms.
For example, `no atrial fibrillation` matches `atrial fibrillation` only in phrase mode.

[Download all count and metric differences](matching_comparison.csv).
Filter by cohort, term, and metric. `phrase_minus_exact` is the change from exact to phrase matching;
for percentage metrics this is a **percentage-point** change. Undefined values remain blank, not zero.
Each mode's guide links its full study, report-change, benchmark, and physician-reference outputs, including 95% intervals.

## Quick comparison: all reports

FN = physician-only term; FP = software-only term. The table includes terms observed under either rule.

{table_text}

Changing the rule changes extraction from **both software and physician reports**.
A higher F1 under one rule does not prove greater clinical correctness.
Differences are descriptive; no confidence interval or significance test for the paired difference is inferred from marginal counts.
Older result files at this directory's root are not part of these two analyses.
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths", nargs="*", type=Path, default=[Path(__file__).parent / "results"],
        help="A matching-mode directory, comparison directory, or results root (default: results beside this script).",
    )
    args = parser.parse_args()
    for path in args.paths:
        candidates = {file.parent for file in path.rglob("changes.csv")}
        directories = sorted(directory for directory in candidates if not any(directory / mode in candidates for mode in MATCHING))
        if not directories:
            parser.error(f"No changes.csv found under {path}.")
        for directory in directories:
            render_results(directory)
            print(f"Saved interpretations: {directory / 'START_HERE.md'}")
        for comparison in sorted({directory.parent for directory in directories if directory.name in MATCHING}):
            _compare_matching(comparison)
