from ecg_data.preprocess.ecg_datasets.common import get_dataset_module


class MapDataset:
    def __init__(self, cfg: dict):
        self.cfg = cfg


def build_map_dataset(cfg: dict):
    return get_dataset_module(cfg, __package__)