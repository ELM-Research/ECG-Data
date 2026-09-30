import torch
import pandas as pd
from tqdm import tqdm
from transformers import pipeline
from ecg_data.preprocess.ecg_datasets.common import open_wfdb

class PTB_XL:
    def __init__(self, data_name: str, data_root_path: str):
        self.data_name = data_name
        self.data_root_path = data_root_path

    def open_data(self, row):
        ecg, fields = open_wfdb(f"{self.data_root_path}/{row['path']}")
        ecg = ecg.T  # WFDB returns (time, lead) --> (lead, time).
        return {"file_path": row["path"], "ecg" : ecg,
                "sf" : fields["fs"], "file_name" : row["path"].replace("/", "_"),
                "reports_physician": row["report"], "current_order": fields["sig_name"]}

    def prepare_df(self,):
        ptbxl_database = pd.read_csv(f"{self.data_root_path}/ptbxl_database.csv", index_col="ecg_id")
        ptbxl_database = ptbxl_database.rename(columns={"filename_hr": "path"})
        df = ptbxl_database[["path", "report"]]
        df = self.translate(df)
        df.to_csv(f"{self.data_root_path}/preprocessed_{self.data_name}.csv", index=False)
        return df
    
    def translate(self, df, batch_size = 24):
        pipe = pipeline("image-text-to-text", model="google/translategemma-27b-it", 
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