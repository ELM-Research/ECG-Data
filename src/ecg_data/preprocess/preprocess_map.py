from ecg_data.preprocess.config.load import get_config
from ecg_data.preprocess.ecg_datasets.map_datasets.map import build_map_dataset

if __name__ == "__main__":
    cfg = get_config()
    print(cfg)
    map_dataset = build_map_dataset(cfg)
    map_dataset.create_dataset()