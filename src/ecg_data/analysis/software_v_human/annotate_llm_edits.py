"""Export a random sample of saved LLM classifications for offline annotation."""

import base64
import hashlib
import json
import random
from pathlib import Path
from tempfile import TemporaryDirectory

from ecg_data.analysis.software_v_human.llm_edits import CATEGORIES, _count, _pair_id, summarize
from ecg_data.analysis.software_v_human.plot_llm_edits import _plot_llm, _snapshot, _write_page
from ecg_data.preprocess.config.load import get_config


def export_annotations(root, *, sample_size=200, seed=0):
    if type(sample_size) is not int or sample_size < 1:
        raise ValueError("annotations.sample_size must be a positive integer.")
    if type(seed) is not int:
        raise ValueError("annotations.seed must be an integer.")

    root = Path(root)
    snapshot = _snapshot(root)
    eligible = [record for record in snapshot["pairs"]
                if record["status"] == "classified" and record["category"] in CATEGORIES]
    if not eligible:
        raise ValueError("No successfully classified pairs to annotate.")
    if len({_pair_id(record) for record in eligible}) != len(eligible):
        raise ValueError("Duplicate classified pair identities in pairs.jsonl.")

    # Sample without replacement, preserving the saved report order.
    indices = set(random.Random(seed).sample(range(len(eligible)), min(sample_size, len(eligible))))
    snapshot["pairs"] = [record for index, record in enumerate(eligible) if index in indices]
    identity = json.dumps({"run": snapshot["run"], "pairs": snapshot["pairs"]},
                          sort_keys=True, allow_nan=False).encode()
    snapshot["annotation"] = {
        "sample_id": hashlib.sha256(identity).hexdigest(),
        "source_jsonl": str((root / "pairs.jsonl").resolve()),
        "cohort": "Successfully classified changed pairs",
        "method": "Simple random sample without replacement",
        "requested_size": sample_size, "sample_size": len(snapshot["pairs"]),
        "eligible_pairs": len(eligible), "seed": seed,
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
    root = Path(cfg["save_path"]) / "llm_edits" / cfg["data_name"] / cfg["plots"]["run_id"]
    export_annotations(root, **cfg.get("annotations", {}))
