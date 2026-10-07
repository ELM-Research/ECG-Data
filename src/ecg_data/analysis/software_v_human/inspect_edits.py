import argparse
import json
from functools import partial
from multiprocessing import Pool

from ecg_data.analysis.software_v_human.edits import NORMALIZATION, STATEMENTS, compare_reports
from ecg_data.analysis.software_v_human.reports import normalize_report, read_reports, report_files


def _collect_file(path, *, data_name, terms, limit, empty_reports):
    groups = (*STATEMENTS, "absent_from_both")
    results = {}
    for index, (source, software, physician) in enumerate(read_reports([path], data_name)):
        if source not in results:
            results[source] = {term: {group: [] for group in groups} for term in terms}
        pair = compare_reports(software, physician, empty_reports=empty_reports)
        if pair["change"] is None:
            continue

        statements = {name: set(pair[name]) for name in STATEMENTS}
        for term in terms:
            group = next((name for name in STATEMENTS if term in statements[name]), "absent_from_both")
            examples = results[source][term][group]
            if len(examples) < limit:
                examples.append({
                    "file": str(path.resolve()), "pair_index": index,
                    "software": software, "physician": physician,
                })
    return results


def _collect(data_path, data_name, terms, *, limit, empty_reports, workers=None):
    terms = normalize_report(terms, **NORMALIZATION)
    if not terms or limit < 1:
        raise ValueError("Provide nonblank terms and a positive example limit.")

    paths = report_files(data_path, data_name)
    worker = partial(_collect_file, data_name=data_name, terms=terms,
                     limit=limit, empty_reports=empty_reports)
    results = {}
    with Pool(processes=workers) as pool:
        # Batch tasks to reduce communication; imap preserves file order.
        for incoming in pool.imap(worker, paths, chunksize=64):
            for source, source_terms in incoming.items():
                target = results.setdefault(source, {})
                for term, groups in source_terms.items():
                    target_groups = target.setdefault(term, {})
                    for group, examples in groups.items():
                        collected = target_groups.setdefault(group, [])
                        collected.extend(examples[:limit - len(collected)])

            # Finish both HEEDB sources before checking whether every group is full.
            if results and all(len(examples) == limit for source in results.values()
                               for term in source.values() for examples in term.values()):
                break

    if not results:
        raise ValueError(f"No {data_name} report pairs found in {data_path}.")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", required=True)
    parser.add_argument("--data-name", choices=("agh", "heedb"), required=True)
    parser.add_argument("--terms", nargs="+", required=True)
    parser.add_argument("--examples", type=int, default=2, help="Examples per source, term, and group.")
    parser.add_argument("--workers", type=int, default=None, help="Worker processes; defaults to CPU count.")
    parser.add_argument("--empty-reports", choices=("exclude", "compare"), default="exclude")
    args = parser.parse_args()
    results = _collect(args.data_path, args.data_name, args.terms,
                       limit=args.examples, empty_reports=args.empty_reports, workers=args.workers)
    print(json.dumps({"empty_reports": args.empty_reports, "examples": results}, indent=2))
