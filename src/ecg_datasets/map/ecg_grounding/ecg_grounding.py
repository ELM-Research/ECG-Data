from pathlib import Path

from ecg_datasets.map.map_dataset import MapDataset
from configs.constants import DATA_DIR
from utils.file_dir import open_json

class ECGGrounding(MapDataset):
    def __init__(self, args):
        super().__init__(args)
        self.save_dir_json = f"src/ecg_datasets/map/{self.args.map}/{self.args.map}_hf.json"
        self.data_name = ["mimic_iv", "code15", "ptb_xl"]

    def get_map_data(self,):
        for data_name in self.data_name:
            saved_dir = f"{DATA_DIR}/{data_name}/preprocessed_{self.args.segment_len}"
            self.available_ecgs.update(f.stem for f in Path(saved_dir).glob("*"))
        data = open_json(f"src/ecg_datasets/map/{self.args.map}/{self.args.map}.json")
        return data
    
    def process_instance(self, instance):
        text = instance["conversations"]
        file_name = instance["ecg"]
        ecg_path, saved_dir = self.get_ecg_path(file_name)
        name = instance.get("name", "")
        return {"text": text, "ecg_path": ecg_path,
                "saved_dir": saved_dir, "name": name}
    
    def get_ecg_path(self, file_name):
        base_dataset_name = file_name.split("/")[0]
        if base_dataset_name == "mimic-iv":
            data_name = "mimic_iv"
            file_name = "_".join(file_name.split("/")[1:])
        elif base_dataset_name == "ecg_ptbxl_benchmarking":
            data_name = "ptb_xl"
            file_name = "_".join(file_name.split("/")[3:])
        elif base_dataset_name == "code15":
            data_name = "code15"
            file_name = file_name.split("/")[-1]
        saved_dir = f"{DATA_DIR}/{data_name}/preprocessed_{self.args.segment_len}"
        return file_name, saved_dir