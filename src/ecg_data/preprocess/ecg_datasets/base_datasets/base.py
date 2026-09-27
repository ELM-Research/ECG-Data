import pandas as pd
import numpy as np
from tqdm import tqdm
from scipy import interpolate
from pathlib import Path
from ecg_data.preprocess.ecg_datasets.common import get_dataset_module

PTB_ORDER = ["I", "II", "III", "aVL", "aVR", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]

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

    def create_dataset(self, df):
        from concurrent.futures import ProcessPoolExecutor, as_completed
        skipped_count = 0
        
        try:
            with ProcessPoolExecutor(max_workers=self.args.num_cores) as executor:
                futures = [executor.submit(self.iterate_dataset, df.iloc[idx]) for idx in range(len(df))]
                for future in tqdm(as_completed(futures), total=len(futures), desc="Preprocessing ECGs..."):
                    try:
                        result = future.result()
                        if result is None:
                            skipped_count += 1
                    except Exception:
                        skipped_count += 1
        except Exception as e:
            print(f"Error in preprocess_instance: {e!s}")
        finally:
            print(f"Total instances skipped: {skipped_count}")

    def iterate_dataset(self, row):
        try:
            row_dict = row.to_dict()
            out = self.dataset_module.open_data(row_dict)
        except Exception as e:
            print(f"Error processing: {e!s}. Skipping this instance.")
            return None

    def unify_lead_order(self, ecg, current_order):
        if current_order == PTB_ORDER:
            return ecg
        order_mapping = {lead: index for index, lead in enumerate(current_order)}
        new_indices = [order_mapping[lead] for lead in PTB_ORDER]
        return ecg[:, new_indices]

    def nsample_ecg(self, ecg, orig_fs, target_fs):
        num_samples, num_leads = ecg.shape
        duration = num_samples / orig_fs
        t_original = np.linspace(0, duration, num_samples, endpoint=True)
        t_target = np.linspace(0, duration, int(num_samples * target_fs / orig_fs), endpoint=True)

        downsampled_data = np.zeros((len(t_target), num_leads))
        for lead in range(num_leads):
            f = interpolate.interp1d(t_original, ecg[:, lead], kind="cubic", 
                                     bounds_error=False, fill_value="extrapolate")
            downsampled_data[:, lead] = f(t_target)
        return downsampled_data


def build_base_dataset(cfg: dict):
    dataset_module = get_dataset_module(cfg["data_name"],
                                        cfg["data_root_path"],
                                        __package__)
    return BaseDataset(dataset_module, toy_dataset_fraction=cfg["toy_dataset_fraction"],
                       development=cfg["development"],)
