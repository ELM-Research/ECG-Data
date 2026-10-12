"""Export a saved LLM run as report-level PNGs and an offline HTML browser."""

import json
from datetime import datetime, timezone
from pathlib import Path

from ecg_data.analysis.software_v_human.llm_edits import CATEGORIES, STATUSES, _count, summarize
from ecg_data.analysis.software_v_human.plot_edits import (
    CHANGE_NAMES, INPUT_NAMES, SOURCE_NAMES, _plot_rates, _plot_reports,
)
from ecg_data.preprocess.config.load import get_config


def _snapshot(root):
    run = json.loads((root / "run.json").read_text())
    data = (root / "pairs.jsonl").read_bytes()
    pairs, counts = [], {}
    # The writer flushes newline-terminated records; ignore only an unfinished tail.
    lines = data.splitlines(keepends=True)
    incomplete = bool(lines and not lines[-1].endswith(b"\n"))
    for number, line in enumerate(lines[:-1] if incomplete else lines, 1):
        try:
            record = json.loads(line)
        except ValueError as error:
            raise ValueError(f"Invalid JSON in {root / 'pairs.jsonl'}:{number}") from error
        pairs.append(record)
        _count(counts, record)
    return {
        "run": run, "pairs": pairs, "incomplete_tail": incomplete,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "summary": summarize(counts, empty_reports=run["empty_reports"],
                             undefined_ratio=run["undefined_ratio"]),
        "names": {"source": SOURCE_NAMES, "change": CHANGE_NAMES, "input": INPUT_NAMES},
    }


def _plot_llm(results, output):
    _plot_reports(results, output)
    _plot_rates(
        results, [(key, key.title()) for key in CATEGORIES],
        lambda metrics, key: (metrics["category_counts"][key], metrics["classified_reports"]),
        title="LLM edit categories", numerator="Successfully classified pairs in the stated category.",
        denominator="All successfully classified changed pairs; skipped pairs are excluded.",
        interpretation="Factual means clinical meaning changed, not verified correction.",
        output=output / "04_category_rates.png",
    )
    _plot_rates(
        results, [(key, key.title()) for key in STATUSES],
        lambda metrics, key: (metrics["status_counts"][key], metrics["input_reports"]),
        title="Processing outcomes", numerator="Input pairs with the stated final status.",
        denominator="All saved input pairs, before exclusions. Unchanged pairs need no LLM call.",
        output=output / "05_processing_status.png",
    )
    _plot_rates(
        results, [("classified_reports", "Successfully classified"), ("skipped_reports", "Skipped after failed attempts")],
        lambda metrics, key: (metrics[key], metrics["edited_reports"]),
        title="Classification coverage", numerator="Changed pairs with the stated outcome.",
        denominator="All included changed pairs, including skipped pairs.",
        output=output / "06_classification_coverage.png",
    )
    attempts = sorted({number for metrics in results.values() for number in metrics["attempt_counts"]})
    if attempts:
        _plot_rates(
            results, [(number, f"{number} attempt{'s' if number != 1 else ''}") for number in attempts],
            lambda metrics, key: (metrics["attempt_counts"].get(key, 0), metrics["edited_reports"]),
            title="LLM attempts per changed pair", numerator="Changed pairs using the stated number of API attempts.",
            denominator="All included changed pairs, including skipped pairs.",
            output=output / "07_attempts.png",
        )


def export_run(root):
    root = Path(root)
    snapshot = _snapshot(root)
    snapshot["figures"] = {}
    for source, metrics in snapshot["summary"].items():
        output = root / "figures" / source
        _plot_llm({source: metrics}, output)
        snapshot["figures"][source] = [str(path.relative_to(root)) for path in sorted(output.glob("*.png"))]
    template = Path(__file__).with_name("llm_edits.html").read_text()
    # Escape '<' so report text cannot close the embedded JSON script element.
    payload = json.dumps(snapshot, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")
    page = root / "index.html"
    page.write_text(template.replace("<!-- SNAPSHOT -->", payload))
    print(f"Saved {len(snapshot['pairs']):,} pairs to {page}")
    return page


if __name__ == "__main__":
    cfg = get_config()
    if cfg["experiment"] != "llm_edits":
        raise ValueError("These plots require experiment: llm_edits.")
    root = Path(cfg["save_path"]) / "llm_edits" / cfg["data_name"] / cfg["plots"]["run_id"]
    export_run(root)
