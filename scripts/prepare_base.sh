# ### PTB-XL
# CUDA_VISIBLE_DEVICES=2 uv run src/preprocess/preprocess_base.py \
# --base src/preprocess/config/ptb_xl.yaml

## CODE15
# uv run src/preprocess/preprocess_base.py \
# --base src/preprocess/config/code15.yaml

# # ## CPSC'
# uv run src/preprocess/preprocess_base.py \
# --base src/preprocess/config/cspsc.yaml

# # ## CSN
# uv run src/preprocess/preprocess_base.py \
# --base src/preprocess/config/csn.yaml

# # ## MIMIC-IV
uv run python src/ecg_data/preprocess/preprocess_base.py \
--config src/ecg_data/preprocess/config/mimic_iv_ecg.yaml