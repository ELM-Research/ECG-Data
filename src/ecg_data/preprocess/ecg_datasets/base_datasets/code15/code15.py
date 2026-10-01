import h5py
import pandas as pd

class CODE15:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path

    def open_data(self, row):
        with h5py.File(row["path"], "r") as f:
            ecg = f["tracings"][int(row["idx"])].T
        return {"file_path": row["path"], "ecg" : ecg, 
                "sf" : 400, "file_name" : row["exam_id"],
                "current_order": ['I', 'II', 'III', 'AVR', 'AVL', 'AVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']}

    def prepare_df(self, ):
        exam_mapping = self.build_code15_h5py()
        df = pd.DataFrame([{"exam_id": exam_id,
                            "path": file_path,
                            "idx": idx,
                            }
            for exam_id, (file_path, idx) in exam_mapping.items()
        ])
        df.to_csv(f"{self.data_root_path}/preprocessed_{self.data_name}.csv", index=False)
        return df
    
    def build_code15_h5py(self):
        mapping = {}
        for part in range(18):
            file_path = f"{self.data_root_path}/exams_part{part}.hdf5"
            with h5py.File(file_path, "r") as f:
                exam_ids = f["exam_id"][:]
                for idx, eid in enumerate(exam_ids):
                    if isinstance(eid, bytes):
                        eid = eid.decode("utf-8")
                    eid = str(int(eid))
                    mapping[eid] = (file_path, idx)
        return mapping