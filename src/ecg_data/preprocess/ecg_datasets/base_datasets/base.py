import pandas as pd
from pathlib import Path
from ecg_data.preprocess.ecg_datasets.common import get_dataset_module


class BaseDataset:
    def __init__(self, dataset_module,
                 toy_dataset_fraction: float | None = None,
                 development: bool = False,):
        self.dataset_module = dataset_module
        self.data_root_path = self.dataset_module.data_root_path
        self.data_name = self.dataset_module.data_name
        self.toy_dataset_fraction = toy_dataset_fraction
        self.development = development

    def get_df(self,):
        if Path(f"{self.data_root_path}/preprocessed_{self.data_name}.csv").exists():
            print("Getting dataframe...")
            df = pd.read_csv(f"{self.data_root_path}/preprocessed_{self.data_name}.csv")
        else: df = self.dataset_module.prepare_df()
        print("Dataframe retrieved.")
        print("Cleaning dataframe...")
        df = self.clean_dataframe(df)
        print("Dataframe cleaned.")
        if self.development:
            print("Dev mode is on. Reducing dataframe size to 1000 instances...")
            df = df.iloc[:1000]
        if self.toy_dataset_fraction:
            print(f"Toy mode is on. Reducing dataframe size to {self.toy_dataset_fraction} of original size...")
            df = df.sample(frac=self.toy_dataset_fraction, random_state=42).reset_index(drop=True)
        print("Dataframe retrieved and cleaned.")
        print(df.head())
        print(f"Number of instances in dataframe: {len(df)}")
        print("Dataframe prepared.")
        return df

    def clean_dataframe(self, df):
        has_nan = df.isna().any().any()
        if has_nan:
            cleaned_df = df.dropna()
            dropped_rows = len(df) - len(cleaned_df)
            print(f"Found and removed {dropped_rows} rows containing NaN values")
            print(f"Remaining rows: {len(cleaned_df)}")
            return cleaned_df
        print("No NaN values found in DataFrame")
        return df


def build_base_dataset(cfg: dict):
    dataset_module = get_dataset_module(cfg["data_name"],
                                        cfg["data_root_path"],
                                        __package__)
    return BaseDataset(dataset_module)
