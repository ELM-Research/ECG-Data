uv run python -m ecg_data.analysis.software_v_human.plot_statement_edits \
<<<<<<< HEAD
  --pairs src/ecg_data/analysis/software_v_human/results/llm_edits/agh/20261024T180253192784Z/pairs.jsonl \
  --annotations src/ecg_data/analysis/software_v_human/results/llm_edits/annotations_EL.json src/ecg_data/analysis/software_v_human/results/llm_edits/annotations_MR_26OCT2026.json src/ecg_data/analysis/software_v_human/results/llm_edits/annotations-XT.json \
  --statements "atrial fibrillation" "normal sinus rhythm"
=======
  --pairs /path/to/pairs.jsonl \
  --annotations /path/to/annotator_1.json /path/to/annotator_2.json \
  --examples 5 \
  --statements "atrial fibrillation" "normal sinus rhythm" "abnormal ecg"
>>>>>>> f98cb687ce456c5b6cf61cfd4844fde1989f8bc9
