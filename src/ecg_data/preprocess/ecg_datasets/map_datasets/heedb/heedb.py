import json
import numpy as np
from tqdm import tqdm
from pathlib import Path
from ecg_data.preprocess.ecg_datasets.common import ecg_placeholder_injection

class HEEDB:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path
        self.preprocessors = [ecg_placeholder_injection]

    def prepare_json(self, save_path: str):
        output_path = Path(save_path) / f"{self.data_name}.jsonl"
        with output_path.open("w", encoding="utf-8") as output:
            for instance in tqdm(Path(self.data_root_path).glob("*/*.npy"),
                                 desc = f"Mapping {self.data_name}"):
                np_file = np.load(instance, allow_pickle=True).item()
                preprocessed_conversation = self.preprocess_report(np_file["reports_physician"])
                line = {"ecg_path": str(instance),
                        "text": preprocessed_conversation}
                output.write(json.dumps(line, ensure_ascii=False) + "\n")

    def preprocess_report(self, report: list):
        joined_report = "; ".join(report)
        return f"<ecg>\n{joined_report}"