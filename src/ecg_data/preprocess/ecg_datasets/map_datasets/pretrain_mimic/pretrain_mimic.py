from ecg_data.preprocess.ecg_datasets.common import open_json
class PRETRAIN_MIMIC:
    def __init__(self, data_name: str, data_root_path: str,):
        self.data_name = data_name
        self.data_root_path = data_root_path

    def get_json(self):
        data = open_json(f"{self.data_root_path}/{self.data_name}.json")
        print(data)