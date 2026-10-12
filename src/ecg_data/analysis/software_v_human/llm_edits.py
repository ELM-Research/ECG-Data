"""Classify report edits with OpenRouter and save each result for later analysis."""

import json
import os
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from itertools import islice
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tqdm import tqdm

from ecg_data.analysis.software_v_human import edits
from ecg_data.analysis.software_v_human.reports import normalize_report, read_reports, report_files

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
CATEGORIES = ("preferential", "factual", "uncertain")
STATUSES = ("excluded", "unchanged", "classified", "skipped")
PROMPT_PATH = Path(__file__).parents[1] / "config/prompts/edits_task.txt"
INPUT_NORMALIZATION = {**edits.NORMALIZATION, "order": "preserve"}


def _unique_object(items):
    result = dict(items)
    if len(result) != len(items):
        raise ValueError("Duplicate JSON keys are not allowed.")
    return result


def _parse_output(content):
    if not isinstance(content, str):
        raise ValueError("Return a JSON object as text.")
    result = json.loads(content, object_pairs_hook=_unique_object)
    if not isinstance(result, dict) or set(result) != {"category", "explanation"}:
        raise ValueError("Return exactly the keys 'category' and 'explanation'.")
    if result["category"] not in CATEGORIES:
        raise ValueError("Category must be preferential, factual, or uncertain.")
    if not isinstance(result["explanation"], str) or not result["explanation"].strip():
        raise ValueError("Explanation must be a nonempty string of 3-5 sentences.")
    return result


