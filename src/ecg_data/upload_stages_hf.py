"""Upload six training stages and two test benchmarks as private datasets."""

import argparse
from pathlib import Path

DATA_ROOT = Path("/p01/whan/data")
SPLITS = {
    "siglep-pretraining": "train",
    "orah-pretraining-1": "train",
    "orah-pretraining-2": "train",
    "orah-sft-1": "train",
    "orah-sft-2": "train",
    "orah-rl": "train",
    "ECG-QA-CoT-Benchmark": "test",
    "ECG-R1-Benchmark": "test",
}

# Counts from the training table are weights, not fixed sample limits.
# Each source is shuffled once, then partitioned across its listed stages.
SOURCES = {
    "heedb": (Path("/batch_data/heedb/heedb.jsonl"), {
        "siglep-pretraining": 1_927_353,
        "orah-pretraining-1": 642_451, "orah-pretraining-2": 5_996_208,
    }),
    "echonext": (DATA_ROOT / "echonext/echonext.jsonl", {
        "orah-pretraining-1": 24_763, "orah-pretraining-2": 57_780,
    }),
    # AGH combines Internal Datasets 1, 2, and 3.
    "agh": (Path("/batch_data/agh/agh.jsonl"), {
        "orah-pretraining-1": 149_929 + 65_445,
        "orah-pretraining-2": 349_835 + 152_706 + 11_460,
    }),
    "ecg_qa": (DATA_ROOT / "ecg_qa/ecg_qa.jsonl", {
        "orah-sft-1": 352_382, "orah-sft-2": 822_226,
    }),
    "pretrain_mimic": (DATA_ROOT / "pretrain_mimic/pretrain_mimic.jsonl", {
        "orah-sft-1": 502_687,
    }),
    "ecg_instruct_45k": (DATA_ROOT / "ecg_instruct_45k/ecg_instruct_45k.jsonl", {
        "orah-sft-1": 44_778,
    }),
    "ecg_grounding": (DATA_ROOT / "ecg_grounding/ecg_grounding_train.jsonl", {
        "orah-sft-1": 15_000, "orah-sft-2": 15_000,
    }),
    "ecg_instruct_pulse": (DATA_ROOT / "ecg_instruct_pulse/ecg_instruct_pulse.jsonl", {
        "orah-sft-2": 1_147_368,
    }),
    "ecg_protocol_gg_cot": (DATA_ROOT / "ecg_protocol_gg_cot/ecg_protocol_gg_cot_train_sft.jsonl", {
        "orah-sft-2": 30_000,
    }),
    "ecg_qa_cot": (DATA_ROOT / "ecg_qa_cot/ecg_qa_cot_train.jsonl", {
        "orah-sft-2": 159_313,
    }),
    "ecg_r1_rl": (DATA_ROOT / "ecg_protocol_gg_cot/ecg_protocol_gg_cot_train_rl.jsonl", {
        "orah-rl": 3_948,
    }),
    "ecg_qa_cot_test": (DATA_ROOT / "ecg_qa_cot/ecg_qa_cot_test.jsonl", {
        "ECG-QA-CoT-Benchmark": 1,
    }),
    "ecg_protocol_gg_cot_test": (DATA_ROOT / "ecg_protocol_gg_cot/ecg_protocol_gg_cot_test.jsonl", {
        "ECG-R1-Benchmark": 1,
    }),
}


def split_ranges(size, weights):
    """Allocate every row once, rounding cumulative table proportions."""
    start = cumulative = 0
    ranges = {}
    for stage, weight in weights.items():
        cumulative += weight
        stop = round(size * cumulative / sum(weights.values()))
        if stop == start:
            raise ValueError(f"Too few rows for {stage}.")
        ranges[stage] = range(start, stop)
        start = stop
    return ranges


def build_datasets(sources, seed):
    from datasets import concatenate_datasets, load_dataset

    parts = {name: [] for name in SPLITS}
    for name, (path, weights) in sources.items():
        data = load_dataset("json", data_files=str(path), split="train").shuffle(seed=seed)
        for stage, indices in split_ranges(len(data), weights).items():
            parts[stage].append(data.select(indices))
            print(f"{stage}: {name} = {len(indices):,}", flush=True)

    # Validate schemas for every stage before any upload.
    return {
        stage: concatenate_datasets(datasets).shuffle(seed=seed)
        for stage, datasets in parts.items()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", default=[], metavar="NAME=JSONL",
                        help="Override a JSONL path in SOURCES.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--mode", choices=["preview", "upload"], default="preview")
    args = parser.parse_args()

    sources = SOURCES.copy()
    for override in args.source:
        name, separator, path = override.partition("=")
        if name not in sources or not separator or not path:
            parser.error(f"Expected NAME=JSONL with NAME in {', '.join(sources)}.")
        sources[name] = (Path(path).expanduser(), sources[name][1])

    missing = [name for name, (path, _) in sources.items() if not path.is_file()]
    if missing:
        parser.error(f"Missing JSONLs for {', '.join(missing)}. Set each with --source NAME=JSONL.")

    datasets = build_datasets(sources, args.seed)
    for name, data in datasets.items():
        print(f"ELM-Research/{name} ({SPLITS[name]}): {len(data):,} rows", flush=True)
    if args.mode == "preview":
        return

    from huggingface_hub import HfApi

    api = HfApi()
    for name in datasets:
        repo_id = f"ELM-Research/{name}"
        api.create_repo(repo_id, repo_type="dataset", visibility="private", exist_ok=True)
        if not api.repo_info(repo_id, repo_type="dataset").private:
            raise ValueError(f"{repo_id} already exists and is not private.")

    for name, data in datasets.items():
        repo_id = f"ELM-Research/{name}"
        data.push_to_hub(repo_id, split=SPLITS[name], private=True)
        print(f"Uploaded https://huggingface.co/datasets/{repo_id}", flush=True)


if __name__ == "__main__":
    main()
