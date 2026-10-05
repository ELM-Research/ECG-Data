import os
import json
import pandas as pd
from tqdm import tqdm
from pathlib import Path
from collections import defaultdict
from ecg_data.preprocess.ecg_datasets.common import preprocess_conversation

SPLIT = "test"
class ECG_QA_COT:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path
        self.available_ecgs = defaultdict(list)
        self.base_data_paths = ["/p01/whan/data/ptb_xl/preprocessed_250_10"]
        for base_data in self.base_data_paths:
            for path in Path(base_data).glob("*/*.npy"):
                unique_id = "_".join(path.stem.split("_")[-4:-1])
                self.available_ecgs[unique_id].append(str(path))

    def prepare_json(self, save_path: str):
        df = pd.read_csv(f"../ecg_qa_cot/ecg_qa_cot_{SPLIT}.csv")
        df = df.to_dict(orient="records")
        written = missing = 0
        output_path = Path(save_path) / f"{self.data_name}_{SPLIT}.jsonl"
        with output_path.open("w", encoding="utf-8") as output:
            for instance in tqdm(df, desc = f"Mapping {self.data_name}"):
                unique_id = self.parse_ecg_id(instance["ecg_id"])
                matches = self.available_ecgs.get(unique_id)
                if not matches:
                    missing += 1
                    continue
                preprocessed_conversation = self.preprocess_conversation(instance)
                for match in matches:
                    line = {"ecg_path": match,
                            "text": preprocessed_conversation}
                    output.write(json.dumps(line, ensure_ascii=False) + "\n")
                    written += 1
        print(f"Write {written} rows; skipped {missing}")

    def preprocess_conversation(self, instance):
        cot = instance["rationale"].split(". Answer:")[0]
        clinical_context = instance["clinical_context"]
        question = instance["question"]
        answer = instance["answer"]
        turns = [
                {"from": "human",
                 "value": f"Clinical Context: {clinical_context}\nQuestion: {question}"},
                {"from": "gpt",
                 "value": f"<think>\n{cot}\n</think>\n\n<answer>{answer}</answer>"},]
        return preprocess_conversation(turns)

    def parse_ecg_id(self, ecg_id: str) -> int:
        parsed_ecg_id = int(ecg_id.strip("[]"))
        return f"{int(parsed_ecg_id / 1000) * 1000:05d}_{parsed_ecg_id:05d}_hr"
