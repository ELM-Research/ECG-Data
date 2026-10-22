"""Estimate a new LLM edit run or summarize saved usage without inference requests."""

import argparse
import json
import math
from pathlib import Path
from urllib.request import urlopen

from tqdm import tqdm

from ecg_data.analysis.software_v_human import llm_edits
from ecg_data.analysis.software_v_human.reports import report_files
from ecg_data.preprocess.config.load import load_config

MODELS_URL = "https://openrouter.ai/api/v1/models"


def saved_usage(root):
    root = Path(root)
    run = json.loads((root / "run.json").read_text())
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
    coverage = dict.fromkeys(totals, 0)
    pairs = changed = attempts = 0
    incomplete = False
    with (root / "pairs.jsonl").open("rb") as file:
        for line in file:
            if not line.endswith(b"\n"):
                incomplete = True
                break
            record = json.loads(line)
            pairs += 1
            changed += record["change"] not in (None, "unchanged")
            for attempt in record["attempts"]:
                attempts += 1
                usage = (attempt.get("response") or {}).get("usage") or {}
                for key in totals:
                    value = usage.get(key)
                    if value is None:
                        continue
                    valid_type = type(value) in (int, float) if key == "cost" else type(value) is int
                    if not valid_type or not math.isfinite(value) or value < 0:
                        raise ValueError(f"Invalid saved usage.{key}: {value!r}")
                    totals[key] += value
                    coverage[key] += 1
    complete_cost = coverage["cost"] == attempts
    return {
        "model": run["llm"]["model"], "run": str(root.resolve()),
        "saved_pairs": pairs, "changed_pairs": changed, "api_attempts": attempts,
        "incomplete_tail_ignored": incomplete, "recorded_usage_totals": totals,
        "attempts_with_usage": coverage,
        "attempts_missing_usage": {key: attempts - count for key, count in coverage.items()},
        "recorded_total_usd": totals["cost"] if complete_cost else None,
        "recorded_usd_per_changed_pair": totals["cost"] / changed if complete_cost and changed else None,
        "scope": "saved pairs only, including all retry attempts; no extrapolation",
        "cost_source": "Saved OpenRouter response usage.cost in USD; no current-price lookup.",
        "missing_usage": "Known totals omit missing fields; total cost is null if any attempt lacks cost.",
    }


def _pricing(model):
    with urlopen(MODELS_URL, timeout=30) as response:
        models = json.load(response)["data"]
    entry = next((entry for entry in models if entry["id"] == model), None)
    if entry is None:
        raise ValueError(f"Model not found in OpenRouter's catalog: {model}")
    prices = {key: float(entry["pricing"][key]) for key in ("prompt", "completion")}
    prices["request"] = float(entry["pricing"].get("request", 0))
    if any(not math.isfinite(value) or value < 0 for value in prices.values()):
        raise ValueError(f"Model has no fixed nonnegative price: {model}")
    return prices


def estimate(cfg, *, chars_per_token=4, output_tokens=None):
    if cfg["experiment"] != "llm_edits":
        raise ValueError("This estimate requires experiment: llm_edits.")
    if not math.isfinite(chars_per_token) or chars_per_token <= 0:
        raise ValueError("chars_per_token must be positive and finite.")
    settings = cfg.get("llm", {})
    model = settings.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Set llm.model to an OpenRouter model ID.")
    max_tokens = settings.get("max_tokens", 1024)
    if type(max_tokens) is not int or max_tokens < 1:
        raise ValueError("llm.max_tokens must be a positive integer.")
    output_tokens = max_tokens if output_tokens is None else output_tokens
    if type(output_tokens) is not int or not 1 <= output_tokens <= max_tokens:
        raise ValueError("output_tokens must be between 1 and llm.max_tokens.")
    prices = _pricing(model)
    options = cfg.get("study_options", {})
    options = {"empty_reports": options.get("empty_reports", "exclude"),
               "truncate": options.get("truncate", []), "remove": options.get("remove", []),
               "skip": options.get("skip", [])}
    prompt = llm_edits.PROMPT_PATH.read_text()
    changed = input_tokens = total = excluded = unchanged = 0

    def count_tokens(software, physician):
        nonlocal changed, input_tokens
        content = llm_edits._messages(software, physician, prompt)[0]["content"]
        changed += 1
        input_tokens += math.ceil(len(content) / chars_per_token)
        return None, []

    pairs = llm_edits._pairs(report_files(cfg["data_path"], cfg["data_name"]), cfg["data_name"])
    for item in tqdm(pairs, desc="estimate_llm_edits", unit="pair"):
        record = llm_edits._analyze_pair(item, classify=count_tokens, **options)
        total += 1
        excluded += record["status"] == "excluded"
        unchanged += record["status"] == "unchanged"
    if not total:
        raise ValueError(f"No {cfg['data_name']} report pairs in {cfg['data_path']}")

    completion_tokens = changed * output_tokens
    input_cost = input_tokens * prices["prompt"]
    output_cost = completion_tokens * prices["completion"]
    request_cost = changed * prices["request"]
    return {
        "model": model, "scope": "full dataset, including any previously saved pairs",
        "input_pairs": total, "excluded_pairs": excluded, "unchanged_pairs": unchanged,
        "changed_pairs": changed, "estimated_requests": changed,
        "chars_per_token": chars_per_token, "output_tokens_per_request": output_tokens,
        "estimated_input_tokens": input_tokens, "estimated_output_tokens": completion_tokens,
        "pricing_source": MODELS_URL, "usd_per_token_or_request": prices,
        "estimated_input_usd": input_cost, "estimated_output_usd": output_cost,
        "estimated_request_usd": request_cost,
        "estimated_total_usd": input_cost + output_cost + request_cost,
        "assumptions": [
            "Input tokens approximate prompt characters divided by chars_per_token, rounded up per pair.",
            "One request per changed pair; retries and chat framing are excluded.",
            "Output uses llm.max_tokens unless --output-tokens is supplied; this is a budget assumption.",
            "Uses listed uncached prices; provider differences, caching, and credit purchase fees are excluded.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", help="Config for a full new-run estimate.")
    source.add_argument("--run", help="Existing run directory containing run.json and pairs.jsonl.")
    parser.add_argument("--chars-per-token", type=float, default=4,
                        help="Rough input token assumption (default: 4 characters per token).")
    parser.add_argument("--output-tokens", type=int,
                        help="Assumed output tokens per request (default: llm.max_tokens).")
    args = parser.parse_args()
    result = (saved_usage(args.run) if args.run else
              estimate(load_config(args.config), chars_per_token=args.chars_per_token,
                       output_tokens=args.output_tokens))
    print(json.dumps(result, indent=2, allow_nan=False))
