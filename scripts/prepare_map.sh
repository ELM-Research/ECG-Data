# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/pretrain_mimic.yaml

# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/heedb.yaml

# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/agh.yaml

# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/echonext.yaml

# # ECG QA COT
# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/ecg_qa_cot.yaml

# # ECG QA
# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/ecg_qa.yaml

# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/ecg_instruct_45k.yaml

uv run python src/ecg_data/preprocess/preprocess_map.py \
--config src/ecg_data/preprocess/config/map_datasets/ecg_instruct_pulse.yaml

# ### ECG Grounding
# uv run src/main.py \
# --map ecg_grounding


# ### PULSE ECG Bench
# uv run src/main.py \
# --map ecg_bench_pulse

# ### PULSE ECG Instruct
# uv run src/main.py \
# --map ecg_instruct_pulse


### PULSE ECG Grounding
# uv run src/main.py \
# --map ecg_grounding

# uv run src/main.py \
# --map ecg_protocol_gg_cot