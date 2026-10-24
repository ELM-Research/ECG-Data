"""Export a random sample of saved LLM classifications for offline annotation."""

import base64
import hashlib
import json
import random
from pathlib import Path
from tempfile import TemporaryDirectory

from ecg_data.analysis.software_v_human.llm_edits import _count, _pair_id, summarize
from ecg_data.analysis.software_v_human.plot_llm_edits import _plot_llm, _snapshot, _write_page
from ecg_data.preprocess.config.load import get_config


def _balanced_sizes(counts, sample_size, rng):
    size = min(sample_size // len(counts), *counts)
    sizes = [size] * len(counts)
    if sum(sizes) < min(sample_size, sum(counts)):
        remaining = [count - size for count in counts]
        index = rng.choices(range(len(counts)), weights=remaining)[0]
        sizes[index] += 1
    return sizes


def export_annotations(root, *, sample_size=200, seed=0, extra_roots=()):
    if type(sample_size) is not int or sample_size < 1:
        raise ValueError("annotations.sample_size must be a positive integer.")
    if type(seed) is not int:
        raise ValueError("annotations.seed must be an integer.")

    root = Path(root)
    roots = [root, *(Path(path) for path in extra_roots)]
    snapshots = [_snapshot(path) for path in roots]
    snapshot = snapshots[0]
    if len(snapshots) > 1:
        runs = [item["run"] for item in snapshots]
        for key in ("empty_reports", "undefined_ratio"):
            if any(run[key] != runs[0][key] for run in runs[1:]):
                raise ValueError(f"Annotation runs must use the same {key}.")
        snapshot["pairs"] = [record for item in snapshots for record in item["pairs"]]
        snapshot["incomplete_tail"] = any(item["incomplete_tail"] for item in snapshots)
        snapshot["run"] = {**runs[0], "runs": runs,
                           "completed": all(run["completed"] for run in runs)}

    datasets = tuple(dict.fromkeys(item["run"]["data_name"] for item in snapshots))
    categories = ("preferential", "factual")
    eligible = [record for record in snapshot["pairs"]
                if record["status"] == "classified" and record["category"] in categories]
    if not eligible:
        raise ValueError("No successfully classified preferential or factual pairs to annotate.")
    if len({_pair_id(record) for record in eligible}) != len(eligible):
        raise ValueError("Duplicate classified pair identities in pairs.jsonl.")

    # Balance datasets, pooling HEEDB software versions, then balance categories.
    groups = [[[index for index, record in enumerate(eligible)
                if record["source"].split("_", 1)[0] == dataset and record["category"] == category]
               for category in categories] for dataset in datasets]
    # Keep the existing limit of one extra pair when a category runs short.
    capacities = [min(sum(map(len, group)), 2 * min(map(len, group)) + 1) for group in groups]
    rng = random.Random(seed)
    sizes = _balanced_sizes(capacities, sample_size, rng)
    indices = set()
    for group, size in zip(groups, sizes):
        category_sizes = _balanced_sizes([len(category) for category in group], size, rng)
        for category, count in zip(group, category_sizes):
            indices.update(rng.sample(category, count))
    snapshot["pairs"] = [record for index, record in enumerate(eligible) if index in indices]
    identity = json.dumps({"run": snapshot["run"], "pairs": snapshot["pairs"]},
                          sort_keys=True, allow_nan=False).encode()
    display_order = list(range(len(snapshot["pairs"])))
    rng.shuffle(display_order)
    snapshot["annotation"] = {
        "sample_id": hashlib.sha256(identity).hexdigest(),
        "source_jsonl": str((root / "pairs.jsonl").resolve()),
        "source_jsonls": [str((path / "pairs.jsonl").resolve()) for path in roots],
        "cohort": "Successfully classified preferential or factual changed pairs",
        "method": "Random sample without replacement, balanced by dataset and by preferential/factual within each dataset",
        "requested_size": sample_size, "sample_size": len(snapshot["pairs"]),
        "eligible_pairs": len(eligible), "seed": seed,
        "display_order": display_order,
    }
    counts = {}
    for record in snapshot["pairs"]:
        _count(counts, record)
    run = snapshot["run"]
    snapshot["summary"] = summarize(counts, empty_reports=run["empty_reports"],
                                    undefined_ratio=run["undefined_ratio"])

    # Embed plots so the annotation HTML can be sent as one file.
    snapshot["figures"] = {}
    with TemporaryDirectory() as directory:
        for source, metrics in snapshot["summary"].items():
            output = Path(directory) / source
            _plot_llm({source: metrics}, output)
            snapshot["figures"][source] = [
                {"path": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode(),
                 "label": path.name.replace("_", " ")}
                for path in sorted(output.glob("*.png"))
            ]

    script = Path(__file__).with_name("llm_edits_annotation.js").read_text()
    print(f"Sampled {len(snapshot['pairs']):,} / {len(eligible):,} classified pairs (seed {seed}).")
    return _write_page(snapshot, root / "annotations.html", script)


if __name__ == "__main__":
    cfg = get_config()
    if cfg["experiment"] != "llm_edits":
        raise ValueError("Annotation requires experiment: llm_edits.")
    options = cfg.get("annotations", {}).copy()
    runs = options.pop("runs", None)
    if runs is None:
        runs = {cfg["data_name"]: cfg["plots"]["run_id"]}
    roots = [Path(cfg["save_path"]) / "llm_edits" / dataset / run_id
             for dataset, run_id in runs.items()]
    export_annotations(roots[0], extra_roots=roots[1:], **options)
