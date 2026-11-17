#!/usr/bin/env bash

# AGH and HEEDB, grouped by statement category.
# PPV, NPV, sensitivity, and specificity go in each dataset's term_metrics/ and combined/term_metrics/.
# Overall and per-term quarterly trends go in time_trends/; trends.json saves counts, slopes, CIs, and p-values.
# Each time_trends/<category>/combined.png overlays its terms; separate plots are kept.
# Analysis is reused from figures/.cache/analysis.json when pairs, run metadata, and selections match.
# Use --refresh-cache after changing source ECG dates or analysis code; styling needs no refresh.
# Legacy HEEDB dates use /p01/whan/data/HEED; override with --heed-root if needed.
# HEEDB date reads use 8 threads; override with --workers.
uv run python -m ecg_data.analysis.software_v_human.plot_llm_edits \
  --config src/ecg_data/analysis/config/llm_edits_sglang.yaml \
           src/ecg_data/analysis/config/llm_edits_sglang2.yaml "$@"

# Only the specified statements. Uncomment to use this example instead.
# uv run python -m ecg_data.analysis.software_v_human.plot_llm_edits \
#   --config src/ecg_data/analysis/config/llm_edits_sglang.yaml \
#            src/ecg_data/analysis/config/llm_edits_sglang2.yaml \
#   --statements "atrial fibrillation" "sinus rhythm"
