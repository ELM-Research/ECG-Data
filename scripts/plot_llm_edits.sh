#!/usr/bin/env bash

# AGH and HEEDB, grouped by statement category.
# PPV, NPV, sensitivity, and specificity go in each dataset's term_metrics/ and combined/term_metrics/.
# Overall and per-term trends use individual dated pairs. See time_trends/trends.json for fit statistics.
# Each time_trends/<category>/combined.png overlays its terms; separate plots are kept.
# The analysis cache rebuilds when its version, inputs, or selections change.
# Use --refresh-cache if the source ECG dates change.
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
