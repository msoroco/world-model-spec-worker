"""Independent source-value guard before the saved bicycle comparison audit."""
from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path

from comparison_audit import audit, audit_saved_pair
from speed_measurement import measure


def check_record(record: dict) -> None:
    samples = record.get("samples")
    conditions = record.get("condition_samples")
    if not isinstance(samples, list) or not samples or not isinstance(conditions, list):
        raise ValueError("original speed and condition samples required")
    speeds = [row.get("speed_mps") for row in samples]
    times = [row.get("time_s") for row in samples]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) or value < 0 for value in speeds):
        raise ValueError("invalid original speed history")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) for value in times) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("original speed time axis invalid")
    mean = record.get("summary", {}).get("mean_speed_mps")
    if isinstance(mean, bool) or not isinstance(mean, (int, float)) or not math.isfinite(mean) or abs(mean - sum(speeds) / len(speeds)) > 1e-8:
        raise ValueError("reported mean differs from original speed history")
    if [row.get("time_s") for row in conditions] != times:
        raise ValueError("condition source time axis differs")


def audit_guarded_pair(plan: dict, comparison_id: str, left: Path,
                       right: Path, left_audit: Path, right_audit: Path) -> dict:
    for path in (left, right):
        check_record(json.loads(Path(path).read_text(encoding="utf-8")))
    return audit_saved_pair(plan, comparison_id, left, right, left_audit, right_audit)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_saved_attempts(plan: dict, comparison_id: str, left_attempt: Path,
                         right_attempt: Path, left_audit: Path, right_audit: Path) -> dict:
    """Compare measured original packets and bind each to its Native delivery audit."""
    records = []
    native_hashes = []
    audit_hashes = []
    for attempt, audit_path in ((Path(left_attempt), Path(left_audit)),
                                (Path(right_attempt), Path(right_audit))):
        native_path = attempt / "result.json"
        inventory_path = attempt / "inventory.json"
        if not native_path.is_file() or not inventory_path.is_file():
            raise ValueError("saved Native result or original inventory missing")
        native = json.loads(native_path.read_text(encoding="utf-8"))
        receipt = json.loads(audit_path.read_text(encoding="utf-8"))
        case_id = native.get("case_id")
        if native.get("diagnostic_fixture") is not False:
            raise ValueError("comparison requires non-diagnostic Native result")
        if (receipt.get("format") != "worker-delivery-audit" or
                receipt.get("passed") is not True or
                receipt.get("case_id") != case_id or
                receipt.get("native_result_sha256") != _sha(native_path) or
                not {"native_source", "all_participants", "time_join", "full_video_decode",
                     "actual_pixels", "physical_completion"} <= set(receipt.get("checks", []))):
            raise ValueError("comparison lacks source-bound independent delivery audit")
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        if inventory.get("diagnostic_fixture") is True:
            raise ValueError("comparison requires non-diagnostic original inventory")
        record = measure(attempt, inventory, case_id)
        if len(record["samples"]) < 900:
            raise ValueError("comparison requires full original bicycle window")
        check_record(record)
        records.append(record)
        native_hashes.append(_sha(native_path))
        audit_hashes.append(_sha(audit_path))
    result = audit(plan, comparison_id, *records)
    result["native_result_sha256"] = native_hashes
    result["delivery_audit_sha256"] = audit_hashes
    result["original_inventory_sha256"] = [_sha(Path(p) / "inventory.json")
                                            for p in (left_attempt, right_attempt)]
    result["independent_delivery_audits"] = True
    return result


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", type=Path)
    parser.add_argument("--right", type=Path)
    parser.add_argument("--left-delivery-audit", type=Path, required=True)
    parser.add_argument("--right-delivery-audit", type=Path, required=True)
    parser.add_argument("--left-attempt", type=Path)
    parser.add_argument("--right-attempt", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if bool(args.left_attempt) != bool(args.right_attempt) or bool(args.left) != bool(args.right):
        raise ValueError("both comparison sides are required")
    if bool(args.left_attempt) == bool(args.left):
        raise ValueError("select either saved attempts or measurement files")
    if args.left_attempt:
        result = audit_saved_attempts(plan, args.comparison, args.left_attempt,
                                      args.right_attempt, args.left_delivery_audit,
                                      args.right_delivery_audit)
    else:
        result = audit_guarded_pair(plan, args.comparison, args.left,
                                    args.right, args.left_delivery_audit,
                                    args.right_delivery_audit)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
