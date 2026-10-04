## ECG QA PTB-XL
# uv run src/main.py \
# --map ecg_qa_ptb_xl

uv run python src/ecg_data/preprocess/preprocess_map.py \
--config src/ecg_data/preprocess/config/map_datasets/pretrain_mimic.yaml

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

### ECG Comprehension
# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg noise flatline \
# --per_len 1000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg noise flatline \
# --per_len 2000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg noise flatline \
# --per_len 3000


# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg noise \
# --per_len 1000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg noise \
# --per_len 2000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg noise \
# --per_len 3000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg flatline \
# --per_len 1000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg flatline \
# --per_len 2000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg flatline \
# --per_len 3000


# uv run src/main.py \
# --map ecg_comprehension \
# --input_type noise flatline \
# --per_len 1000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type noise flatline \
# --per_len 2000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type noise flatline \
# --per_len 3000




# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg noise \
# --per_len 30000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg noise \
# --per_len 60000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg noise \
# --per_len 90000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg flatline \
# --per_len 30000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg flatline \
# --per_len 60000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type ecg flatline \
# --per_len 90000


# uv run src/main.py \
# --map ecg_comprehension \
# --input_type noise flatline \
# --per_len 30000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type noise flatline \
# --per_len 60000

# uv run src/main.py \
# --map ecg_comprehension \
# --input_type noise flatline \
# --per_len 90000


uv run src/main.py \
--map ecg_comprehension \
--ecg_numeric r_peak_count \
--per_len 50000

uv run src/main.py \
--map ecg_comprehension \
--ecg_numeric r_peak_count \
--per_len 100000

uv run src/main.py \
--map ecg_comprehension \
--ecg_numeric r_peak_count \
--per_len 150000


uv run src/main.py \
--map ecg_comprehension \
--ecg_numeric heart_rate_bpm_int \
--per_len 50000

uv run src/main.py \
--map ecg_comprehension \
--ecg_numeric heart_rate_bpm_int \
--per_len 100000

uv run src/main.py \
--map ecg_comprehension \
--ecg_numeric heart_rate_bpm_int \
--per_len 150000


uv run src/main.py \
--map ecg_comprehension \
--ecg_numeric heart_rate_bpm_float \
--per_len 50000

uv run src/main.py \
--map ecg_comprehension \
--ecg_numeric heart_rate_bpm_float \
--per_len 100000

uv run src/main.py \
--map ecg_comprehension \
--ecg_numeric heart_rate_bpm_float \
--per_len 150000
