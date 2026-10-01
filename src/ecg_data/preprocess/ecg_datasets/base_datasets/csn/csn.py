import os
import glob
import pandas as pd
from tqdm import tqdm
from pathlib import Path
from datasets import load_dataset
from ecg_data.preprocess.ecg_datasets.common import open_wfdb

class CSN:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path

    def prepare_df(self, ):
        hf_dataset = load_dataset("PULSE-ECG/ECGBench", name="csn-test-no-cot", streaming=False)
        csn_paths = glob.glob(f"{self.data_root_path}/WFDBRecords/*/*/*.hea")
        csn_filename_to_path = {os.path.basename(path).split(".")[0]: path.replace(".hea", "") for path in csn_paths}
        df = pd.DataFrame([])
        for item in tqdm(hf_dataset["test"], desc = "Preparing CSN DF"):
            file_path = item["image_path"]
            file_name = file_path.split("/")[-1].split("-")[0]
            if file_name in csn_filename_to_path:
                new_row = pd.DataFrame({
                    "path": [csn_filename_to_path[file_name]],
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