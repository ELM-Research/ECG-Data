import argparse
import json

from datasets import load_dataset
from huggingface_hub import HfApi


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine JSONL files and upload to ELM-Research.")
    parser.add_argument("--jsonl", nargs="+", required=True, help="JSONL files with matching schemas.")
    parser.add_argument("--name", required=True, help="Dataset name without the organization.")
    parser.add_argument("--visibility", choices=["private", "public"], default="private")
    args = parser.parse_args()

    # dataset = load_dataset("json", data_files=args.jsonl, split="train")
    repo_id = f"ELM-Research/{args.name}"
    # api = HfApi()
    # api.create_repo(repo_id, repo_type="dataset", visibility=args.visibility, exist_ok=True)
    # api.update_repo_settings(repo_id, repo_type="dataset", visibility=args.visibility)
    # dataset.push_to_hub(repo_id, split="train")
    # print(f"Uploaded {len(dataset)} rows: https://huggingface.co/datasets/{repo_id}")

    uploaded = load_dataset(repo_id, split="train", streaming=True)
    for instance in uploaded:
        print(instance)
        print(instance["ecg_path"])
        break