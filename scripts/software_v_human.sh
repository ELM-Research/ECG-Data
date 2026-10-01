# uv run python src/ecg_data/analysis/software_v_human/main.py \
# --config src/ecg_data/analysis/config/software_v_human_agh.yaml

# uv run python src/ecg_data/analysis/software_v_human/main.py \
# --config src/ecg_data/analysis/config/software_v_human_heedb.yaml


# uv run python src/ecg_data/analysis/software_v_human/results_interpreter.py src/ecg_data/analysis/software_v_human/results/agh

# uv run python src/ecg_data/analysis/software_v_human/results_interpreter.py src/ecg_data/analysis/software_v_human/results/heedb_new

# uv run python src/ecg_data/analysis/software_v_human/results_interpreter.py src/ecg_data/analysis/software_v_human/results/heedb_old

uv run python src/ecg_data/analysis/software_v_human/inspection.py src/ecg_data/analysis/software_v_human/results/heedb_new --limit 5
