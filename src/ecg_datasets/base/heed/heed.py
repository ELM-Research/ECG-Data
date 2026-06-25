import pandas as pd
import glob
import os


from ecg_datasets.base.base_dataset import BaseDataset
from configs.constants import DATA_DIR, PTB_ORDER

class HEED(BaseDataset):
    def __init__(self, args):
        super().__init__(args)
        self.group_dirs = sorted(glob.glob(f"{DATA_DIR}/HEED/I*"))
        diagnoses_dic = pd.read_csv(f"{self.group_dirs[0]}/12SL_diagnoses/diagnoses_dictionary.csv")
        self.code_to_diagnosis = dict(zip(diagnoses_dic["codes"], diagnoses_dic["diagnoses"]))

    def prepare_df(self,):
        cols = ["FileName", "codes_physician", "codes_software"]
        dfs = []
        for group_dir in self.group_dirs:
            acq = pd.read_csv(f"{group_dir}/12SL_diagnoses/diagnoses_acquisition.csv").dropna(subset=cols)[cols]
            acq["path"] = os.path.basename(group_dir) + "/WFDB" + acq["FileName"]
            dfs.append(acq)
        df = pd.concat(dfs, ignore_index=True)[["path", "codes_physician", "codes_software"]]
        df.to_csv(f"{DATA_DIR}/{self.args.base}/{self.args.base}.csv", index=False)

    def map_codes(self, codes):
        return [self.code_to_diagnosis[int(c)] for c in str(codes).split(",") if int(c) in self.code_to_diagnosis]

    def open_ecg(self, row,):
        file_path = f"{DATA_DIR}/HEED/{row['path']}"
        ecg, sf = self.open_wfdb(file_path)
        return {"file_path": file_path, "ecg" : ecg,
                "sf" : sf, "file_name" : "_".join(row["path"].split("/")),
                "report": self.map_codes(row["codes_physician"]),
                "muse_report": self.map_codes(row["codes_software"])}
    
    def reorder_indices(self, ecg):
        current_order = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
        order_mapping = {lead: index for index, lead in enumerate(current_order)}
        new_indices = [order_mapping[lead] for lead in PTB_ORDER]
        return ecg[:, new_indices]