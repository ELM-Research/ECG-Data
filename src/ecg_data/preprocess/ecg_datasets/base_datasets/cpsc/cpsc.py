import os
import glob
import pandas as pd
from tqdm import tqdm
from pathlib import Path
from datasets import load_dataset
from ecg_data.preprocess.ecg_datasets.common import open_wfdb

class CPSC:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path

    def prepare_df(self, ):
        hf_dataset = load_dataset("PULSE-ECG/ECGBench", name="cpsc-test", streaming=False, cache_dir="./../.huggingface")
        cpsc_paths = glob.glob(f"{self.data_root_path}/training/*/*/*.hea")
        cpsc_filename_to_path = {os.path.basename(path).split(".")[0]: path.replace(".hea", "") for path in cpsc_paths}
        df = pd.DataFrame([])
        for item in tqdm(hf_dataset["test"], desc = "Preparing CPSC DF"):
            file_path = item["image_path"]
            file_name = file_path.split("/")[-1].split("-")[0]
            if file_name in cpsc_filename_to_path:
                new_row = pd.DataFrame({
                    "path": [cpsc_filename_to_path[file_name]],
                    "orig_file_name": [file_name],
                })
                df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(f"{self.data_root_path}/preprocessed_{self.data_name}.csv", index=False)
        return df

    def open_data(self, row,):
        ecg, fields = open_wfdb(row["path"])
        return {"file_path": row["path"], "ecg" : ecg.T,
                "sf" : fields["fs"], "file_name" : Path(row["path"]).stem,
                "current_order": fields["sig_name"]}