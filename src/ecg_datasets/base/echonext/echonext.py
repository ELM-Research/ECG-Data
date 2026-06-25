import numpy as np
import pandas as pd

from ecg_datasets.base.base_dataset import BaseDataset
from configs.constants import DATA_DIR, PTB_ORDER

# Each positive echo-derived binary flag contributes one diagnosis statement,
# yielding a list-of-findings report built solely from the metadata labels.
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

class EchoNext(BaseDataset):
    def __init__(self, args):
        super().__init__(args)
        self.root_dir = f"{DATA_DIR}/{args.base}/1.1.1"

    def prepare_df(self):
        print("Preparing DF")
        metadata = pd.read_csv(f"{self.root_dir}/EchoNext_metadata_100k.csv")
        # Waveforms are stored per split in EchoNext_<split>_waveforms.npy with row
        # order matching the metadata; split_idx is each record's row in that array.
        metadata["split_idx"] = metadata.groupby("split").cumcount()
        df = metadata[["split", "split_idx", *LABEL_TO_STATEMENT]]
        df.to_csv(f"{DATA_DIR}/{self.args.base}/{self.args.base}.csv", index=False)
        print(f"Prepared {len(df)} records: {metadata['split'].value_counts().to_dict()}")

    def open_ecg(self, row):
        split, idx = row["split"], row["split_idx"]
        path = f"{self.root_dir}/EchoNext_{split}_waveforms.npy"
        # mmap so each worker materializes only its (2500, 12) slice, not the whole split.
        ecg = np.array(np.load(path, mmap_mode="r")[idx, 0])
        assert ecg.shape == (2500, 12)  # 10 s, 12-lead at 250 Hz
        report = [text for col, text in LABEL_TO_STATEMENT.items() if row[col] == 1]
        return {"file_path": path, "ecg": ecg, "sf": 250,
                "file_name": f"{self.args.base}_{split}_{idx}",
                "report": report or ["No significant structural heart disease"]}

    def reorder_indices(self, ecg):
        current_order = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
        order_mapping = {lead: index for index, lead in enumerate(current_order)}
        new_indices = [order_mapping[lead] for lead in PTB_ORDER]
        return ecg[:, new_indices]
