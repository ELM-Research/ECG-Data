## ECG QA PTB-XL
# uv run src/main.py \
# --map ecg_qa_ptb_xl

# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/pretrain_mimic.yaml

# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/heedb.yaml

# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/agh.yaml

# uv run python src/ecg_data/preprocess/preprocess_map.py \
# --config src/ecg_data/preprocess/config/map_datasets/echonext.yaml

uv run python src/ecg_data/preprocess/preprocess_map.py \
--config src/ecg_data/preprocess/config/map_datasets/ecg_qa_cot.yaml

### ECG QA MIMIC-IV
# uv run src/main.py \
# --map ecg_qa_mimic_iv

# ### Pretrain MIMIC
# uv run src/main.py \
# --map pretrain_mimic

# ### ECG Grounding
# uv run src/main.py \
# --map ecg_grounding

# ### ECG Instruct 45k
# uv run src/main.py \
# --map ecg_instruct_45k

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