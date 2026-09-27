import pandas as pd
import glob
import os

class HEEDB:
    def __init__(self, data_name: str, data_root_path: str):
        self.data_name = data_name
        self.data_root_path = data_root_path
        # diagnoses_dictionary.csv in I0001 and I0006 are identical when only comparing codes and diagnoses columns
        diagnoses_dic = pd.read_csv(f"{self.data_root_path}/I0006/12SL_diagnoses/diagnoses_dictionary.csv")

    def prepare_df(self,):
        cols = ["path", "codes_physician", "codes_software_old", "codes_software_new"]
        groups = sorted(glob.glob(f"{self.data_root_path}/I*"))
        dfs = []
        for group in groups:
            metadata = pd.read_csv(f"{group}/metadata/metadata.csv", usecols=["FileName"], dtype=str)
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