from tqdm import tqdm

from utils.file_dir import save_json

class MapDataset:
    def __init__(self, args):
        self.args = args
        self.available_ecgs = set()
        self.valid_instances = []

    def map_data(self,):
        data = self.get_map_data()
        for instance in tqdm(data, desc=f"Mapping {self.args.map}"):
            processed_instance = self.process_instance(instance)
            if processed_instance is None:
                continue
            ecg_path = processed_instance["ecg_path"]
            saved_dir = processed_instance["saved_dir"]
            for i in range(100):
                if f"{ecg_path}_{i}" in self.available_ecgs:
                    self.valid_instances.append({
                        "ecg_path": f"{saved_dir}/{ecg_path}_{i}.npy",
                        "text": processed_instance["text"],
                        "name": processed_instance["name"],})
                    
        print(f"Total instances for {self.args.map}: {len(data)}")
        print(f"Length of available ecgs: {len(self.available_ecgs)}")
        print(f"Valid instances: {len(self.valid_instances)}")
        save_json(self.valid_instances, self.save_dir_json)


class SyntheticDataset:
    def __init__(self, args):
        self.args = args
        self.valid_instances = []

    def map_data(self,):
        data = self.get_map_data()                   
        print(f"Total instances for {self.args.map}: {len(data)}")
        save_json(data, self.save_dir_json)