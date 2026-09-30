# # ## HEEDB
# uv run python src/ecg_data/preprocess/preprocess_base.py \
# --config src/ecg_data/preprocess/config/heedb.yaml


# AGH
# uv run python src/ecg_data/preprocess/preprocess_base.py \
# --config src/ecg_data/preprocess/config/agh.yaml


# PTB XL
# uv run python src/ecg_data/preprocess/preprocess_base.py \
# --config src/ecg_data/preprocess/config/ptb_xl.yaml


# MIMIC IV ECG
uv run python src/ecg_data/preprocess/preprocess_base.py \
--config src/ecg_data/preprocess/config/mimic_iv_ecg.yaml