# Software versus physician reports

Set `data_path` and `save_path` in the analysis configuration, then run:

```sh
bash scripts/software_v_human.sh heedb
bash scripts/software_v_human.sh agh
```

The script defaults to AGH. Its configuration remains gitignored; create
`src/ecg_data/analysis/config/software_v_human_agh.yaml` locally with:

```yaml
defaults:
  - ./common.yaml
data_name: agh
data_path: /batch_data/agh/filtered_batch_meta_data_v3
```

HEEDB reads `*/*.npy` once per file; AGH reads JSON arrays in `*.json`.
Each comparison writes `summary.json` and `terms.csv` under `save_path`:

| Directory | Software field | Physician field |
| --- | --- | --- |
| `agh` | `OriginalDiagnosis` | `Diagnosis` |
| `heedb_old` | `reports_software_old` | `reports_physician` |
| `heedb_new` | `reports_software_new` | `reports_physician` |

Counting rules:

- Use only the 69 phrases from Supplemental Table 1, DOI `10.1093/ehjdh/ztaf119`.
  Ignore case and collapse whitespace. Match whole phrases, without synonyms.
- For each term: present in both reports means retained; software only means
  deleted; physician only means added. Absent from both means ignored.
- Skip a pair if neither report contains any listed term. Missing or null reports
  are also skipped. An empty report has no terms; if the other report has a term,
  count it as added or deleted. Print and save both skip counts per comparison.
- A report is modified only when a listed term is added or deleted. Other wording,
  term order, and repeated mentions do not change that classification.
- Count repeated mentions as term frequency, but each report only once for
  presence. Matches include suspected, negated, and historical mentions.

`terms.csv` contains observed terms for `all`, `unchanged`, and `modified` report
cohorts. Each row includes its category, original/final frequencies and report
counts, proportions, and retained/deleted/added counts. Terms absent from both
reports are not counted; terms never observed in a cohort have no row.

Proportions use the cohort's analyzed report count (`report_count`), after skips.
The three term groups sum to the number of pairs containing that term in either
report. `summary.json` includes total, analyzed, skipped, unchanged, and modified
report counts. Undefined summary proportions are `null`.
