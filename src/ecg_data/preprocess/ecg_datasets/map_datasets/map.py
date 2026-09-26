from ecg_data.preprocess.ecg_datasets._build import _build_dataset


class MapDataset:
    def __init__(self, cfg: dict):
        self.cfg = cfg


def build_map_dataset(cfg: dict):
    return _build_dataset(cfg, __package__)
