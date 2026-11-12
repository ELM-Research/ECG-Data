#!/usr/bin/env bash

# AGH and HEEDB, grouped by statement category.
uv run python -m ecg_data.analysis.software_v_human.plot_llm_edits \
  --config src/ecg_data/analysis/config/llm_edits_sglang.yaml \
           src/ecg_data/analysis/config/llm_edits_sglang2.yaml

# Only the specified statements. Uncomment to use this example instead.
# uv run python -m ecg_data.analysis.software_v_human.plot_llm_edits \
#   --config src/ecg_data/analysis/config/llm_edits_sglang.yaml \
#            src/ecg_data/analysis/config/llm_edits_sglang2.yaml \
#   --statements "atrial fibrillation" "sinus rhythm"
