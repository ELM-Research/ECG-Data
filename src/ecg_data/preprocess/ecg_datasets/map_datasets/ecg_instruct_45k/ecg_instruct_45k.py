import json
from tqdm import tqdm
from pathlib import Path
from collections import defaultdict
from ecg_data.preprocess.ecg_datasets.common import open_json, preprocess_conversation

class ECG_INSTRUCT_45K:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path
        self.available_ecgs = defaultdict(list)
        self.base_data_paths = ["/p01/whan/data/mimic_iv_ecg/preprocessed_250_10"]
        for base_data in self.base_data_paths:
            for path in Path(base_data).glob("*/*.npy"):
                # MIMIC-IV-ECG study IDs are unique; BaseDataset appends _<segment>.npy.
                unique_id = path.stem.rsplit("_", 2)[-2]
                self.available_ecgs[unique_id].append(str(path))

    def prepare_json(self, save_path: str):
        json_data = open_json(f"{self.data_root_path}/{self.data_name}.json")
        written = missing = 0
        output_path = Path(save_path) / f"{self.data_name}.jsonl"
        with output_path.open("w", encoding="utf-8") as output:
            for instance in tqdm(json_data, desc = f"Mapping {self.data_name}"):
                matches = self.available_ecgs.get(instance["id"])
                if not matches:
                    missing += 1
                    continue
                preprocessed_conversation = preprocess_conversation(instance["conversations"])
                for match in matches:
                    line = {"ecg_path": match,
                            "text": preprocessed_conversation}
                    output.write(json.dumps(line, ensure_ascii=False) + "\n")
                    written += 1
        print(f"Write {written} rows; skipped {missing}")
