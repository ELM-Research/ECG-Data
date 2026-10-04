from ecg_data.preprocess.ecg_datasets.common import get_dataset_module


class MapDataset:
    def __init__(self, dataset_module,
                 save_path: str | None = None,
                 toy_dataset_fraction: float | None = None,
                 development: bool = False,):
        self.dataset_module = dataset_module
        self.save_path = save_path

    def prepare_map_dict(self,):
        return self.dataset_module.get_json()

    def create_dataset(self, map_dict):
        pass

def build_map_dataset(cfg: dict):
    dataset_module = get_dataset_module(cfg["data_name"],
                                        cfg["data_root_path"],
                                        __package__)
    return MapDataset(dataset_module,
                      save_path = cfg["save_path"],
                      toy_dataset_fraction=cfg["toy_dataset_fraction"],
                      development=cfg["development"],)