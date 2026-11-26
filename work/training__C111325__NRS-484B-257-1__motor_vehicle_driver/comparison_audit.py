"""Independent original-source comparison audit for one exact statutory group."""

import argparse
import json
from pathlib import Path

from audit_diagnostic_comparisons import audit as audit_group, record
from delivery_audit import audit as audit_delivery
from measure_saved_packet import inspect


def pairs(values):
    parsed = {}
    for value in values:
        case, separator, path = value.partition("=")
        if not separator or not case or not path or case in parsed:
            raise ValueError("Each case path needs unique CASE=PATH form")
        parsed[case] = Path(path).resolve()
    return parsed


def compare(comparison_id, attempts, processing):
    folder = Path(__file__).resolve().parent
    plan = json.loads((folder / "case-plan.json").read_text())
    selected = [entry for entry in plan["comparisons"] if entry["comparison_id"] == comparison_id]
    if len(selected) != 1:
        raise ValueError("Unknown exact statutory comparison")
    comparison = selected[0]
    case_ids = set(comparison["case_ids"])
    if set(attempts) != case_ids or set(processing) != case_ids:
        raise ValueError("Comparison lacks exact member attempts or processing receipts")
    records = {}
    for case_id in comparison["case_ids"]:
        attempt = attempts[case_id]
        audit_delivery(case_id, attempt, processing[case_id], diagnostic=False)
        measured = inspect(attempt, case_id)
        if measured["source_kind"] != "original_native_readback":
            raise ValueError("Original Native source required for delivery comparison")
        context = json.loads((attempt / "stop_yield_context.json").read_text())
        rows = [json.loads(line) for line in (attempt / "stop_yield_motion.jsonl").read_text().splitlines()]
        records[case_id] = record(context, rows, case_id, source_root=attempt)
        if records[case_id]["observation"] != {k: v for k, v in measured.items() if k != "packet_sources"}:
            raise ValueError("Independent comparison differs from saved measurement")
    return audit_group(comparison, records, require_original=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", action="append", default=[], metavar="CASE=PATH")
    parser.add_argument("--processing", action="append", default=[], metavar="CASE=PATH")
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison, pairs(args.attempt), pairs(args.processing)), sort_keys=True))
