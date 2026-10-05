import os
import json
import pandas as pd
from tqdm import tqdm
from pathlib import Path
from collections import defaultdict
from ecg_data.preprocess.ecg_datasets.common import open_json, exact_string_removal, \
    ecg_placeholder_injection

SPLIT = "train"
class ECG_QA_COT:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path
        self.available_ecgs = defaultdict(list)
        self.base_data_paths = ["/p01/whan/data/ptb_xl/preprocessed_250_10"]
        for base_data in self.base_data_paths:
            for path in Path(base_data).glob("*/*.npy"):
                # MIMIC-IV-ECG study IDs are unique; BaseDataset appends _<segment>.npy.
                print(path)
                # print(study_id)
                input()
                self.available_ecgs[0].append(str(path))

        self.preprocessors = [exact_string_removal,
                              ecg_placeholder_injection]

    def prepare_json(self, save_path: str):
        df = pd.read_csv(f"../ecg_qa_cot/ecg_qa_cot_{SPLIT}.csv")
        df = df.to_dict(orient="records")
        written = missing = 0
        output_path = Path(save_path) / f"{self.data_name}.jsonl"
        with output_path.open("w", encoding="utf-8") as output:
            for instance in tqdm(df, desc = f"Mapping {self.data_name}"):
                unique_id = self.get_ptbxl_ecg_path(self.parse_ecg_id(instance["ecg_id"]))
                print(unique_id)
                input()
                matches = self.available_ecgs.get(unique_id)
                if not matches:
                    missing += 1
                    continue
                preprocessed_conversation = self.preprocess_conversation(instance["conversations"])
                for match in matches:
                    line = {"ecg_path": match,
                            "text": preprocessed_conversation}
                    # output.write(json.dumps(line, ensure_ascii=False) + "\n")
                    written += 1
        print(f"Write {written} rows; skipped {missing}")

    def preprocess_value(self, text: str, role: str):
        for preprocessor in self.preprocessors:
            text = preprocessor(text, role)
        return text

    def preprocess_conversation(self, turns: list[dict]):
        return [
            {**turn, "value": self.preprocess_value(turn["value"], turn["from"])}
            for turn in turns
        ]

    def parse_ecg_id(self, ecg_id: str) -> int: return int(ecg_id.strip("[]"))

    def get_ptbxl_ecg_path(self, ecg_id: int) -> str:
        """Get the file path for a PTB-XL ECG record."""
        return os.path.join(
            "/p01/whan/data/ptb_xl/records500/",
            f"{int(ecg_id / 1000) * 1000:05d}",
            f"{ecg_id:05d}_hr"
        )

# SPLIT = "test"  # test


# class ECGQACot(MapDataset):
#     def __init__(self, args):
#         super().__init__(args)
#         self.saved_dir = f"{DATA_DIR}/ptb_xl/preprocessed_{self.args.segment_len}"
#         self.save_dir_json = f"src/ecg_datasets/map/ecg_qa_cot/{self.args.map}_{SPLIT}_hf.json"

#     def get_map_data(self):
#         self.available_ecgs.update(f.stem for f in Path(self.saved_dir).glob("*"))
#         df = pd.read_csv(f"../ecg_qa_cot/ecg_qa_cot_{SPLIT}.csv")
#         return df.to_dict(orient="records")

#     def process_instance(self, instance):
#         ecg_id_val = self.parse_ecg_id(instance["ecg_id"])
#         ecg_path = self.get_ptbxl_ecg_path(ecg_id_val)
#         cot = instance["rationale"].split(". Answer:")[0]
#         clinical_context = instance["clinical_context"]
#         question = instance["question"]
#         answer = instance["answer"]
#         human_value = f"Clinical Context: {clinical_context}\nQuestion: {question}"
#         gpt_value = f"<think>\n{cot}\n</think>\n\n<answer>{answer}</answer>"
#         return {
#             "ecg_path": "_".join(ecg_path.split("/")[3:]),
#             "text": [
#                 {"from": "human", "value": human_value},
#                 {"from": "gpt", "value": gpt_value},
#             ],
#             "saved_dir": self.saved_dir,
#             "name": instance["question_type"],
#         }

#     def parse_ecg_id(self, ecg_id_raw: str) -> int:
#         if ecg_id_raw is None:
#             raise ValueError("Missing ecg_id in CoT CSV row")
#         try:
#             ecg_id_clean = str(ecg_id_raw).strip().strip("[]").strip()
#             return int(ecg_id_clean)
#         except Exception as e:
#             raise ValueError(f"Failed to parse ecg_id '{ecg_id_raw}': {e}")

#     def get_ptbxl_ecg_path(self, ecg_id: int) -> str:
#         """Get the file path for a PTB-XL ECG record."""
#         return os.path.join(
#             "../data/ptb_xl/records500/",
#             f"{int(ecg_id / 1000) * 1000:05d}",
#             f"{ecg_id:05d}_hr"
#         )