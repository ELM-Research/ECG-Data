from pathlib import Path

from ecg_datasets.map.map_dataset import MapDataset
from configs.constants import DATA_DIR
from utils.file_dir import open_json

class ECGInstruct45k(MapDataset):
    def __init__(self, args):
        super().__init__(args)
        self.data_name = "mimic_iv"
        self.saved_dir = f"{DATA_DIR}/{self.data_name}/preprocessed_{self.args.segment_len}"
        self.save_dir_json = f"src/ecg_datasets/map/{self.args.map}/{self.args.map}_hf.json"
    
    def get_map_data(self, ):
        self.available_ecgs.update(f.stem for f in Path(self.saved_dir).glob("*"))
        data = open_json(f"src/ecg_datasets/map/{self.args.map}/{self.args.map}.json")
        return data
    
    def process_instance(self, instance):
        text = instance["conversations"]
        ecg_path = "_".join(instance["ecg"].split("/"))
        name = instance.get("name", "")
        return {"ecg_path": ecg_path, "text" : text,
                "saved_dir" : self.saved_dir, "name": name}