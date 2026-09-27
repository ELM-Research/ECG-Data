import pandas as pd
import numpy as np
from tqdm import tqdm
from fractions import Fraction
from multiprocessing import Pool
from scipy.signal import resample_poly
from pathlib import Path
from ecg_data.preprocess.ecg_datasets.common import get_dataset_module

PTB_ORDER = ["I", "II", "III", "aVL", "aVR", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]

class BaseDataset:
    def __init__(self, dataset_module,
                 target_sf : int = 250, # Hz
                 segment_length: int = 10, # Seconds
                 save_path: str = None,
                 toy_dataset_fraction: float | None = None,
                 development: bool = False,
                 num_cores: int | None = None,
                 records_per_part: int = 100000,):
        self.records_per_part = records_per_part
        self.dataset_module = dataset_module
        self.data_root_path = self.dataset_module.data_root_path
        self.data_name = self.dataset_module.data_name
        self.target_sf = target_sf
        self.segment_length = segment_length
        self.toy_dataset_fraction = toy_dataset_fraction
        self.development = development
        self.num_cores = num_cores
        self.save_path = save_path
        Path(self.save_path).mkdir(parents=True, exist_ok=True)

    def get_df(self,):
        if Path(f"{self.data_root_path}/preprocessed_{self.data_name}.csv").exists():
            print("Getting dataframe...")
            df = pd.read_csv(f"{self.data_root_path}/preprocessed_{self.data_name}.csv", dtype=str)
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
        rows = enumerate(row for _, row in df.iterrows())
        if self.development:
            for row in tqdm(rows, total=len(df), desc = f"Development: {self.development}"):
                self.iterate_dataset(row)
            return
        skipped_count = 0
        with Pool(processes=self.num_cores) as pool:
            results = pool.imap_unordered(self.iterate_dataset, rows, chunksize=64)
            for result in tqdm(results, total=len(df), desc="Preprocessing ECGs..."):
                if result is None:
                    skipped_count += 1
        print(f"Total instances skipped: {skipped_count}")

    def iterate_dataset(self, item):
        row_index, row = item
        try:
            row_dict = row.to_dict()
            out = self.dataset_module.open_data(row_dict)
            if out is None or any(
                value is None
                or (isinstance(value, (str, list)) and len(value) == 0)
                for value in out.values()
            ): return None # If any values do not exist, lets skip
            if np.any(np.isnan(out["ecg"])) or np.any(np.isinf(out["ecg"])): return None
            assert out["ecg"].shape[0] == 12, f"Unexpected ECG shape: {out['ecg'].shape}"
            ecg = self.unify_lead_order(out["ecg"], out["current_order"])
            if out["sf"] != self.target_sf: ecg = self.nsample_ecg(ecg, out["sf"])

            instances = [
                {**out, "ecg": segment, "sf": self.target_sf, "current_order": PTB_ORDER}
                for segment in self.segment_ecg(ecg)
            ]
            part = Path(self.save_path) / f"part_{row_index // self.records_per_part:06d}"
            part.mkdir(parents=True, exist_ok=True)
            for i in range(len(instances)):
                np.save(part / f"{out['file_name']}_{i}.npy", instances[i])
            return True
        except Exception as e:
            print(f"Error processing: {e!s}. Skipping this instance.")
            return None

    def unify_lead_order(self, ecg, current_order):
        if current_order == PTB_ORDER:
            return ecg
        order_mapping = {lead: index for index, lead in enumerate(current_order)}
        new_indices = [order_mapping[lead] for lead in PTB_ORDER]
        return ecg[new_indices, :]

    def nsample_ecg(self, ecg, orig_sf):
        ratio = Fraction(str(self.target_sf)) / Fraction(str(orig_sf))
        # Filter before downsampling; axis 1 is time for (lead, time) arrays.
        return resample_poly(ecg, ratio.numerator, ratio.denominator, axis=1)

    def segment_ecg(self, ecg):
        # non-overlapping segments
        samples = int(self.segment_length * self.target_sf)
        return [ecg[:, start:start + samples] for start in range(0, ecg.shape[1] - samples + 1, samples)]

def build_base_dataset(cfg: dict):
    dataset_module = get_dataset_module(cfg["data_name"],
                                        cfg["data_root_path"],
                                        __package__)
    return BaseDataset(dataset_module, target_sf = cfg["target_sf"],
                       segment_length=cfg["segment_length"],
                       save_path=cfg["save_path"],
                       toy_dataset_fraction=cfg["toy_dataset_fraction"],
                       development=cfg["development"],
                       num_cores=cfg["num_cores"],
                       records_per_part=cfg["records_per_part"],)
