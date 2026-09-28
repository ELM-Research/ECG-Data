import glob
import json
import numpy as np
from pathlib import Path
from ecg_data.preprocess.config.load import get_config

def analyze_agh(data_path):
    KEYS_OF_INTEREST = ["Diagnosis", "OriginalDiagnosis"]
    for f in sorted(Path(data_path).glob("*.json")):
        json_file = json.loads(f.read_text())
        for instance in json_file:
            print(instance)
            input()

def analyze_heedb(data_path):
    for instance in glob.glob(f"{data_path}/*/*.npy"):
        np_file = np.load(instance, allow_pickle=True).item()
        print(np_file)
        input()

if __name__ == "__main__":
    cfg = get_config()
    print(cfg)
    if cfg["data_name"] == "agh":
        analyze_agh(cfg["data_path"])
    elif cfg["data_name"] == "heedb":
        analyze_heedb(cfg["data_path"])