def _request(messages, *, api_key, model, temperature, max_tokens, timeout):
    payload = {
        "model": model, "messages": messages, "temperature": temperature,
        "max_tokens": max_tokens, "response_format": {"type": "json_object"},
    }
    request = Request(ENDPOINT, data=json.dumps(payload).encode(), headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as error:
        if error.code in (400, 401, 402, 403, 404, 422):
            raise RuntimeError(f"OpenRouter HTTP {error.code}; check key, credit, and model settings.") from error
        raise
    if not isinstance(result, dict):
        raise ValueError("OpenRouter returned an invalid response envelope.")
    if result.get("error"):
        error = result["error"]
        if str(error.get("code")) in ("400", "401", "402", "403", "404", "422"):
            raise RuntimeError(f"OpenRouter error: {error}")
        raise URLError(str(error))
    return result


def _classify(software, physician, *, prompt, request, max_attempts):
    reports = {"software_report": software, "physician_report": physician}
    content = re.sub(r"\{(software_report|physician_report)\}",
                     lambda match: json.dumps(reports[match[1]], ensure_ascii=False), prompt)
    messages = [{"role": "user", "content": content}]
    attempts = []
    for number in range(1, max_attempts + 1):
        output = None
        attempt = {"number": number, "response": None, "error": None}
        attempts.append(attempt)
        try:
            response = request(messages)
            attempt["response"] = response
            try:
                output = response["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as error:
                raise ValueError("OpenRouter response has no assistant content.") from error
            result = _parse_output(output)
            return result, attempts
        except (URLError, TimeoutError) as error:
            attempt["error"] = str(error)
            if number < max_attempts:
                time.sleep(2 ** (number - 1))
        except ValueError as error:
            attempt["error"] = str(error)
            if isinstance(output, str):
                messages.append({"role": "assistant", "content": output})
            messages.append({"role": "user", "content": (
                f"Your previous output was incorrect: {error} "
                "Return only the required JSON object, with no extra keys or Markdown."
            )})
    return None, attempts


def _pairs(paths, data_name):
    for path in paths:
        for index, (source, software, physician) in enumerate(read_reports([path], data_name)):
            yield {"source": source, "file": str(path.resolve()), "pair_index": index}, software, physician


def _analyze_pair(item, *, empty_reports, classify):
    identity, software, physician = item
    comparison = edits.compare_reports(software, physician, empty_reports=empty_reports)
    record = {
        **identity, **comparison, "software_report": None, "physician_report": None,
        "status": "excluded", "category": None, "explanation": None, "attempts": [],
    }
    if comparison["change"] is None:
        return record
    record["software_report"] = list(normalize_report(software, **INPUT_NORMALIZATION))
    record["physician_report"] = list(normalize_report(physician, **INPUT_NORMALIZATION))
    if comparison["change"] == "unchanged":
        record["status"] = "unchanged"
        return record
    result, attempts = classify(record["software_report"], record["physician_report"])
    record.update(status="classified" if result else "skipped", attempts=attempts)
    if result:
        record.update(result)
    return record


def _count(counts, record):
    source = record["source"]
    if source not in counts:
        counts[source] = {key: Counter() for key in ("inputs", "statuses", "changes", "categories", "attempts")}
    current = counts[source]
    current["inputs"][record["input_status"]] += 1
    current["statuses"][record["status"]] += 1
    if record["change"] is not None:
        current["changes"][record["change"]] += 1
    if record["category"] is not None:
        current["categories"][record["category"]] += 1
    if record["attempts"]:
        current["attempts"][len(record["attempts"])] += 1


def summarize(counts, *, empty_reports, undefined_ratio):
    """Category rates use classified changed pairs; failed calls never become labels."""
    def ratio(numerator, denominator):
        return numerator / denominator if denominator else undefined_ratio

    results = {}
    for source, current in counts.items():
        total = sum(current["inputs"].values())
        statuses = current["statuses"]
        included = total - statuses["excluded"]
        changed = included - statuses["unchanged"]
        classified = statuses["classified"]
        results[source] = {
            "study": "llm_edits", "normalization": edits.NORMALIZATION,
            "llm_input_normalization": INPUT_NORMALIZATION,
            "empty_reports": empty_reports, "input_reports": total,
            "included_reports": included, "excluded_reports": statuses["excluded"],
            "input_status_counts": {key: current["inputs"][key] for key in edits.INPUTS},
            "status_counts": {key: statuses[key] for key in STATUSES},
            "report_counts": {key: current["changes"][key] for key in edits.CHANGES},
            "edited_reports": changed, "edit_rate": ratio(changed, included),
            "classified_reports": classified, "skipped_reports": statuses["skipped"],
            "classification_coverage": ratio(classified, changed),
            "skip_rate": ratio(statuses["skipped"], changed),
            "category_counts": {key: current["categories"][key] for key in CATEGORIES},
            "category_rates": {key: ratio(current["categories"][key], classified) for key in CATEGORIES},
            "attempt_counts": dict(current["attempts"]),
            "api_attempts": sum(number * count for number, count in current["attempts"].items()),
            "denominators": {
                "edit_rate": included, "category_rates": classified,
                "classification_coverage": changed, "skip_rate": changed,
            },
        }
    return results


def _save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def run_analysis(cfg):
    options = cfg.get("study_options", {})
    empty_reports = options.get("empty_reports", "exclude")
    edits.compare_reports([], [], empty_reports=empty_reports)
    settings = {"temperature": 0, "max_tokens": 1024, "timeout": 120, "max_attempts": 3,
                **cfg.get("llm", {})}
    model = settings.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Set llm.model to an OpenRouter model ID.")
    for key in ("max_attempts", "max_tokens"):
        if type(settings[key]) is not int or settings[key] < 1:
            raise ValueError(f"llm.{key} must be a positive integer.")
    if settings["timeout"] <= 0:
        raise ValueError("llm.timeout must be positive.")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Set OPENROUTER_API_KEY in your environment.")
    batch_size = 1 if cfg["development"] else cfg.get("reports_per_batch", 8)
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("reports_per_batch must be a positive integer.")
    prompt = PROMPT_PATH.read_text()
    pairs = _pairs(report_files(cfg["data_path"], cfg["data_name"]), cfg["data_name"])
    batch = tuple(islice(pairs, batch_size))
    if not batch:
        raise ValueError(f"No {cfg['data_name']} report pairs in {cfg['data_path']}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = Path(cfg["save_path"]) / "llm_edits" / cfg["data_name"] / run_id
    output.mkdir(parents=True)
    metadata = {
        "run_id": run_id, "completed": False, "endpoint": ENDPOINT, "llm": settings,
        "data_name": cfg["data_name"], "data_path": str(Path(cfg["data_path"]).resolve()),
        "development": cfg["development"], "reports_per_batch": batch_size,
        "normalization": edits.NORMALIZATION, "empty_reports": empty_reports,
        "llm_input_normalization": INPUT_NORMALIZATION,
        "undefined_ratio": cfg["undefined_ratio"], "prompt": prompt,
    }
    _save(output / "run.json", metadata)
    print(f"Saving {output}")
    request = partial(_request, api_key=api_key, **{key: settings[key] for key in (
        "model", "temperature", "max_tokens", "timeout",
    )})
    classify = partial(_classify, prompt=prompt, request=request, max_attempts=settings["max_attempts"])
    worker = partial(_analyze_pair, empty_reports=empty_reports, classify=classify)
    counts = {}
    results = {}
    with (output / "pairs.jsonl").open("w") as file, ThreadPoolExecutor(max_workers=batch_size) as pool:
        with tqdm(desc="llm_edits", unit="pair") as progress:
            while batch:
                for record in pool.map(worker, batch):
                    file.write(json.dumps(record, allow_nan=False) + "\n")
                    file.flush()
                    _count(counts, record)
                    progress.update()
                    if cfg["development"]:
                        print(json.dumps(record, indent=2, allow_nan=False))
                results = summarize(counts, empty_reports=empty_reports, undefined_ratio=cfg["undefined_ratio"])
                _save(output / "summary.json", results)
                if cfg["development"] and input("Enter for next pair; q to stop: ").strip().lower() == "q":
                    break
                batch = tuple(islice(pairs, batch_size))
            else:
                metadata["completed"] = True
    _save(output / "run.json", metadata)
    for source, metrics in results.items():
        print(f"{source}: classified={metrics['classified_reports']}; skipped={metrics['skipped_reports']}; "
              f"excluded={metrics['excluded_reports']}; inputs={metrics['input_status_counts']}")
    return results
