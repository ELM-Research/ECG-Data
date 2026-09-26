from importlib import import_module


def get_dataset_module(data_name: str, data_root_path: str, package: str):
    module = import_module(f"{package}.{data_name}.{data_name}")
    dataset = getattr(module, data_name.upper())
    return dataset(data_name, data_root_path)