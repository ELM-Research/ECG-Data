import json
import glob
from tqdm import tqdm
from pathlib import Path
from collections import defaultdict
from ecg_data.preprocess.ecg_datasets.common import open_json, preprocess_conversation

class ECG_QA:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path
        self.available_ecgs = defaultdict(list)
        self.base_data_paths = ["/p01/whan/data/mimic_iv_ecg/preprocessed_250_10"]
        for base_data in self.base_data_paths:
            for path in Path(base_data).glob("*/*.npy"):
                # MIMIC-IV-ECG study IDs are unique; BaseDataset appends _<segment>.npy.
                unique_id = path.stem.rsplit("_", 2)[-2]
                self.available_ecgs[unique_id].append(str(path))

    def prepare_json(self, save_path: str):
        paraphrased_jsons = glob.glob(f"{self.data_root_path}/paraphrased/*/*.json")
        template_jsons = glob.glob(f"{self.data_root_path}/template/*/*.json")
        path_to_all_jsons = paraphrased_jsons + template_jsons
        data = self.setup_ecg_qa(path_to_all_jsons)
        written = missing = 0
        output_path = Path(save_path) / f"{self.data_name}.jsonl"
        with output_path.open("w", encoding="utf-8") as output:
            for instance in tqdm(data, desc = f"Mapping {self.data_name}"):
                unique_id = str(instance["ecg_id"][0])
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
        answer = " ".join(instance["answer"])
        turns = [{"role": "user", "content": instance["question"]},
                {"role": "assistant", "content": answer},]
        return preprocess_conversation(turns)
    
    def setup_ecg_qa(self, glob_paths):
        question_types=["single-verify", "single-choose", "single-query"]
        data = []
        for fname in sorted(glob_paths):
            loaded_file = open_json(fname)
            filtered_list = [item for item in loaded_file if item["question_type"] in question_types]
            data.extend(filtered_list)
        return data
