# ### PTB-XL
# CUDA_VISIBLE_DEVICES=2 uv run src/ecg_preprocess/preprocess_base.py \
# --base src/ecg_preprocess/config/ptb_xl.yaml

## CODE15
# uv run src/ecg_preprocess/preprocess_base.py \
# --base src/ecg_preprocess/config/code15.yaml

# # ## CPSC'
# uv run src/ecg_preprocess/preprocess_base.py \
# --base src/ecg_preprocess/config/cspsc.yaml

# # ## CSN
# uv run src/ecg_preprocess/preprocess_base.py \
# --base src/ecg_preprocess/config/csn.yaml

# # ## MIMIC-IV
uv run python src/ecg_preprocess/preprocess_base.py \
--config src/ecg_preprocess/config/mimic_iv_ecg.yaml