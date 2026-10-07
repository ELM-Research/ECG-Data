# Edits-study prompts

Use [`edits_llm.yaml`](../src/ecg_data/analysis/config/edits_llm.yaml) to select
`matching: exact` or `matching: semantic`, then choose an analysis. Prompt text
lives in [`prompts/edits.yaml`](../src/ecg_data/analysis/software_v_human/prompts/edits.yaml).
Both modes use the same JSON fields and target statements.

The LLM returns per-pair decisions only. It does not calculate counts, metric
contributions, or rates. The pipeline contract mirrors the current edits study:

1. Compare each report pair and save its labels and explanations.
2. Analysis code aggregates labels into the existing edits-results format.
3. `plot_edits.py` reads those saved counts and calculates the four statement
   metrics, report-edit plots, and input-quality plots.

| Analysis | Output | Use |
| --- | --- | --- |
| combined | Report change, target groups, literal edit types, explanations | All analyses in one call |
| reports | Report change and explanation | Overall edit rate and change categories |
| statements | Every target's G1–G4 group and explanation | All four statement metrics |
| edit_types | Every literal edit's type and explanation | Preferential/factual review |

Use `combined` for one response per pair. For separate calls, join `reports`,
`statements`, and `edit_types` by record ID and software source before aggregation;
count each pair once. The same statement labels feed all four metric plots.

Render the selected prompt:

```bash
uv run python -m ecg_data.analysis.software_v_human.edits_prompts \
  --config src/ecg_data/analysis/config/edits_llm.yaml
```

This only prints a prompt. It does not call a model, send reports, or change the
existing rules analysis. Supply the rendered instructions and the input JSON
below to the chosen LLM. Model execution, response validation, and aggregation of
saved LLM responses are not yet implemented; the contracts below specify their
required inputs and outputs.

## Definitions

Exact mode follows [`edits.py`](../src/ecg_data/analysis/software_v_human/edits.py)
and [`reports.py`](../src/ecg_data/analysis/software_v_human/reports.py): lowercase
whole entries, remove blank entries, collapse duplicates, ignore order, and
otherwise match literally. Punctuation and whitespace in nonblank entries remain
significant. The empty-report exclusion matches
[`edits_heedb.yaml`](../src/ecg_data/analysis/config/edits_heedb.yaml).

Semantic mode compares conveyed clinical information. Equivalent wording and
redundant summaries can be unchanged; negation, certainty, measurements, and
other meaningful qualifiers must be preserved. Ambiguous decisions use `null`
and an explanation. These are unresolved LLM decisions, not G4 or unchanged.

Edit types follow the study definitions supplied in this discussion:

- **Preferential:** wording, presentation, or redundancy changes that preserve
  clinical information. Removing “abnormal ECG” can qualify when remaining
  statements already convey the abnormality.
- **Factual:** an edit involving demonstrably incorrect information. Identify the
  incorrect statement and evidence for the error; do not assume the physician is
  correct.
- **Uncertain:** the reports cannot establish either classification.

A changed finding or measurement alone does not prove an error. Report-only runs
cannot confirm corrections that require the ECG or other unavailable evidence;
those remain uncertain for physician review.

Both modes classify the same literal additions and deletions. This keeps
preferential edits visible when semantic metrics call the reports unchanged.
Whole-report edits are decided from the entire pair, not just selected targets.

## Input and output example

Supply the same statement lists used by the rules; do not introduce new splitting
of raw prose. `null` means missing; `[]` means empty. Empty, missing, and malformed
pairs are excluded in both modes and still receive an `input_status`.

For combined and statement prompts, provide a fixed list of lowercase,
nonblank target statements. Use the vocabulary from the saved rules results
(`terms` keys), including statements absent from this particular pair. That is
necessary to count G4 and compare the same statement across modes. Do not let each
model invent a different vocabulary. Analyze the complete vocabulary; top-K
selection and filtering to `terms.py` belong to plotting. Reports and edit_types
do not need targets.

Keep record ID, source, matching mode, analysis, model settings, and the exact
prompt outside the report text and attach them to each saved response. Compare
old and new software with the physician report separately.

