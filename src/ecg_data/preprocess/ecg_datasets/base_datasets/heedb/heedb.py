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
        groups = sorted(glob.glob(f"{self.data_root_path}/I*"))
        for group in groups:
            metadata = pd.read_csv(f"{group}/metadata/metadata.csv")
            print(metadata.head()) 

