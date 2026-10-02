from ecg_data.preprocess.ecg_datasets.common import get_dataset_module


class MapDataset:
    def __init__(self, dataset_module):
        self.dataset_module = dataset_module

    def map_dataset(self,):
        map_data = self.dataset_module.get_map_data()


def build_map_dataset(cfg: dict):
    dataset_module = get_dataset_module(cfg["data_name"],
                                        cfg["data_root_path"],
                                        __package__)
    return MapDataset(dataset_module)