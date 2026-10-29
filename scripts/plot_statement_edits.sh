# Two separate figures. Omit either input to plot only the other.
uv run python -m ecg_data.analysis.software_v_human.plot_statement_edits \
  --pairs /path/to/pairs.jsonl \
  --annotations /path/to/annotator_1.json /path/to/annotator_2.json \
  --statements "atrial fibrillation" "normal sinus rhythm" "abnormal ecg" \
  --output /path/to/statement_figures
