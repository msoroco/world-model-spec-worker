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
    summary = record.get("summary", {})
    window = summary.get("approach_window", {})
    selected = speeds
    if window.get("source_verified") is True:
        start, end = window.get("start_x_m"), window.get("end_x_m")
        if (not all(isinstance(value, (int, float)) and math.isfinite(value)
                    for value in (start, end)) or start >= end):
            raise ValueError("reported original approach window invalid")
        selected = [row["speed_mps"] for row in samples
                    if isinstance(row.get("x_m"), (int, float)) and
                    start <= row["x_m"] <= end]
        if len(selected) < 20 or len(selected) != window.get("sample_count"):
            raise ValueError("reported original approach window differs from source")
    mean = summary.get("mean_speed_mps")
    if isinstance(mean, bool) or not isinstance(mean, (int, float)) or not math.isfinite(mean) or abs(mean - sum(selected) / len(selected)) > 1e-8:
        raise ValueError("reported mean differs from original speed history")
    episode = summary.get("episode_mean_speed_mps")
    if episode is not None and (not isinstance(episode, (int, float)) or
            not math.isfinite(episode) or abs(episode - sum(speeds) / len(speeds)) > 1e-8):
        raise ValueError("reported episode mean differs from original speed history")
    if [row.get("time_s") for row in conditions] != times:
        raise ValueError("condition source time axis differs")


def audit_guarded_pair(plan: dict, comparison_id: str, left: Path,
                       right: Path, left_audit: Path, right_audit: Path) -> dict:
    for path in (left, right):
        check_record(json.loads(Path(path).read_text(encoding="utf-8")))
    return audit_saved_pair(plan, comparison_id, left, right, left_audit, right_audit)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selected_camera_contract(attempt: Path, case_id: str) -> dict:
    """Read the exact selected Native camera source, never a claimed camera label."""
    manifest_path = Path(__file__).resolve().with_name("execution-manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = [item for item in manifest["cases"] if item["case_id"] == case_id]
    if len(entries) != 1:
        raise ValueError("comparison case absent from frozen manifest")
    selection_path = attempt / "candidate-selection.json"
    if selection_path.is_file():
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        candidate_id = selection.get("candidate_id")
    else:
        selection = None
        candidate_id = "primary"
    entry = entries[0]
    if candidate_id == "primary":
        selected = entry
    else:
        matches = [item for item in entry.get("candidates", [])
                   if item.get("id") == candidate_id]
        if len(matches) != 1:
            raise ValueError("comparison candidate selection invalid")
        selected = matches[0]
    construction_path = manifest_path.parent / selected["construction"]
    expected_hash = selected["construction_sha256"]
    if _sha(construction_path) != expected_hash:
        raise ValueError("comparison manifest construction hash stale")
    if selection is not None and (selection.get("case_id") != case_id or
                                  selection.get("construction_sha256") != expected_hash or
                                  selection.get("manifest_sha256") != _sha(manifest_path)):
        raise ValueError("comparison candidate selection receipt stale")
    if candidate_id != "primary" and selection is None:
        raise ValueError("comparison fallback selection receipt missing")
    actual = json.loads((attempt / "construction.json").read_text(encoding="utf-8"))
    expected = json.loads(construction_path.read_text(encoding="utf-8"))
    if actual != expected:
        raise ValueError("comparison original construction differs from selected candidate")
    sources = [item["content"] for item in actual["files"]
               if item["path"] == "native_capture.py"]
    configs = [json.loads(item["content"]) for item in actual["files"]
               if item["path"] == "config.json"]
    if len(sources) != 1 or len(configs) != 1:
        raise ValueError("comparison selected camera source missing")
    config = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    if config != configs[0]:
        raise ValueError("comparison original camera config differs from construction")
    return {"source_sha256": hashlib.sha256(sources[0].encode()).hexdigest(),
            "cameras": config["cameras"], "duration_s": config["duration_s"],
            "rate_hz": config["rate_hz"]}


def audit_saved_attempts(plan: dict, comparison_id: str, left_attempt: Path,
                         right_attempt: Path, left_audit: Path, right_audit: Path) -> dict:
    """Compare measured original packets and bind each to its Native delivery audit."""
    records = []
    native_hashes = []
    audit_hashes = []
    camera_contracts = []
    planned = {case["case_id"]: case["controller"]["target_speed_mps"]
               for case in plan["cases"]}
    for attempt, audit_path in ((Path(left_attempt), Path(left_audit)),
                                (Path(right_attempt), Path(right_audit))):
        native_path = attempt / "result.json"
        inventory_path = attempt / "inventory.json"
        if not native_path.is_file() or not inventory_path.is_file():
            raise ValueError("saved Native result or original inventory missing")
        native = json.loads(native_path.read_text(encoding="utf-8"))
        receipt = json.loads(audit_path.read_text(encoding="utf-8"))
        case_id = native.get("case_id")
        camera_contracts.append(_selected_camera_contract(attempt, case_id))
        if native.get("diagnostic_fixture") is not False:
            raise ValueError("comparison requires non-diagnostic Native result")
        target_checks = native.get("target_checks")
        if (case_id not in planned or not isinstance(target_checks, list) or
                len(target_checks) != 1 or
                target_checks[0].get("target") != "bicycle_speed_mps" or
                target_checks[0].get("requested") != planned[case_id] or
                target_checks[0].get("matched") is not True):
            raise ValueError("saved Native speed target differs from exact planned case")
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
        if len(record["samples"]) != 900:
            raise ValueError("comparison requires exact 900-frame original bicycle window")
        check_record(record)
        records.append(record)
        native_hashes.append(_sha(native_path))
        audit_hashes.append(_sha(audit_path))
    if camera_contracts[0] != camera_contracts[1]:
        raise ValueError("fixed camera source or capture contract changed")
    result = audit(plan, comparison_id, *records)
    result["selected_camera_contract"] = camera_contracts[0]
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
