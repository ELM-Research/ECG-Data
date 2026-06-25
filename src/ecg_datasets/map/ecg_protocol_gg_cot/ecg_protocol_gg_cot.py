from pathlib import Path
from datasets import load_dataset
from tqdm import tqdm
import re

from ecg_datasets.map.map_dataset import MapDataset
from configs.constants import DATA_DIR
from utils.file_dir import ensure_directory_exists, open_json, save_json

SPLIT = "test"

class ECGProtocolGGCot(MapDataset):
    def __init__(self, args):
        super().__init__(args)
        if SPLIT == "train":
            self.data_name = ["mimic_iv", "code15", "ptb_xl"]
        else:
            self.data_name = ["mimic_iv"]
        self.save_dir_json = f"src/ecg_datasets/map/{self.args.map}/{self.args.map}_{SPLIT}_hf.json"

    def get_map_data(self,):
        for data_name in self.data_name:
            saved_dir = f"{DATA_DIR}/{data_name}/preprocessed_{self.args.segment_len}"
            self.available_ecgs.update(f.stem for f in Path(saved_dir).glob("*"))
        json_path = f"src/ecg_datasets/map/ecg_protocol_gg_cot/{self.args.map}_{SPLIT}.json"
        if ensure_directory_exists(file=json_path):
            data = open_json(json_path)
        else:
            data = self.create_json(json_path)
        return data

    def process_instance(self, instance):
        return instance

    def create_json(self, json_path):
        # Counter({'MIMIC-IV-ECG': 799687
        # 'PTB-XL': 149425
        # 'ECG-QA': 139358
        # 'CODE-15%': 67640})
        data = []
        if SPLIT == "train":
            # list_of_hf_datasets = ["rl"]
            list_of_hf_datasets = ["rl"]
            # list_of_hf_datasets = ["base"]
            hf_dataset_name = "PKUDigitalHealth/ECG-Protocol-Guided-Grounding-CoT"
        else:
            list_of_hf_datasets = ["test"]
            hf_dataset_name = "LANSG/ECG-Grounding"
        for name in list_of_hf_datasets:
            if SPLIT == "train":
                dataset = load_dataset(hf_dataset_name, name = name, split = "train")
            else:
                dataset = load_dataset(hf_dataset_name, split = name)

            for item in tqdm(dataset, desc = f"{SPLIT}: {name}"):

                if SPLIT == "train":
                    conversations = item["messages"][1:]
                    # for msg in conversations:
                    #     msg["content"] = re.sub(r"</?think>|\n<answer>|</answer>", "", msg["content"])
                    # print(conversations)
                    # input()
                    if item["source"] == "MIMIC-IV-ECG":
                        data_name = "mimic_iv"
                        ecg_path = "_".join(item["objects"]["ecg"][0].split("/")[1:])
                    elif item["source"] == "PTB-XL":
                        data_name = "ptb_xl"
                        ecg_path = "_".join(item["objects"]["ecg"][0].split("/")[3:])
                    elif item["source"] == "CODE-15%":
                        data_name = "code15"
                        ecg_path = item["objects"]["ecg"][0].split("/")[-1]
                    elif item["source"] == "ECG-QA":
                        if "ptbxl" in item["objects"]["ecg"][0]:
                            data_name = "ptb_xl"
                            ecg_path = "_".join(item["objects"]["ecg"][0].split("/")[3:])
                        elif "mimic" in item["objects"]["ecg"][0]:
                            data_name = "mimic_iv"
                            ecg_path = "_".join(item["objects"]["ecg"][0].split("/")[1:])
                    data.append({
                    "text": conversations,
                    "saved_dir": f"{DATA_DIR}/{data_name}/preprocessed_{self.args.segment_len}",
                    "ecg_path": ecg_path,
                    "name": item["source"],
                })
                elif SPLIT == "test" and item["source"] == "MIMIC-IV-ECG":
                    conversations = item["conversations"]
                    ecg_path = "_".join(item["ecg"].split("/")[1:])
                    data_name = "mimic_iv"
                    data.append({
                    "text": conversations,
                    "saved_dir": f"{DATA_DIR}/{data_name}/preprocessed_{self.args.segment_len}",
                    "ecg_path": ecg_path,
                    "name": item["source"],
                })
        # from collections import Counter
        # unique_count = Counter(d["name"] for d in data)
        # print(unique_count)
        # input()
        save_json(data, json_path)
        return data