Example combined input (A is an unspecified abnormal finding):

```json
{
  "software_report": ["Abnormal ECG", "Abnormal finding A"],
  "physician_report": ["Abnormal finding A"],
  "targets": ["abnormal ecg", "abnormal finding a", "finding b"]
}
```

Exact-mode output:

```json
{
  "input_status": "nonempty",
  "change": "deleted_only",
  "report_explanation": "The physician removed 'Abnormal ECG' and retained 'Abnormal finding A'.",
  "statements": [
    {
      "statement": "abnormal ecg",
      "group": "G2",
      "explanation": "'Abnormal ECG' occurs only in the software report."
    },
    {
      "statement": "abnormal finding a",
      "group": "G1",
      "explanation": "'Abnormal finding A' occurs in both reports."
    },
    {
      "statement": "finding b",
      "group": "G4",
      "explanation": "Neither report contains 'finding b'."
    }
  ],
  "edits": [
    {
      "operation": "deleted",
      "statement": "abnormal ecg",
      "edit_type": "preferential",
      "explanation": "The retained 'Abnormal finding A' already conveys abnormality; 'Abnormal ECG' adds no distinct information."
    }
  ]
}
```

Semantic-mode output for the same input:

```json
{
  "input_status": "nonempty",
  "change": "unchanged",
  "report_explanation": "Both reports convey 'Abnormal finding A'; the removed 'Abnormal ECG' summary is redundant.",
  "statements": [
    {
      "statement": "abnormal ecg",
      "group": "G1",
      "explanation": "The software states 'Abnormal ECG'; the physician's retained 'Abnormal finding A' also conveys abnormality."
    },
    {
      "statement": "abnormal finding a",
      "group": "G1",
      "explanation": "Both reports explicitly state 'Abnormal finding A'."
    },
    {
      "statement": "finding b",
      "group": "G4",
      "explanation": "Neither report conveys finding B."
    }
  ],
  "edits": [
    {
      "operation": "deleted",
      "statement": "abnormal ecg",
      "edit_type": "preferential",
      "explanation": "The retained 'Abnormal finding A' already conveys abnormality; 'Abnormal ECG' adds no distinct information."
    }
  ]
}
```

## Complete A/B/C examples

A, B, and C represent distinct whole statements. Each physician alternative is
a separate pair. These examples cover all 49 ordered pairs of nonempty subsets
of `{A, B, C}`. They do not cover empty, missing, or malformed reports.

| Group for A | Software contains A | Physician contains A | Meaning |
| --- | --- | --- | --- |
| G1 | Yes | Yes | A retained |
| G2 | Yes | No | A deleted |
| G3 | No | Yes | A added |
| G4 | No | No | A absent from both |

| Group | Software | Separate physician alternatives |
| --- | --- | --- |
| G1 | [A] | [A] · [A, B] · [A, C] · [A, B, C] |
| G1 | [A, B] | [A] · [A, B] · [A, C] · [A, B, C] |
| G1 | [A, C] | [A] · [A, B] · [A, C] · [A, B, C] |
| G1 | [A, B, C] | [A] · [A, B] · [A, C] · [A, B, C] |
| G2 | [A] | [B] · [C] · [B, C] |
| G2 | [A, B] | [B] · [C] · [B, C] |
| G2 | [A, C] | [B] · [C] · [B, C] |
| G2 | [A, B, C] | [B] · [C] · [B, C] |
| G3 | [B] | [A] · [A, B] · [A, C] · [A, B, C] |
| G3 | [C] | [A] · [A, B] · [A, C] · [A, B, C] |
| G3 | [B, C] | [A] · [A, B] · [A, C] · [A, B, C] |
| G4 | [B] | [B] · [C] · [B, C] |
| G4 | [C] | [B] · [C] · [B, C] |
| G4 | [B, C] | [B] · [C] · [B, C] |

Use every pair in the named groups. These formulas are for postprocessing code;
they are not part of the LLM prompts:

