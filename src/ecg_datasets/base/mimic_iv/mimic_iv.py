import pandas as pd

from configs.constants import DATA_DIR, PTB_ORDER

from ecg_datasets.base.base_dataset import BaseDataset

class MIMIC_IV(BaseDataset):
    def __init__(self, args):
        super().__init__(args)
    
    def prepare_df(self, ):
        record_list = pd.read_csv(f"{DATA_DIR}/{self.args.base}/record_list.csv")
        machine_measurements = pd.read_csv(f"{DATA_DIR}/{self.args.base}/machine_measurements.csv")
        report_columns = [f"report_{i}" for i in range(18)]
        machine_measurements["report"] = machine_measurements[report_columns].apply(
            lambda x: " ".join([str(val) for val in x if pd.notna(val)]), axis=1
        )
        mm_columns = ["subject_id", "study_id"] + report_columns + ["report"]
        merged_df = pd.merge(
            record_list[["subject_id", "study_id", "file_name", "path"]], machine_measurements[mm_columns], on=["subject_id", "study_id"], how="inner"
        )
        merged_df = merged_df.dropna(subset=report_columns, how="all")
        df = merged_df[["path", "report"]]
        df.to_csv(f"{DATA_DIR}/{self.args.base}/{self.args.base}.csv", index=False)

    def open_ecg(self, row,):
        row_path = row["path"]
        report = row["report"]
        file_path = f"{DATA_DIR}/mimic_iv/{row_path}"
        ecg, sf = self.open_wfdb(file_path)
        assert sf == 500 and ecg.shape == (5000, 12)
        return {"file_path": file_path, "ecg" : ecg, 
                "sf" : sf, "file_name" : "_".join(row_path.split("/")),
                "report": report}
    
    def reorder_indices(self, ecg):
        current_order = ["I", "II", "III", "aVR", "aVF", "aVL", "V1", "V2", "V3", "V4", "V5", "V6"]
        order_mapping = {lead: index for index, lead in enumerate(current_order)}
        new_indices = [order_mapping[lead] for lead in PTB_ORDER]
        return ecg[:, new_indices]