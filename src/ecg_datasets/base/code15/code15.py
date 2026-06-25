import pandas as pd
import h5py

from configs.constants import DATA_DIR, PTB_ORDER

from ecg_datasets.base.base_dataset import BaseDataset

class CODE15(BaseDataset):
    def __init__(self, args):
        super().__init__(args)
    
    def prepare_df(self, ):
        exam_mapping = self.build_code15_h5py()
        df = pd.DataFrame([
            {
                "exam_id": exam_id,
                "path": file_path,
                "idx": idx,
                "report": "placeholder report",
            }
            for exam_id, (file_path, idx) in exam_mapping.items()
        ])
        df.to_csv(f"{DATA_DIR}/{self.args.base}/{self.args.base}.csv", index=False)

    def build_code15_h5py(self):
        mapping = {}
        for part in range(18):
            file_path = f"{DATA_DIR}/code15/exams_part{part}.hdf5"
            with h5py.File(file_path, "r") as f:
                exam_ids = f["exam_id"][:]
                for idx, eid in enumerate(exam_ids):
                    if isinstance(eid, bytes):
                        eid = eid.decode("utf-8")
                    eid = str(int(eid))
                    mapping[eid] = (file_path, idx)
        return mapping
    
    def open_ecg(self, row,):
        file_path = row["path"]
        tracing_idx = row["idx"]
        exam_id = row["exam_id"]
        report = row["report"]
        sf = 400
        with h5py.File(file_path, "r") as f:
            ecg = f["tracings"][tracing_idx]
        assert ecg.shape == (4096, 12)
        return {"file_path": file_path, "ecg" : ecg, 
                "sf" : sf, "file_name" : f"{exam_id}",
                "report": report}
    
    def reorder_indices(self, ecg):
        current_order = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
        order_mapping = {lead: index for index, lead in enumerate(current_order)}
        new_indices = [order_mapping[lead] for lead in PTB_ORDER]
        return ecg[:, new_indices]