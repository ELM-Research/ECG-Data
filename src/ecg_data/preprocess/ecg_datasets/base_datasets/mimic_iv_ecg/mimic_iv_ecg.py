import pandas as pd
from ecg_data.preprocess.ecg_datasets.common import open_wfdb

class MIMIC_IV_ECG:
    def __init__(self, data_name: str, data_root_path: str):
        self.data_name = data_name
        self.data_root_path = data_root_path

    def open_data(self, row):
        ecg, fields = open_wfdb(f"{self.data_root_path}/{row['path']}")
        return {"file_path": f"{self.data_root_path}/{row['path']}", "ecg" : ecg.T,
                "sf" : fields["fs"], "file_name" : f"{self.data_root_path}/{row['path']}".replace("/", "_"),
                "reports_physician": row["report"], "current_order": fields["sig_name"]}

    def prepare_df(self, ):
        record_list = pd.read_csv(f"{self.data_root_path}/record_list.csv")
        machine_measurements = pd.read_csv(f"{self.data_root_path}/machine_measurements.csv")
        report_columns = [f"report_{i}" for i in range(18)]
        machine_measurements["report"] = machine_measurements[report_columns].apply(
            lambda x: ", ".join([str(val).lower() for val in x if pd.notna(val)]), axis=1
        )
        mm_columns = ["subject_id", "study_id"] + report_columns + ["report"]
        merged_df = pd.merge(
            record_list[["subject_id", "study_id", "file_name", "path"]], machine_measurements[mm_columns], on=["subject_id", "study_id"], how="inner"
        )
        merged_df = merged_df.dropna(subset=report_columns, how="all")
        df = merged_df[["path", "report"]]
        df.to_csv(f"{self.data_root_path}/preprocessed_{self.data_name}.csv", index=False)
        return df