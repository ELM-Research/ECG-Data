# Software versus physician reports

This analysis measures **term agreement with physician reports** under two matching rules.
It does not establish clinical correctness or patient benefit.

## Run

Set `data_path` and `save_path` in the configuration, then run:

```sh
uv run python -m ecg_data.analysis.software_v_human.main \
  --config src/ecg_data/analysis/config/software_v_human_heedb.yaml

uv run python -m ecg_data.analysis.software_v_human.results_interpreter /path/to/results
```

Open **`START_HERE.md`** in each comparison directory. It explains the results,
compares matching modes, and links their separate plots and tables.
All plotting happens in the interpreter; the main analysis only saves counts.
Each input file is loaded once. Both modes use the same report pairs, exclusions,
and textual modified/unchanged cohorts.

```text
heedb_new/
  START_HERE.md                 # Side-by-side FN, FP, and F1
  matching_comparison.csv       # All counts and metrics, by term and cohort
  exact_statement/              # Complete statements must match
  phrase/                       # Terms may occur within longer statements
```

Each mode contains its own raw counts, `START_HERE.md`, study plots, benchmark
plots, report-pattern plots, physician-reference ratios, and confidence intervals.
The interpreter accepts the results root, a comparison directory, or a mode directory.

For AGH, create the gitignored `software_v_human_agh.yaml` locally:

```yaml
defaults:
  - ./common.yaml
data_name: agh
data_path: /batch_data/agh/filtered_batch_meta_data_v3
```

HEEDB reads `*/*.npy`; AGH reads JSON arrays in `*.json`.

| Comparison | Software field | Physician field |
| --- | --- | --- |
| `agh` | `OriginalDiagnosis` | `Diagnosis` |
| `heedb_old` | `reports_software_old` | `reports_physician` |
| `heedb_new` | `reports_software_new` | `reports_physician` |

**Rerun analysis once to generate both modes.** Comparison requires results from
the same analysis run; a saved run identifier prevents mixing different cohorts.
After that rerun, interpretation changes need only the saved files.
Old single-mode files at the comparison root are left untouched and ignored when
the new mode directories exist.

`matching_comparison.csv` reports exact and phrase values and `phrase_minus_exact`.
Counts stay counts; ratios are percentages, with differences in percentage points.
Undefined values remain blank. The comparison is descriptive, not a paired
significance test. Matching changes extraction from the physician reference too,
so higher agreement under one mode does not establish greater clinical accuracy.

## Matching and counting

