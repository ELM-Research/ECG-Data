import json
from functools import partial
from itertools import chain, islice
from multiprocessing import Pool
from pathlib import Path

from tqdm import tqdm

from ecg_data.analysis.software_v_human import edits, ouyang
from ecg_data.analysis.software_v_human.reports import read_reports, report_files
from ecg_data.preprocess.config.load import get_config

EXPERIMENTS = {"ouyang": ouyang, "edits": edits}


def _batches(paths, size):
    while batch := tuple(islice(paths, size)):
        yield batch


def _count_batch(paths, *, data_name, experiment, options):
    study = EXPERIMENTS[experiment]
    return study.count_reports(read_reports(paths, data_name), **options)


def run_analysis(cfg):
    experiment = cfg["experiment"]
    batch_size = cfg["files_per_batch"]
    cores = cfg["num_cores"]
    options = cfg.get("study_options", {})

    paths = iter(report_files(cfg["data_path"], cfg["data_name"]))
    first = next(paths, None)
    if first is None:
        raise FileNotFoundError(f"No {cfg['data_name']} report files in {cfg['data_path']}")
    batches = _batches(chain((first,), paths), batch_size)
    worker = partial(_count_batch, data_name=cfg["data_name"], experiment=experiment, options=options)
    study = EXPERIMENTS[experiment]
    counts = {}

    if cfg["development"]:
        for batch in tqdm(batches, desc=experiment, unit="batch"):
            study.merge_counts(counts, worker(batch))
    else:
        with Pool(processes=cores) as pool:
            results = pool.imap_unordered(worker, batches, chunksize=1)
            for result in tqdm(results, desc=experiment, unit="batch"):
                study.merge_counts(counts, result)

    results = study.summarize(counts, undefined_ratio=cfg["undefined_ratio"], **options)
    for source, metrics in results.items():
        if "input_status_counts" in metrics:
            print(f"{source}: {metrics['input_status_counts']}; excluded={metrics['excluded_reports']}")
    output = Path(cfg["save_path"]) / experiment / f"{cfg['data_name']}.json"
    contents = json.dumps(results, indent=2, sort_keys=True, allow_nan=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(contents + "\n")
    print(f"Saved {output}")
    return results


if __name__ == "__main__":
    cfg = get_config()
    print(cfg)
    run_analysis(cfg)
