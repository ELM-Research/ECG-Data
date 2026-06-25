import pandas as pd
from typing import Tuple, Union
from tqdm import tqdm
import numpy as np
from pathlib import Path
import wfdb
from scipy import interpolate

from utils.file_dir import ensure_directory_exists
from configs.constants import DATA_DIR

class BaseDataset:
    def __init__(self, args):
        self.args = args
        self.save_dir = f"{DATA_DIR}/{self.args.base}/preprocessed_{self.args.segment_len}"
        ensure_directory_exists(folder = self.save_dir)

    def get_df(self,):
        print("Getting dataframe...")
        df = pd.read_csv(f"{DATA_DIR}/{self.args.base}/{self.args.base}.csv")
        print("Dataframe retrieved.")
        print("Cleaning dataframe...")
        df = self.clean_dataframe(df)
        print("Dataframe cleaned.")
        if self.args.dev:
            print("Dev mode is on. Reducing dataframe size to 1000 instances...")
            df = df.iloc[:1000]
        if self.args.toy:
            print(f"Toy mode is on. Reducing dataframe size to {self.args.toy} of original size...")
            df = df.sample(frac=self.args.toy, random_state=42).reset_index(drop=True)
        print("Dataframe retrieved and cleaned.")
        print(df.head())
        print(f"Number of instances in dataframe: {len(df)}")
        print("Dataframe prepared.")
        return df
    
    def clean_dataframe(self, df: "pd.DataFrame") -> Tuple["pd.DataFrame", bool, int]:
        has_nan = df.isna().any().any()
        if has_nan:
            rows_before = len(df)
            cleaned_df = df.dropna()
            dropped_rows = rows_before - len(cleaned_df)
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
            ecg_out = self.open_ecg(row_dict)
            report = ecg_out["report"]
            ecg = ecg_out["ecg"]
            sf = ecg_out["sf"]
            file_name = ecg_out["file_name"]

            if self.args.base in ("mimic_iv", "code15", "echonext"):
                ecg = self.reorder_indices(ecg)
            
            if sf != self.args.target_sf:
                downsampled_ecg = self.nsample_ecg(ecg, orig_fs=sf, target_fs=self.args.target_sf)
            else:
                downsampled_ecg = ecg
            
            segmented_ecg, segmented_report = self.segment_ecg(downsampled_ecg, report)
            assert len(segmented_report) == segmented_ecg.shape[0]
                        
            if np.any(np.isnan(segmented_ecg)) or np.any(np.isinf(segmented_ecg)):
                return None
            
            for i in range(len(segmented_report)):
                save_path = f"{self.save_dir}/{file_name}_{i}.npy"
                save_dic = {
                    "ecg" : np.transpose(segmented_ecg[i], (1, 0)),
                    "report" : segmented_report[i],
                    "ecg_path" : ecg_out["file_path"],
                    "original_sf" : sf,
                    "target_sf" : self.args.target_sf,
                    "segment_len" : self.args.segment_len,
                    "npy_path" : save_path
                }
                
                np.save(save_path, save_dic)
            return True
        
        except Exception as e:
            print(f"Error processing: {e!s}. Skipping this instance.")
            return None
        
    def open_wfdb(self, path: Union[str, Path]):
        signal, fields = wfdb.rdsamp(path)
        print(f"fields: {fields}")
        return signal, fields["fs"]
    
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
    
    def check_nan_inf(self, ecg,):
        if np.any(np.isnan(ecg)) or np.any(np.isinf(ecg)):
            ecg = np.nan_to_num(ecg, nan=0.0, posinf=0.0, neginf=0.0)
        return ecg
    
    def segment_ecg(self, ecg, report,):
        time_length, _ = ecg.shape
        num_segments = time_length // self.args.segment_len

        ecg_data_segmented = []
        text_data_segmented = []

        for i in range(num_segments):
            start_idx = i * self.args.segment_len
            end_idx = (i + 1) * self.args.segment_len
            ecg_data_segmented.append(ecg[start_idx:end_idx, :])
            text_data_segmented.append(report)

        return np.array(ecg_data_segmented), text_data_segmented
