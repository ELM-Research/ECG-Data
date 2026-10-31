uv run python -m ecg_data.analysis.software_v_human.plot_statement_edits \
  --pairs src/ecg_data/analysis/software_v_human/results/llm_edits/agh/20261024T180253192784Z/pairs.jsonl \
  --annotations src/ecg_data/analysis/software_v_human/results/llm_edits/annotations_EL.json src/ecg_data/analysis/software_v_human/results/llm_edits/annotations_MR_26OCT2026.json src/ecg_data/analysis/software_v_human/results/llm_edits/annotations-XT.json \
  --examples 5 \
  --statements "atrial fibrillation" "normal sinus rhythm"