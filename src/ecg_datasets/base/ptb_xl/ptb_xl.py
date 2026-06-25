import pandas as pd
from transformers import pipeline
import torch
from tqdm import tqdm

from configs.constants import DATA_DIR

from ecg_datasets.base.base_dataset import BaseDataset

class PTB_XL(BaseDataset):
    def __init__(self, args):
        super().__init__(args)

    def prepare_df(self,):
        ptbxl_database = pd.read_csv(f"{DATA_DIR}/{self.args.base}/ptbxl_database.csv", index_col="ecg_id")
        ptbxl_database = ptbxl_database.rename(columns={"filename_hr": "path"})
        df = ptbxl_database[["path", "report"]]
        df = self.translate(df)
        df.to_csv(f"{DATA_DIR}/{self.args.base}/{self.args.base}.csv", index=False)
    
    def translate(self, df, batch_size = 24):
        pipe = pipeline("image-text-to-text", model="google/translategemma-12b-it", 
                        device="cuda", dtype=torch.bfloat16,)
        df = df.copy()
        reports = df["report"].tolist()
        messages = [[{"role": "user",
                     "content": [{"type": "text",
                                  "source_lang_code": "de",
                                  "target_lang_code": "en",
                                  "text": f"{report}",}],}] for report in reports]
        translated_reports = []
        for i in tqdm(range(0, len(messages), batch_size), desc = "Translating PTB-XL"):
            batch = messages[i:i + batch_size]
            outputs = pipe(text = batch, max_new_tokens = 256, batch_size = len(batch))
            translated_reports.extend([o[0]["generated_text"][-1]["content"] for o in outputs])
        df["report"] = translated_reports
        return df
    
    def open_ecg(self, row,):
        row_path = row["path"]
        report = row["report"]
        file_path = f"{DATA_DIR}/ptb_xl/{row_path}"
        ecg, sf = self.open_wfdb(file_path)
        assert sf == 500 and ecg.shape == (5000, 12)
        return {"file_path": file_path, "ecg" : ecg, 
                "sf" : sf, "file_name" : "_".join(row_path.split("/")),
                "report": report}