import pandas as pd
from datasets import load_dataset
import glob
import os
from tqdm import tqdm
from pathlib import Path

from configs.constants import DATA_DIR

from ecg_datasets.base.base_dataset import BaseDataset

class CSN(BaseDataset):
    def __init__(self, args):
        super().__init__(args)
    
    def prepare_df(self, ):
        hf_dataset = load_dataset("PULSE-ECG/ECGBench", name="csn-test-no-cot", streaming=False, cache_dir="./../.huggingface")
        csn_paths = glob.glob(f"{DATA_DIR}/csn/WFDBRecords/*/*/*.hea")
        csn_filename_to_path = {os.path.basename(path).split(".")[0]: path.replace(".hea", "") for path in csn_paths}
        df = pd.DataFrame([])
        for item in tqdm(hf_dataset["test"], desc = "Preparing CSN DF"):
            file_path = item["image_path"]
            file_name = file_path.split("/")[-1].split("-")[0]
            conversations = item["conversations"]
            if file_name in csn_filename_to_path:
                new_row = pd.DataFrame({
                    "path": [csn_filename_to_path[file_name]],
                    "report": [conversations],
                    "orig_file_name": [file_name],
                })
                df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(f"{DATA_DIR}/{self.args.base}/{self.args.base}.csv", index=False)

    def open_ecg(self, row,):
        row_path = row["path"]
        report = row["report"]
        ecg, sf = self.open_wfdb(row_path)
        assert sf == 500 and ecg.shape == (5000, 12)
        return {"file_path": row_path, "ecg" : ecg, 
                "sf" : sf, "file_name" : Path(row_path).stem,
                "report": report}