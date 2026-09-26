from importlib import import_module


def _build_dataset(cfg: dict, package: str):
    name = cfg["data"]
    module = import_module(f"{package}.{name}.{name}")
    dataset = getattr(module, name.upper())
    return dataset(cfg)