| Metric | Numerator groups | Denominator groups | Example counts |
| --- | --- | --- | --- |
| Sensitivity | G1 | G1 + G3 | 16 / 28 |
| Specificity | G4 | G2 + G4 | 9 / 21 |
| PPV | G1 | G1 + G2 | 16 / 28 |
| NPV | G4 | G3 + G4 | 9 / 21 |

Across all 49 pairs, whole-report counts are 7 unchanged, 12 added_only,
12 deleted_only, and 18 both. Overall edit rate is 42 / 49. These are illustrative
counts, not estimates from the ECG dataset. A/B/C alone does not establish
whether an edit is preferential or factual.

## Aggregate outside the LLM

The existing visualizations require the following saved fields. The LLM only
provides the per-pair labels in the middle column; code produces the last column.

| Visualization | Per-pair LLM output | Saved analysis fields |
| --- | --- | --- |
| Overall edit rate | `change` | `edited_reports`, `included_reports` |
| Report-change types | `change` | `report_counts`, `included_reports` |
| Input quality | `input_status` | `input_status_counts`, `input_reports` |
| Sensitivity, specificity, PPV, NPV | Each target's `group` | `terms[statement].retained`, `deleted`, `added`, `absent_from_both` |
| Top-K statement selection | The same target groups | `terms[statement].edited_report_count` |
| Reference-term selection | The target statement names | `terms` keys matched against `terms.py` |

Save `study`, `normalization`, `empty_reports`, source, and matching-mode metadata
from configuration. Compute the remaining totals and rates in analysis code, as
the rules study does. Keep original reports, per-pair labels, edit types, and
explanations for physician review separately from the aggregate plot data.

The four formulas above match
[`plot_edits.py`](../src/ecg_data/analysis/software_v_human/plot_edits.py). Count
G1–G4 for each fixed target, using all included pairs, including unchanged pairs.
Calculate each software source and matching mode separately. Do not pool synonyms
or different target statements into a single denominator.

Let N be the number of included pairs with a resolved decision for the analysis.
For exact mode, every valid nonempty pair has a resolved decision. For semantic
mode, track unresolved groups per target and unresolved report changes separately.

| Saved quantity | Calculation |
| --- | --- |
| retained / deleted / added / absent_from_both | G1 / G2 / G3 / G4 counts, respectively |
| software_report_count | G1 + G2 |
| software_absent_report_count | G3 + G4 |
| physician_report_count | G1 + G3 |
| mentioned_report_count | G1 + G2 + G3 |
| edited_report_count for a target | G2 + G3 |
| disagreement_rate for a target | (G2 + G3) / (G1 + G2 + G3) |
| added_report_ratio for a target | G3 / (G3 + G4) |
| deleted_report_ratio for a target | G2 / (G1 + G2) |
| Overall edit_rate | Resolved pairs with change other than unchanged / N |
| Each report change rate | Pairs in that change category / N |
| Each input-quality rate | Pairs with that input_status / all input pairs |

Compute numerators and denominators from aggregated G1–G4 counts in code. A zero
denominator gives `null`, not zero. Do not average per-pair ratios.
Classifications of literal edits do not change these counts.
A replacement contributes a literal addition and deletion, while its report is
counted once in the overall edit rate.

Before aggregation, validate JSON fields, labels, complete target coverage, and
edit coverage. A failed or incomplete
model response is a model-output failure, not an invalid report or an absent
statement. Do not silently turn missing predictions into G4. The current rules
summarizer infers G4 from included-pair counts; it can only be reused directly
when all target groups are resolved on those pairs. Unresolved predictions need
explicit coverage accounting before producing plot data.

Report model-output failures and unresolved decisions. For each comparison,
calculate LLM and rules metrics on the same successfully resolved pairs and report
the coverage denominator alongside them. Keep full-cohort rules results as well.
Compare individual groups and report-change labels; aggregate agreement can hide
offsetting errors. Disagreement in semantic mode can reflect its different edit
definition, so it is not automatically an LLM error.

For physician review, show both reports, the relevant target or literal edit, its
label, and its explanation. Record acceptability of the edit decision,
preferential/factual classification, and explanation separately, allowing a
correction or “cannot determine.” Include unchanged and G1/G4 cases to check for
missed edits. No model or physician evaluation has been run yet.
