from pathlib import Path
from ecg_data.preprocess.ecg_datasets.common import get_dataset_module

class MapDataset:
    def __init__(self, dataset_module,
                 save_path: str,):
        self.dataset_module = dataset_module
        self.save_path = save_path
        Path(self.save_path).mkdir(parents=True, exist_ok=True)

    def create_dataset(self,):
        return self.dataset_module.prepare_json()

def build_map_dataset(cfg: dict):
    dataset_module = get_dataset_module(cfg["data_name"],
                                        cfg["data_root_path"],
                                        __package__)
    return MapDataset(dataset_module,
                      save_path = cfg["save_path"])