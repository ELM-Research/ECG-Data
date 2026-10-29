# AGH and HEEDB old only. Figures go beside inputs; annotations use the first JSON's folder.
uv run python -m ecg_data.analysis.software_v_human.plot_statement_edits \
  --pairs /path/to/pairs.jsonl \
  --annotations /path/to/annotator_1.json /path/to/annotator_2.json \
  --examples 5 \
  --statements "atrial fibrillation" "normal sinus rhythm" "abnormal ecg"
