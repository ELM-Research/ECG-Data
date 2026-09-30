import pandas as pd
import glob
import os
from ecg_data.preprocess.ecg_datasets.common import open_wfdb

class HEEDB:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path
        # diagnoses_dictionary.csv in I0001 and I0006 are identical when only comparing codes and diagnoses columns
        diagnoses_dic = pd.read_csv(f"{self.data_root_path}/I0006/12SL_diagnoses/diagnoses_dictionary.csv")
        self.code_to_diagnosis = dict(zip(diagnoses_dic["codes"], diagnoses_dic["diagnoses"]))

    def open_data(self, row):
        ecg, fields = open_wfdb(row["path"])
        ecg = ecg.T  # WFDB returns (time, lead) --> (lead, time).
        reports_physician = self.map_codes(row["codes_physician"])
        reports_software_old = self.map_codes(row["codes_software_old"])
        reports_software_new = self.map_codes(row["codes_software_new"])
        if any(not code_list for code_list in (reports_physician, reports_software_old, reports_software_new)):
            return None
        return {"file_path": row["path"], "ecg" : ecg,
                "sf" : fields["fs"], "file_name" : row["path"].replace("/", "_"),
                "ECGAcquisitionTime": row["ECGAcquisitionTime"],
                "reports_physician": reports_physician, # here reports are a list of strings
                "reports_software_old": reports_software_old,
                "reports_software_new": reports_software_new,
                "codes_physician": row["codes_physician"],
                "codes_software_old": row["codes_software_old"],
                "codes_software_new": row["codes_software_new"],
                "current_order": fields["sig_name"]}

    def map_codes(self, codes):
        return [self.code_to_diagnosis[int(c)] for c in str(codes).split(",") if int(c) in self.code_to_diagnosis]

    def prepare_df(self,):
        cols = ["path", "ECGAcquisitionTime", "codes_physician", "codes_software_old", "codes_software_new"]
        groups = sorted(glob.glob(f"{self.data_root_path}/I*"))
        dfs = []
        for group in groups:
            metadata = pd.read_csv(
                f"{group}/metadata/metadata.csv", usecols=["FileName", "ECGAcquisitionTime"], dtype=str,
            )
            diagnoses_v24 = pd.read_csv(
                f"{group}/12SL_diagnoses/diagnoses_v24.csv",
                usecols=["FileName", "codes"], dtype=str,
            ).rename(columns={"codes": "codes_software_new"})
            diagnoses_acquisition = pd.read_csv(
                f"{group}/12SL_diagnoses/diagnoses_acquisition.csv",
                usecols=["FileName", "codes_physician", "codes_software"], dtype=str,
            ).rename(columns={"codes_software": "codes_software_old"})

            # Normalizing path name
            for df in [metadata, diagnoses_acquisition, diagnoses_v24]:
                df.dropna(subset=["FileName"], inplace=True)
                df["FileName"] = (
                    df["FileName"].str.removeprefix("./").str.removeprefix("/")
                    .str.removeprefix("WFDB/").str.removesuffix(".hea\n")
                )

            # Inner merge csvs base on normalized FileName
            df = metadata.merge(diagnoses_acquisition, on="FileName", how="inner", validate="one_to_one")
            df = df.merge(diagnoses_v24, on="FileName", how="inner", validate="one_to_one")
            df["path"] = f"{group}/WFDB/" + df["FileName"]
            
            headers = df["path"] + ".hea"
            missing = headers[~headers.map(os.path.isfile)]
            if not missing.empty:
                raise FileNotFoundError(f"{len(missing)} missing")
            dfs.append(df[cols])

        df = pd.concat(dfs, ignore_index=True)
        df.to_csv(f"{self.data_root_path}/preprocessed_{self.data_name}.csv", index=False)
        return df
