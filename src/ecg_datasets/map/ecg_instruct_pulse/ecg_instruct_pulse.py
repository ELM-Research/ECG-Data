from pathlib import Path

from ecg_datasets.map.map_dataset import MapDataset
from configs.constants import DATA_DIR
from utils.file_dir import open_json

class ECGInstructPulse(MapDataset):
    def __init__(self, args):
        super().__init__(args)
        self.data_name = ["mimic_iv", "code15", "ptb_xl"]
        self.save_dir_json = f"src/ecg_datasets/map/{self.args.map}/{self.args.map}_hf.json"
    
    def get_map_data(self,):
        for data_name in self.data_name:
            saved_dir = f"{DATA_DIR}/{data_name}/preprocessed_{self.args.segment_len}"
            self.available_ecgs.update(f.stem for f in Path(saved_dir).glob("*"))
        data = open_json(f"src/ecg_datasets/map/{self.args.map}/{self.args.map}.json")
        return data
    
    def process_instance(self, instance):
        text = instance["conversations"]
        ecg_path, saved_dir = self.get_ecg_path(instance)
        name = instance.get("name", "")
        return {"ecg_path": ecg_path, "text": text,
                "saved_dir" : saved_dir, "name": name}

    def get_ecg_path(self, instance):
        parts = instance["image"].split("/")
        dataset_image_type = parts[0]
        filename = parts[-1]
        if dataset_image_type in ["mimic_v4", "mimic"]:
            dataset_image_type = "mimic_iv"
            base_filename = filename.split("-")[0]
            path_to_file = "_".join(parts[1:-1] + [base_filename])
            ecg_path = f"files_{path_to_file}"
        if dataset_image_type in ["ptb-xl"]:
            dataset_image_type = "ptb_xl"
            record_number = filename.split("_")[0]
            record_number = f"{record_number}_hr"
            subfolder = record_number[:2] + "000"
            ecg_path = f"records500_{subfolder}_{record_number}"
        elif dataset_image_type in ["code15_v4"]:
            dataset_image_type = "code15"
            ecg_path = filename.split("-")[0]
        saved_dir = f"{DATA_DIR}/{dataset_image_type}/preprocessed_{self.args.segment_len}"
        return ecg_path, saved_dir
