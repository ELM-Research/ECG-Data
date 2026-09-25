# ### PTB-XL
# CUDA_VISIBLE_DEVICES=2 uv run src/preprocess_base.py.py \
# --base src/ecg_preprocess/config/ptb_xl.yaml

## CODE15
# uv run src/preprocess_base.py.py \
# --base src/ecg_preprocess/config/code15.yaml

# # ## CPSC'
# uv run src/preprocess_base.py.py \
# --base src/ecg_preprocess/config/cspsc.yaml

# # ## CSN
# uv run src/preprocess_base.py.py \
# --base src/ecg_preprocess/config/csn.yaml

# # ## MIMIC-IV
uv run python src/preprocess_base.py.py \
--config src/ecg_preprocess/config/mimic_iv_ecg.yaml