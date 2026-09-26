from ecg_data.preprocess.config.load import get_config
from ecg_data.preprocess.ecg_datasets.base_datasets.base import build_base_dataset

if __name__ == "__main__":
    cfg = get_config()
    print(cfg)
    print(type(cfg))
    build_base_dataset(cfg)