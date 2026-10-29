# AGH and HEEDB old only. Figures go beside inputs; annotations use the first JSON's folder.
uv run python -m ecg_data.analysis.software_v_human.plot_statement_edits \
  --pairs src/ecg_data/analysis/software_v_human/results/llm_edits/agh/20261024T180253192784Z/pairs.jsonl \
  --annotations /path/to/annotator_1.json /path/to/annotator_2.json \
  --statements "atrial fibrillation" "normal sinus rhythm" "abnormal ecg"
