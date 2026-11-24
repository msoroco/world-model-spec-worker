"""Exact-case saved alley finalizer over audited original sources.

Exterior operation measurements remain observations. They do not establish a
person's interior attention or a legal conclusion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from attention_measurement import measure
from native_operation import CASE_PROFILES
from saved_delivery import audit
from measurement_contract import check as check_measurement_contract


def finalize(attempt: Path, case_id: str, allow_diagnostic: bool = False) -> dict:
    if case_id not in CASE_PROFILES:
        raise ValueError("unknown exact case")
    original = audit(attempt, case_id, require_delivery=not allow_diagnostic)
    operation = attempt / "operation.jsonl"
    measured = measure(operation, case_id)
    operation_hash = hashlib.sha256(operation.read_bytes()).hexdigest()
    if measured["source"]["sha256"] != operation_hash or original["source_sha256"]["operation"] != operation_hash:
        raise ValueError("measured operation is not the audited original source")
    if measured["frame_count"] != original["original_frames"]:
        raise ValueError("measured and audited original frame counts differ")
    result = {
        "format": "worker-alley-exact-saved-measurement-v1",
        "case_id": case_id,
        "selected_requirement": "LVMC-11-22-010",
        "source_kind": "audited_original_native_capture",
        "source_sha256": original["source_sha256"],
        "original_frames": original["original_frames"],
        "decoded_original_pngs": original["decoded_original_pngs"],
        "diagnostic_fixture": original["diagnostic_fixture"],
        "operation_measurement": measured,
        "attention_state": "unobserved",
        "legal_judgment": "unresolved",
    }
    contract = Path(__file__).resolve().parent / ("measurement-contract-" + case_id.rsplit("__", 1)[1] + ".json")
    check_measurement_contract(contract, attempt, result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args(argv)
    if args.output.exists():
        raise ValueError("saved finalizer output already exists")
    result = finalize(args.attempt, args.case, args.allow_diagnostic)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
