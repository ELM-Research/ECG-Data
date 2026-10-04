import json
from collections import defaultdict
from tqdm import tqdm
from pathlib import Path
from ecg_data.preprocess.ecg_datasets.common import open_json, exact_string_removal, \
    ecg_placeholder_injection

class PRETRAIN_MIMIC:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path
        self.ecgs_by_study = defaultdict(list)
        base_data_paths = ["/p01/whan/data/mimic_iv_ecg/preprocessed_250_10"]
        for base_data in base_data_paths:
            for path in Path(base_data).glob("*/*.npy"):
                # MIMIC-IV-ECG study IDs are unique; BaseDataset appends _<segment>.npy.
                study_id = path.stem.rsplit("_", 2)[-2]
                self.ecgs_by_study[study_id].append(str(path))

        self.preprocessors = [exact_string_removal,
                              ecg_placeholder_injection]

    def prepare_json(self, save_path: str):
        json_data = open_json(f"{self.data_root_path}/{self.data_name}.json")
        output_path = Path(save_path) / f"{self.data_name}.jsonl"
        with output_path.open("w", encoding="utf-8") as output:
            for instance in tqdm(json_data, desc = f"Mapping {self.data_name}"):
                study_id = Path(instance["ecg"]).stem
                matches = self.ecgs_by_study.get(study_id)
                if not matches:
                    continue
                preprocessed_conversation = self.preprocess_conversation(instance["conversations"])
                for match in matches:
                    line = {"ecg_path": match,
                            "text": preprocessed_conversation}
                    output.write(json.dumps(line, ensure_ascii=False) + "\n")

    def preprocess_value(self, text: str, role: str):
        for preprocessor in self.preprocessors:
            text = preprocessor(text, role)
        return text

    def preprocess_conversation(self, turns: list[dict]):
        return [
            {**turn, "value": self.preprocess_value(turn["value"], turn["from"])}
            for turn in turns
        ]
