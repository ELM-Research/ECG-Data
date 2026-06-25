from pathlib import Path
from datasets import load_dataset
from tqdm import tqdm
import glob
import os

from ecg_datasets.map.map_dataset import MapDataset
from utils.file_dir import ensure_directory_exists, open_json, save_json
from configs.constants import DATA_DIR

class ECGBenchPulse(MapDataset):
    def __init__(self, args):
        super().__init__(args)
        self.data_name = ["mimic_iv", "code15", "ptb_xl", "csn", "cpsc"]
        self.save_dir_json = f"src/ecg_datasets/map/{self.args.map}/{self.args.map}_hf.json"

    def get_map_data(self,):
        json_path = f"src/ecg_datasets/map/{self.args.map}/ecg_bench_pulse_datasets.json"
        if ensure_directory_exists(file=json_path):
            data = open_json(json_path)
        else:
            data = self.create_json(json_path)

        for data_name in self.data_name:
            saved_dir = f"{DATA_DIR}/{data_name}/preprocessed_{self.args.segment_len}"
            self.available_ecgs.update(f.stem for f in Path(saved_dir).glob("*"))
        return data

    def create_json(self, json_path):
        list_of_hf_datasets = ["cpsc-test", "csn-test-no-cot", "code15-test", "ptb-test", "ptb-test-report", "ecgqa-test"]
        data = []

        for name in tqdm(list_of_hf_datasets, desc="Loading ECGBenchPulse datasets"):
            dataset = load_dataset("PULSE-ECG/ECGBench", name=name, streaming=False)
            for item in dataset["test"]:
                conversations = item["conversations"]
                file_path = item["image_path"]
                file_name = file_path.split("/")[-1].split("-")[0]
                # Handle ecgqa-test special case
                if name == "ecgqa-test":
                    for conv in conversations:
                        if isinstance(conv.get("value"), list):
                            conv["value"] = "".join(conv["value"])
                data.append({
                    "file_path": file_path,
                    "file_name": file_name,
                    "conversations": conversations,
                    "name": name,
                })
        save_json(data, json_path)
        return data

    def process_instance(self, instance):
        text = instance["conversations"]
        file_name = instance["file_name"]
        name = instance.get("name", "")
        ecg_path, saved_dir = self.get_ecg_path(file_name, name)
        return {"ecg_path": ecg_path, "text": text,
                "saved_dir" : saved_dir, "name": name}

    def get_ecg_path(self, file_name, name):
        if name in ["ecgqa-test", "ptb-test-report", "ptb-test"]:
            data_name = "ptb_xl"
            subfolder = file_name[:2] + "000"
            ecg_path = f"records500_{subfolder}_{file_name}"
        elif name == "cpsc-test":
            data_name = "cpsc"
            cpsc_paths = glob.glob(f"{DATA_DIR}/cpsc/training/*/*/*.hea")
            cpsc_filename_to_path = {os.path.basename(path).split(".")[0]: path.replace(".hea", "") for path in cpsc_paths}
            ecg_path = cpsc_filename_to_path[file_name]
            ecg_path = ecg_path.split("/")[-1]
        elif name == "csn-test-no-cot":
            data_name = "csn"
            csn_paths = glob.glob(f"{DATA_DIR}/csn/WFDBRecords/*/*/*.hea")
            csn_filename_to_path = {os.path.basename(path).split(".")[0]: path.replace(".hea", "") for path in csn_paths}
            ecg_path = csn_filename_to_path[file_name]
            ecg_path = ecg_path.split("/")[-1]
        elif name == "code15-test":
            data_name = "code15"
            ecg_path = file_name.split("-")[0]

        saved_dir = f"{DATA_DIR}/{data_name}/preprocessed_{self.args.segment_len}"
        return ecg_path, saved_dir