from tqdm import tqdm
from pathlib import Path
from ecg_data.preprocess.ecg_datasets.common import open_json, exact_string_removal, \
    ecg_placeholder_injection, append_jsonl

class PRETRAIN_MIMIC:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path
        self.available_ecgs = set()
        base_data_paths = ["/p01/whan/data/mimic_iv_ecg/preprocessed_250_10"]
        for base_data in base_data_paths:
            self.available_ecgs.update(str(f) for f in Path(base_data).glob("*/*.npy"))

        self.preprocessors = [exact_string_removal,
                              ecg_placeholder_injection]

    def prepare_json(self,):
        json_data = open_json(f"{self.data_root_path}/{self.data_name}.json")
        for instance in tqdm(json_data, desc = f"Mapping {self.data_name}"):
            ecg_path = "_".join(instance["ecg"].split("/"))
            preprocessed_conversation = self.preprocess_conversation(instance["conversations"])
            matches = [item for item in self.available_ecgs if ecg_path in item]
            for match in matches:
                line = {"ecg_path": match,
                        "text": preprocessed_conversation}
                append_jsonl(f"{self.data_root_path}/{self.data_name}.jsonl", line)

    def preprocess_value(self, text: str, role: str):
        for preprocessor in self.preprocessors:
            text = preprocessor(text, role)
        return text

    def preprocess_conversation(self, turns: list[dict]):
        return [
            {**turn, "value": self.preprocess_value(turn["value"], turn["from"])}
            for turn in turns
        ]
