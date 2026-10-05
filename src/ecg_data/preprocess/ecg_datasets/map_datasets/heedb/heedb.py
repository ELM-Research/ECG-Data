import json
import numpy as np
from tqdm import tqdm
from pathlib import Path
from multiprocessing import Pool
from ecg_data.preprocess.ecg_datasets.common import ecg_placeholder_injection

class HEEDB:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path
        self.preprocessors = [ecg_placeholder_injection]

    def prepare_json(self, save_path: str):
        output_path = Path(save_path) / f"{self.data_name}.jsonl"
        instances = Path(self.data_root_path).glob("*/*.npy")
        with Pool() as pool, output_path.open("w", encoding="utf-8") as output:
            lines = pool.imap(self._map_instance, instances, chunksize=64)
            for line in tqdm(lines, desc=f"Mapping {self.data_name}"):
                output.write(line + "\n")

    def _map_instance(self, instance: Path):
        np_file = np.load(instance, allow_pickle=True).item()
        line = {"ecg_path": str(instance),
                "text": self.preprocess_report(np_file["reports_physician"])}
        return json.dumps(line, ensure_ascii=False)

    def preprocess_report(self, report: list):
        joined_report = "; ".join(report)
        return f"<ecg>\n{joined_report}"
