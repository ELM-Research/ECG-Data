# Software versus physician reports

Set `data_path` and `save_path` in the analysis configuration, then run:

```sh
uv run python -m ecg_data.analysis.software_v_human.main \
  --config src/ecg_data/analysis/config/software_v_human_heedb.yaml
```

For AGH, use `software_v_human_agh.yaml` instead. Its configuration remains
gitignored; create it locally with:

```yaml
defaults:
  - ./common.yaml
data_name: agh
data_path: /batch_data/agh/filtered_batch_meta_data_v3
```

HEEDB reads `*/*.npy` once per file; AGH reads JSON arrays in `*.json`.

| Output directory | Software field | Physician field |
| --- | --- | --- |
| `agh` | `OriginalDiagnosis` | `Diagnosis` |
| `heedb_old` | `reports_software_old` | `reports_physician` |
| `heedb_new` | `reports_software_new` | `reports_physician` |

## Reading the results

Each comparison writes these files under `save_path`:

| File | Contents |
| --- | --- |
| `overview.png` | Terms with edits, ranked by edit count: addition and deletion percentages, with N beside each bar. |
| `terms_<category>.png` | All 69 terms, grouped by category, using the same two plots. |
| `overview_error_rates.png`, `terms_<category>_error_rates.png` | The same plots using false negative and false positive rates. |
| `all_reports/` | Shared-denominator disagreement plots and `disagreement.csv`, including unchanged reports. |
| `counts.csv` | Before/after term frequencies and report counts. |
| `prevalence.csv` | Before/after proportions and the cohort's report count. |
| `changes.csv` | The four presence groups and addition/deletion ratios. |
| `summary.json` | Total, analyzed, excluded, unchanged, and modified report counts. |

The addition/deletion and error-rate figures use **modified reports only**, as in
the paper's term-change analysis. The `all_reports/` figures use **all reports**.
The overview ranks terms by added + deleted reports, not net change or percentage.
The category plots include unobserved terms.
Bar height shows the percentage; **N** is the number of reports with that edit.
Addition percentages use originally absent reports; deletion percentages use
originally present reports. Both use the modified cohort only.

The new plots treat physician term presence as the reference:
- False negative rate = added / (retained + added).
- False positive rate = deleted / (deleted + never present).

Initial presence + added - deleted equals final presence; this is the false
negative denominator only. These rates describe **modified reports only**.

Generate all three analyses together from existing counts without rerunning analysis:

```sh
uv run python -m ecg_data.analysis.software_v_human.results_interpreter /path/to/results
```

The input CSVs have one row per term and cohort: `all`, `unchanged`, or `modified`.
Filter `cohort` to `modified` for the addition/deletion and error-rate figures,
or `all` for the disagreement figures. Filter to `unchanged` and
`modified` in `prevalence.csv` to compare term proportions between report groups.
Ratios and proportions are fractions from 0 to 1; charts display percentages.
Undefined ratios are blank in CSV, `null` in JSON, and `n/a` in charts.

These three tables replace the wide `terms.csv`; every previous metric is retained.
Old output files are not removed. Use a fresh output directory to avoid mixing runs.

## Disagreement across all reports

The same `results_interpreter` command also writes `all_reports/disagreement.csv`,
`all_reports/overview.png`, and `all_reports/terms_<category>.png` in each comparison
directory (`agh`, `heedb_old`, or `heedb_new`). This analysis includes unchanged reports.

For each term, the shared denominator is **retained + deleted + added**: reports
where either software or physician includes the term. Reports with neither are
excluded from this denominator. The CSV includes all four counts, the full cohort
size (`report_count`), and the shared denominator (`either_report_count`).

- `missed_ratio` = added / denominator: the physician added the term.
- `extra_ratio` = deleted / denominator: the physician removed the term.
- `disagreement_ratio` = (added + deleted) / denominator: term presence differs.

The two plots share an axis scale and show missed and extra percentages;
their sum is total disagreement.
The overview ranks by addition + deletion count; category plots include all terms.
Zero denominators produce blank CSV ratios and `n/a` in category plots.
These are not standard false negative and false positive rates. They match the
previous script's per-term bar denominators, while retaining current phrase matching
and input exclusions. This does not reproduce its whole-report `All` bar.

## Counting rules

The terms and category assignments match Supplemental Table S1 of
[Chiu et al., DOI 10.1093/ehjdh/ztaf119](https://doi.org/10.1093/ehjdh/ztaf119).
The calculations implement the paper's term-frequency and modification definitions.
They do not reproduce its physician exclusions, sampling, or other statistical analyses.

- A report is **modified** if the complete original and final texts differ,
  including case, whitespace, order, or repeated mentions. List-valued reports
  are joined with spaces before comparison.
- For term matching, ignore case and collapse whitespace. Match the 69 whole
  phrases without synonyms. The paper does not specify its exact matching code.
- Repeated mentions count toward term frequency; each report counts only once
  toward term presence. Matches include suspected, negated, and historical mentions.
- Exclude pairs with a missing/null report. Empty reports and pairs containing
  no listed terms remain in the analysis and its denominators.
- For each term: retained = present in both; deleted = original only;
  added = final only; never present = absent from both. These four counts sum
  to the cohort's report count. A retained term can occur in a modified report.
- A report replacing one term with another counts as one deletion and one
  addition, under their respective terms. A single term cannot be both within
  the same report pair; changing repeated mentions alone is neither.
- Added ratio = added / (added + never present).
  Deleted ratio = deleted / (retained + deleted).
- Prevalence = reports containing the term / all analyzed reports in that cohort.
  All 69 terms have rows, including terms with zero occurrences.
