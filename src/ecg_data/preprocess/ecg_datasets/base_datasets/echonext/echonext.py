import numpy as np
import pandas as pd

from ecg_data.preprocess.ecg_datasets.base_datasets.base import PTB_ORDER

LABEL_TO_STATEMENT = {
    "lvef_lte_45_flag": "Left ventricular systolic dysfunction",
    "lvwt_gte_13_flag": "Left ventricular hypertrophy",
    "aortic_stenosis_moderate_or_greater_flag": "Moderate or greater aortic stenosis",
    "aortic_regurgitation_moderate_or_greater_flag": "Moderate or greater aortic regurgitation",
    "mitral_regurgitation_moderate_or_greater_flag": "Moderate or greater mitral regurgitation",
    "tricuspid_regurgitation_moderate_or_greater_flag": "Moderate or greater tricuspid regurgitation",
    "pulmonary_regurgitation_moderate_or_greater_flag": "Moderate or greater pulmonary regurgitation",
    "rv_systolic_dysfunction_moderate_or_greater_flag": "Right ventricular systolic dysfunction",
    "pericardial_effusion_moderate_large_flag": "Moderate or large pericardial effusion",
    "pasp_gte_45_flag": "Pulmonary hypertension",
    "tr_max_gte_32_flag": "Elevated tricuspid regurgitation velocity",
}

class ECHONEXT:
    def __init__(self, data_name: str, data_root_path: str):
        self.data_name = data_name
        self.data_root_path = data_root_path

    def prepare_df(self):
        metadata = pd.read_csv(f"{self.data_root_path}/echonext_metadata_100k.csv")
        # Waveforms are stored per split in EchoNext_<split>_waveforms.npy with row
        # order matching the metadata; split_idx is each record's row in that array.
        metadata["split_idx"] = metadata.groupby("split").cumcount()
        df = metadata[["split", "split_idx", *LABEL_TO_STATEMENT]]
        df.to_csv(f"{self.data_root_path}/preprocessed_{self.data_name}.csv", index=False)
        return df
        
    def open_data(self, row):
        split, idx = row["split"], int(row["split_idx"])
        path = f"{self.data_root_path}/EchoNext_{split}_waveforms.npy"
        # mmap so each worker materializes only its (2500, 12) slice, not the whole split.
        ecg = np.array(np.load(path, mmap_mode="r")[idx, 0]).T
        report = [text for col, text in LABEL_TO_STATEMENT.items() if row[col] == '1']
        return {"file_path": path, "ecg": ecg, "sf": 250,
                "file_name" : f"{split}_{idx}",
                "reports_physician": ", ".join(report) or "No significant structural heart disease",
                "current_order": ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]}