The 69 terms and nine categories come from Supplemental Table S1 of
[Chiu et al.](https://doi.org/10.1093/ehjdh/ztaf119).
The study's requested counting formulas and textual cohorts are retained.
Both matching variants are retained; the paper does not
publish enough matching code to claim an exact reproduction of its extraction.
Its physician exclusions, sampling, and other statistical analyses are not reproduced.

- Compare complete original and final texts to classify reports as textually
  `unchanged` or `modified`. Lists are joined with spaces for this comparison.
- **Exact statement:** each list item or line of a string report must equal a
  listed term after lowercasing and collapsing whitespace. Qualifiers,
  punctuation, and multiple findings within one statement prevent a match.
- **Phrase:** restore the earlier word-boundary phrase search over normalized
  full report text, joining lists with spaces. A term can match inside a longer,
  negated, suspected, or historical statement. This is not fuzzy matching.
- Neither mode expands synonyms. `no atrial fibrillation` matches
  `atrial fibrillation` only in phrase mode; `AF` matches it in neither mode.
- Repeated matching statements or phrase occurrences count toward frequency. Term presence counts
  once per ECG. Unlisted statements are outside the benchmark.
- Exclude pairs with missing/null reports. Keep empty reports and reports with
  no listed terms. Summaries report those counts explicitly.
- For each term: retained = TP, deleted = FP, added = FN, absent from both = TN.
  These four counts sum to the number of analyzed reports in the cohort.

Whole-report term patterns are addition only, deletion only, both, or
**no term presence change**. They use all 69 terms and all analyzed reports.
No term presence change can include textual edits; it is not the study's
textually unchanged group. The two classifications are plotted separately.

## Outputs

Within each matching-mode directory, saved data remain `counts.csv`, `prevalence.csv`,
`changes.csv`, and `summary.json`. Each term table contains `all`, `unchanged`,
and `modified` cohorts. The paths below are relative to that mode directory.

| Output | What it shows | Cohort |
| --- | --- | --- |
| Root `overview.png`, `terms_<category>.png` | Study added/deleted ratios | Modified |
| Root `*_error_rates.png` | Earlier modified-only error rates | Modified |
| `study/*_counts.png` | Four before/after term-frequency and report-count metrics | Modified |
| `study/*_groups.png` | Four term-presence groups | Modified |
| `study/*_prevalence.png` | Before/after prevalence in both textual cohorts | Each cohort separately |
| `reports/` | Textual changes and report-level term patterns | All |
| `benchmark/` | Precision, recall, F1, error rates, and confusion counts per term | All |
| `physician_reference/` | Misses and extras divided by physician-positive count | All |
| `all_reports/` | Earlier shared-denominator disagreement | All |

Term plots retain the order in `terms.py`. Category plots include all terms.
Benchmark overviews include every observed term, including perfect agreement.
Edit/disagreement overviews show edited terms only; count/prevalence overviews
show observed terms. Undefined ratios are blank in CSV and `n/a` in plots.

`benchmark/metrics.csv`, `physician_reference/metrics.csv`, `study/metrics.csv`,
`study/prevalence.csv`, `reports/metrics.csv`, and `all_reports/disagreement.csv`
include 95% interval columns ending `_ci_low` and `_ci_high`.
Plot labels show numerator/denominator; horizontal lines show those intervals.

`benchmark/clinical_review.csv` is a clinician worksheet for consequences of
misses/extras, reference-label validation, evidence, and reviewer names.
It starts blank and is never overwritten. Counts cannot supply these judgments.

Old generated files are not deleted. Use a fresh result directory after changing
matching rules, and follow `START_HERE.md` for the current outputs.

## Formulas

All formulas below use **per-term ECG counts**, not repeated-mention frequencies
or averages of per-report ratios. Physician term presence is the chosen reference.

| Metric | Formula |
| --- | --- |
| Study added ratio | FN / (FN + TN) |
| Study deleted ratio | FP / (TP + FP) |
| Precision | TP / (TP + FP) |
| Recall | TP / (TP + FN) |
| F1 | 2TP / (2TP + FP + FN) |
| False negative rate | FN / (TP + FN) |
| False positive rate | FP / (FP + TN) |
| Advisor: missed per reference | FN / (TP + FN) |
| Advisor: extra per reference | FP / (TP + FN) |
| Earlier shared-denominator missed / extra | FN or FP / (TP + FP + FN) |

The advisor's denominator is `initial presence + added - deleted = TP + FN`.
Its extra ratio is not a false positive rate and can exceed 100%.
Precision, recall, and F1 follow the
[standard definitions](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_fscore_support.html).

## Confidence intervals and clinical limits

`metrics.py` computes pointwise 95% intervals:

- Proportions: [Wilson score intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
- F1: Wilson limits for `J = TP/(TP+FP+FN)`, transformed by `2J/(1+J)`.
  Doubling TP in F1 does not create more independent observations.
- Extra per reference: Wilson limits for `FP/(TP+FP+FN)`, transformed to
  [odds](https://fingertips.phe.org.uk/static-reports/public-health-technical-guidance/Basic_statistics/Proportions.html).
- Zero denominators: estimate and interval undefined.

These intervals assume independent ECG pairs. They do not adjust for repeated
patients, sites, or multiple comparisons. Patient-level identifiers are needed
for patient-clustered intervals. Intervals describe sampling uncertainty, not
errors in physician labels or extraction. Compare software on the same ECGs
and references; interval overlap is not a paired comparison test.

A missing physician term is treated as negative for this benchmark; clinical
absence is not independently verified. Exact matching avoids substring errors
but does not resolve synonyms, clinical meaning, or physician mistakes.
If physicians edited MUSE output, independent adjudication is needed to assess
that dependence. Clinical usefulness requires clinician review and relevant
outcome evidence; see [FDA guidance on agreement versus correctness](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/statistical-guidance-reporting-results-studies-evaluating-diagnostic-tests-guidance-industry-and-fda).

## Inspect removed terms

Optional configuration:

```yaml
inspect_comparison: heedb_new
inspect_removed_terms:
  - sinus rhythm
  - left axis deviation
```

The main analysis saves both report texts to each mode's `removed_examples.jsonl`
for every matching removal under that rule. It overwrites these files when enabled.
Omitting the setting disables logging and leaves existing files untouched.

```sh
uv run python -m ecg_data.analysis.software_v_human.inspection \
  /path/to/results/heedb_new/exact_statement --limit 5
```

The path may point directly to the JSONL file. Worker completion order determines
example order. `--limit` controls printing; the old `inspect_limit` configuration
is unused. Inspection remains isolated in `inspection.py` and its main-analysis hooks.
