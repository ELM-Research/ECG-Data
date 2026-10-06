import json
import numpy as np
from pathlib import Path
from ecg_data.preprocess.config.load import get_config

def read_reports(data_path, data_name):
    if data_name == "agh":
        for path in sorted(Path(data_path).glob("*.json")):
            for instance in json.loads(path.read_text()):
                yield (
                    "agh",
                    instance.get("OriginalDiagnosis"),
                    instance.get("Diagnosis"),
                )
        return

    if data_name == "heedb":
        for path in sorted(Path(data_path).glob("*/*.npy")):
            instance = np.load(path, allow_pickle=True).item()
            physician = instance.get("reports_physician")
            yield "heedb_old", instance.get("reports_software_old"), physician
            yield "heedb_new", instance.get("reports_software_new"), physician
        return

    raise ValueError(f"Unknown dataset: {data_name}")

if __name__ == "__main__":
    cfg = get_config()