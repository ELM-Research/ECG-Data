import pandas as pd
import glob

class HEEDB:
    def __init__(self, data_name: str, data_root_path: str):
        self.data_name = data_name
        self.data_root_path = data_root_path
        # diagnoses_dictionary.csv in I0001 and I0006 are identical when only comparing codes and diagnoses columns
        diagnoses_dic = pd.read_csv(f"{self.data_root_path}/I0006/12SL_diagnoses/diagnoses_dictionary.csv")
        # diagnoses_v241 = pd.read_csv(f"{self.groups[0]}/12SL_diagnoses/diagnoses_v24.csv")
        # print(diagnoses_v241.head())
        # diagnoses_v242 = pd.read_csv(f"{self.groups[1]}/12SL_diagnoses/diagnoses_v24.csv")
        # print(diagnoses_v242.head())

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
            diagnoses_acquisition["path"] = diagnoses_acquisition["FileName"]

            # Match site-specific prefixes while preserving the acquisition path.
            for df in [metadata, diagnoses_acquisition, diagnoses_v24]:
                df.dropna(subset=["FileName"], inplace=True)
                df["FileName"] = (
                    df["FileName"].str.removeprefix("./").str.removeprefix("/").str.removeprefix("WFDB/")
                )

            df = metadata.merge(diagnoses_acquisition, on="FileName", how="inner", validate="one_to_one")
            df = df.merge(diagnoses_v24, on="FileName", how="inner", validate="one_to_one")
            dfs.append(df[cols])

        df = pd.concat(dfs, ignore_index=True)
        df.to_csv(f"{self.data_root_path}/preprocessed_{self.data_name}.csv", index=False)
        return df