import glob
from pathlib import Path

from ecg_datasets.map.map_dataset import MapDataset
from utils.file_dir import open_json
from configs.constants import DATA_DIR

class ECGQA(MapDataset):
    def __init__(self, args):
        super().__init__(args)
        if "mimic_iv" in self.args.map:
            self.data_name ="mimic_iv"
        elif "ptb_xl" in self.args.map:
            self.data_name = "ptb_xl"
        self.saved_dir = f"{DATA_DIR}/{self.data_name}/preprocessed_{self.args.segment_len}"
        self.save_dir_json = f"src/ecg_datasets/map/ecg_qa/{self.args.map}_hf.json"

    def get_map_data(self, ):
        self.available_ecgs.update(f.stem for f in Path(self.saved_dir).glob("*"))
        paraphrased_jsons = glob.glob(f"src/ecg_datasets/map/ecg_qa/output/{self.data_name}/paraphrased/*/*.json")
        template_jsons = glob.glob(f"src/ecg_datasets/map/ecg_qa/output/{self.data_name}/template/*/*.json")
        path_to_all_jsons = paraphrased_jsons + template_jsons
        data = self.setup_ecg_qa(path_to_all_jsons)
        return data
    
    def process_instance(self, instance):
        name = instance.get("name", "")
        text = [instance["question_type"], instance["question"], instance["answer"]]
        ecg_path = "_".join(instance["ecg_path"][0].split("/")[3:])
        return {"ecg_path": ecg_path, "text": text, 
                "saved_dir": self.saved_dir, "name": name,}

    def setup_ecg_qa(self, glob_paths, question_types=["single-verify", "single-choose", "single-query"]):
        data = []
        for fname in sorted(glob_paths):
            loaded_file = open_json(fname)
            filtered_list = [item for item in loaded_file if item["question_type"] in question_types]
            data.extend(filtered_list)
        return data