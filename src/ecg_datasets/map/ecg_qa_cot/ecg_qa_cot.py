import glob
from pathlib import Path
import pandas as pd

from ecg_datasets.map.map_dataset import MapDataset
from utils.file_dir import open_json
from configs.constants import DATA_DIR

SPLIT = "train"  # test


class ECGQACot(MapDataset):
    def __init__(self, args):
        super().__init__(args)
        self.saved_dir = f"{DATA_DIR}/ptb_xl/preprocessed_{self.args.segment_len}"
        self.save_dir_json = f"src/ecg_datasets/map/ecg_qa_cot/{self.args.map}_{SPLIT}_hf.json"
        self.setup_ecg_qa()

    def get_map_data(self):
        self.available_ecgs.update(f.stem for f in Path(self.saved_dir).glob("*"))
        df = pd.read_csv(f"../ecg_qa_cot/ecg_qa_cot_{SPLIT}.csv")
        return df.to_dict(orient="records")

    def process_instance(self, instance):
        key = (instance["ecg_id"], instance["sample_id"], instance["question_id"])
        matched = self.qa_index[key]

        return {
            "ecg_path": "_".join(matched["ecg_path"][0].split("/")[3:]),
            "text": [
                {"from": "human", "value": instance["question"]},
                {"from": "gpt", "value": instance["answer"]},
            ],
            "saved_dir": self.saved_dir,
            "name": instance["question_type"],
        }

    def setup_ecg_qa(self, question_types=("single-verify", "single-choose", "single-query")):
        glob_paths = (
            glob.glob("src/ecg_datasets/map/ecg_qa/output/ptb_xl/paraphrased/*/*.json")
            + glob.glob("src/ecg_datasets/map/ecg_qa/output/ptb_xl/template/*/*.json")
        )

        self.data = []
        for fname in sorted(glob_paths):
            self.data.extend(
                item
                for item in open_json(fname)
                if item["question_type"] in question_types
            )

        self.qa_index = {
            (item["ecg_id"][0], item["sample_id"], item["question_id"]): item
            for item in self.data
        }
