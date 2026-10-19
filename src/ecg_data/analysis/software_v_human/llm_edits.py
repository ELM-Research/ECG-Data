"""Classify report edits with OpenRouter, Hugging Face, or SGLang and save each result."""

import json
import os
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from http.client import IncompleteRead
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
    try:
        result = json.loads(content, object_pairs_hook=_unique_object)
    except json.JSONDecodeError:
        # HF reasoning may precede the final JSON without an opening <think> tag.
        if "</think>" not in content:
            raise
        result = json.loads(content.rsplit("</think>", 1)[1], object_pairs_hook=_unique_object)
    if not isinstance(result, dict) or set(result) != {"category", "explanation"}:
        raise ValueError("Return exactly the keys 'category' and 'explanation'.")
    if result["category"] not in CATEGORIES:
        raise ValueError("Category must be preferential, factual, or uncertain.")
    if not isinstance(result["explanation"], str) or not result["explanation"].strip():
        raise ValueError("Explanation must be a nonempty string of 3-5 sentences.")
    return result


def _request(messages, *, endpoint, api_key, model, temperature, max_tokens, timeout):
    payload = {
        "model": model, "messages": messages, "temperature": temperature,
        "max_tokens": max_tokens, "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(endpoint, data=json.dumps(payload).encode(), headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as error:
        if error.code in (400, 401, 402, 403, 404, 422):
            raise RuntimeError(f"LLM HTTP {error.code}; check endpoint, key, and model settings.") from error
        raise
    if not isinstance(result, dict):
        raise ValueError("LLM returned an invalid response envelope.")
    if result.get("error"):
        error = result["error"]
        if str(error.get("code")) in ("400", "401", "402", "403", "404", "422"):
            raise RuntimeError(f"LLM error: {error}")
        raise URLError(str(error))
    return result


def _messages(software, physician, prompt):
    reports = {"software_report": software, "physician_report": physician}
    content = re.sub(r"\{(software_report|physician_report)\}",
                     lambda match: json.dumps(reports[match[1]], ensure_ascii=False), prompt)
    return [{"role": "user", "content": content}]


def _load_hf(model, device_map="auto"):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model, padding_side="left")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(model, device_map=device_map, dtype="auto")
    model.eval()

    def request(messages):
        inputs = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, padding=True,
            return_tensors="pt", return_dict=True,
        ).to(model.device)
        with torch.inference_mode():
            outputs = model.generate(**inputs, pad_token_id=tokenizer.pad_token_id, max_new_tokens=512)
        if hasattr(outputs, "sequences"):
            outputs = outputs.sequences
        contents = tokenizer.batch_decode(outputs[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        if len(contents) != len(messages):
            raise RuntimeError("The HF model must return one sequence per report pair.")
        return [{"choices": [{"message": {"role": "assistant", "content": content}}]} for content in contents]

    return request


def _classify_batch(reports, *, prompt, request, max_attempts):
    messages = [_messages(software, physician, prompt) for software, physician in reports]
    results = [(None, []) for _ in reports]
    pending = list(range(len(reports)))
    for number in range(1, max_attempts + 1):
        if not pending:
            break
        responses = request([messages[index] for index in pending])
        retry = []
        wait = False
        for index, response in zip(pending, responses, strict=True):
            output = None
            attempts = results[index][1]
            attempt = {"number": number, "response": None, "error": None}
            attempts.append(attempt)
            try:
                if isinstance(response, Exception):
                    raise response
                attempt["response"] = response
                try:
                    output = response["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as error:
                    raise ValueError("Response has no assistant content.") from error
                results[index] = _parse_output(output), attempts
                continue
            except (URLError, TimeoutError, IncompleteRead) as error:
                attempt["error"] = str(error)
                wait = True
            except ValueError as error:
                attempt["error"] = str(error)
                if isinstance(output, str):
                    messages[index].append({"role": "assistant", "content": output})
                messages[index].append({"role": "user", "content": (
                    f"Your previous output was incorrect: {error} "
                    "Return only the required JSON object, with no extra keys or Markdown."
                )})
            retry.append(index)
        pending = retry
        if wait and number < max_attempts:
            time.sleep(2 ** (number - 1))
    return results


def _classify(software, physician, *, prompt, request, max_attempts):
    def request_batch(messages):
        try:
            return [request(messages[0])]
        except (URLError, TimeoutError, IncompleteRead, ValueError) as error:
            return [error]

    return _classify_batch([(software, physician)], prompt=prompt,
                           request=request_batch, max_attempts=max_attempts)[0]


def _pairs(paths, data_name):
    for path in paths:
        for index, (source, software, physician) in enumerate(read_reports([path], data_name)):
            yield {"source": source, "file": str(path.resolve()), "pair_index": index}, software, physician


def _analyze_pair(item, *, empty_reports, classify=None, truncate=(), remove=()):
    identity, software, physician = item
    comparison = edits.compare_reports(software, physician, empty_reports=empty_reports,
                                       truncate=truncate, remove=remove)
    record = {
        **identity, **comparison, "software_report": None, "physician_report": None,
        "status": "excluded", "category": None, "explanation": None, "attempts": [],
    }
    if comparison["change"] is None:
        return record
    record["software_report"] = list(normalize_report(software, **INPUT_NORMALIZATION, truncate=truncate, remove=remove))
    record["physician_report"] = list(normalize_report(physician, **INPUT_NORMALIZATION, truncate=truncate, remove=remove))
    if comparison["change"] == "unchanged":
        record["status"] = "unchanged"
        return record
    record["status"] = "skipped"
    if classify is None:
        return record
    result, attempts = classify(record["software_report"], record["physician_report"])
    record.update(status="classified" if result else "skipped", attempts=attempts)
    if result:
        record.update(result)
    return record


def _analyze_batch(items, *, empty_reports, classify, truncate=(), remove=()):
    records = [_analyze_pair(item, empty_reports=empty_reports, truncate=truncate, remove=remove) for item in items]
    changed = [record for record in records if record["status"] == "skipped"]
    if changed:
        results = classify([(record["software_report"], record["physician_report"]) for record in changed])
        for record, (result, attempts) in zip(changed, results, strict=True):
            record.update(status="classified" if result else "skipped", attempts=attempts)
            if result:
                record.update(result)
    return records


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


def summarize(counts, *, empty_reports, undefined_ratio, truncate=(), remove=()):
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
            "truncate": list(truncate),
            "remove": list(remove),
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


def _pair_id(record):
    return record["source"], record["file"], record["pair_index"]


def _load_saved(path, counts, retry_skipped=True):
    saved = set()
    good_lines = []
    with path.open("r+b") as file:
        while line := file.readline():
            if not line.endswith(b"\n"):
                # A write interrupted before its newline is not a saved record.
                file.truncate(file.tell() - len(line))
                break
            record = json.loads(line)
            identity = _pair_id(record)
            if identity in saved:
                raise ValueError(f"Duplicate saved pair: {identity}")
            if retry_skipped and record.get("status") == "skipped":
                continue  # drop it so it will be reprocessed
            saved.add(identity)
            good_lines.append(line)
            _count(counts, record)
    if retry_skipped:
        path.write_bytes(b"".join(good_lines))  # rewrite without skipped records
    return saved


def run_analysis(cfg):
    options = cfg.get("study_options", {})
    empty_reports = options.get("empty_reports", "exclude")
    truncate = options.get("truncate", [])
    remove = options.get("remove", [])
    edits.compare_reports([], [], empty_reports=empty_reports, truncate=truncate, remove=remove)
    settings = cfg.get("llm", {})
    backend = settings.get("backend", "openrouter")
    if backend not in ("openrouter", "huggingface", "sglang"):
        raise ValueError("llm.backend must be 'openrouter', 'huggingface', or 'sglang'.")
    defaults = ({"temperature": 0, "max_tokens": 1024, "timeout": 120} if backend != "huggingface"
                else {"device_map": "auto"})
    settings = {**defaults, "backend": backend, "max_attempts": 3, **settings}
    if backend == "huggingface":
        for key in ("temperature", "max_tokens", "timeout"):
            settings.pop(key, None)
    model = settings.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Set llm.model to a model ID or local HF model directory.")
    for key in (("max_attempts", "max_tokens") if backend != "huggingface" else ("max_attempts",)):
        if type(settings[key]) is not int or settings[key] < 1:
            raise ValueError(f"llm.{key} must be a positive integer.")
    if backend != "huggingface" and settings["timeout"] <= 0:
        raise ValueError("llm.timeout must be positive.")
    endpoint = ENDPOINT
    if backend == "sglang":
        endpoint = settings.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint.startswith(("http://", "https://")):
            raise ValueError("Set llm.endpoint to the SGLang HTTP chat completions URL.")
    api_key = os.environ.get("SGLANG_API_KEY" if backend == "sglang" else "OPENROUTER_API_KEY")
    if backend == "openrouter" and not api_key:
        raise ValueError("Set OPENROUTER_API_KEY in your environment.")
    batch_size = 1 if cfg["development"] else cfg.get("reports_per_batch", 8)
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("reports_per_batch must be a positive integer.")
    prompt = PROMPT_PATH.read_text()
    pairs = _pairs(report_files(cfg["data_path"], cfg["data_name"]), cfg["data_name"])

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    resume_from = cfg.get("resume_from")
    output = (Path(resume_from) if resume_from else
              Path(cfg["save_path"]) / "llm_edits" / cfg["data_name"] / run_id)
    metadata = {
        "run_id": run_id, "completed": False,
        "endpoint": endpoint if backend != "huggingface" else None, "llm": settings,
        "data_name": cfg["data_name"], "data_path": str(Path(cfg["data_path"]).resolve()),
        "development": cfg["development"], "reports_per_batch": batch_size,
        "normalization": edits.NORMALIZATION, "empty_reports": empty_reports,
        "truncate": truncate, "remove": remove,
        "llm_input_normalization": INPUT_NORMALIZATION,
        "undefined_ratio": cfg["undefined_ratio"], "prompt": prompt,
    }
    counts = {}
    saved = set()
    if resume_from:
        previous = json.loads((output / "run.json").read_text())
        previous["llm"].setdefault("backend", "openrouter")
        for key in ("truncate", "remove"):
            if previous.get(key, []) != metadata[key]:
                raise ValueError(f"Cannot resume: {key} differs from the saved run.")
        for key in ("endpoint", "llm", "data_name", "data_path", "normalization",
                    "empty_reports", "llm_input_normalization", "prompt"):
            if previous[key] != metadata[key]:
                raise ValueError(f"Cannot resume: {key} differs from the saved run.")
        metadata["run_id"] = previous["run_id"]
        saved = _load_saved(output / "pairs.jsonl", counts)
        pairs = (item for item in pairs if _pair_id(item[0]) not in saved)
        print(f"Resuming {output}: {len(saved)} saved pairs")
    batch = tuple(islice(pairs, batch_size))
    if not batch and not saved:
        raise ValueError(f"No {cfg['data_name']} report pairs in {cfg['data_path']}")
    output.mkdir(parents=True, exist_ok=bool(resume_from))
    _save(output / "run.json", metadata)
    results = summarize(counts, empty_reports=empty_reports, undefined_ratio=cfg["undefined_ratio"],
                        truncate=truncate, remove=remove)
    _save(output / "summary.json", results)
    print(f"Saving {output}")
    if backend == "huggingface":
        request = _load_hf(model, device_map=settings["device_map"])
        classify = partial(_classify_batch, prompt=prompt, request=request, max_attempts=settings["max_attempts"])
        worker = partial(_analyze_batch, empty_reports=empty_reports, classify=classify, truncate=truncate, remove=remove)
    else:
        request = partial(_request, endpoint=endpoint, api_key=api_key, **{key: settings[key] for key in (
            "model", "temperature", "max_tokens", "timeout",
        )})
        classify = partial(_classify, prompt=prompt, request=request, max_attempts=settings["max_attempts"])
        worker = partial(_analyze_pair, empty_reports=empty_reports, classify=classify, truncate=truncate, remove=remove)
    with (output / "pairs.jsonl").open("a") as file, ThreadPoolExecutor(max_workers=batch_size) as pool:
        with tqdm(desc="llm_edits", unit="pair", initial=len(saved)) as progress:
            while batch:
                records = worker(batch) if backend == "huggingface" else pool.map(worker, batch)
                for record in records:
                    file.write(json.dumps(record, allow_nan=False) + "\n")
                    file.flush()
                    _count(counts, record)
                    progress.update()
                    if cfg["development"]:
                        print(json.dumps(record, indent=2, allow_nan=False))
                results = summarize(counts, empty_reports=empty_reports, undefined_ratio=cfg["undefined_ratio"],
                                    truncate=truncate, remove=remove)
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
