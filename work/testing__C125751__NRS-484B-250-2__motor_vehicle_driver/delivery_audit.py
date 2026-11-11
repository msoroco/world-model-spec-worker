"""Independent source and measurement audit for the selected signal pair.

This CPU audit proves the delivery checker works on retained diagnostic sources.
Synthetic pixels and declared reviews do not establish physical or legal truth.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from camera_setup import SIZES
from worker_exchange.media import audit as audit_video
from worker_exchange.measurement_contract import validate, verify_report

PREFIX = "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__"
CASES = {PREFIX + "signal_operative": "Green", PREFIX + "signal_off": "Off"}
CAMERAS = tuple(name + ".mkv" for name in SIZES)
FRAMES = 1100


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text())


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit_delivery(case_id, attempt, package, receipt_dir=None):
    if case_id not in CASES:
        raise ValueError("Unknown exact C125751 delivery case")
    attempt, package = Path(attempt), Path(package)
    config, result = _read(attempt / "config.json"), _read(attempt / "result.json")
    if config.get("selected_case_id") != case_id or result.get("case_id") != case_id:
        raise ValueError("Exact delivery case identity differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("rate_hz"), config.get("duration_s")) != (
            "NRS-484B-250-2", "C125751", 20, 55):
        raise ValueError("Exact C125751 law, cell, rate and duration required")
    if config.get("target_signal_state") != CASES[case_id]:
        raise ValueError("Selected Native signal request differs")
    if result.get("provenance_kind") != "synthetic_fixture" or result.get("physical_acceptance_claimed") is not False:
        raise ValueError("Diagnostic fixture must not claim physical acceptance")
    hashes = result.get("source_evidence_hashes")
    if not isinstance(hashes, dict) or not {"video_frames.jsonl", "signal_history.jsonl",
            "crossing_history.jsonl", "stop_history.jsonl", "head_visibility_review.json",
            "other_head_visibility_review.json"} <= set(hashes):
        raise ValueError("Saved result lacks all original participant and device sources")
    for name, expected in hashes.items():
        if not (attempt / name).is_file() or _sha(attempt / name) != expected:
            raise ValueError("Result source hash differs: " + name)
    if _sha(attempt / "capture/evidence.jsonl") != result.get("capture_evidence_sha256"):
        raise ValueError("Capture evidence hash differs")
    if result.get("trace_reference") != "trace.jsonl" or result.get("video_frame_map_reference") != "video_frames.jsonl":
        raise ValueError("Saved trace or original frame-map reference differs")

    mapping_path = attempt / "video_frames.jsonl"
    mapping = _rows(mapping_path)
    if len(mapping) != FRAMES:
        raise ValueError("Full original frame-map duration required")
    previous_frame, previous_time = -1, float("-inf")
    for index, row in enumerate(mapping):
        frame, time = row.get("carla_frame"), row.get("time_s")
        if (row.get("video_frame") != index or type(frame) is not int or frame <= previous_frame
                or type(time) not in (int, float) or not math.isfinite(time) or time <= previous_time):
            raise ValueError("Nonmonotone original video frame/time join")
        if index and abs(time - previous_time - .05) > 1e-3:
            raise ValueError("Original source frames are not 20 Hz")
        previous_frame, previous_time = frame, time
    trace = _rows(attempt / "trace.jsonl")
    if len(trace) != FRAMES or any(row.get("frame") != mapping[i]["carla_frame"]
                                  or row.get("time_s") != mapping[i]["time_s"] for i, row in enumerate(trace)):
        raise ValueError("Original trace and video frame/time join differs")
    for name in ("crossing_history.jsonl", "stop_history.jsonl", "signal_history.jsonl"):
        rows = _rows(attempt / name)
        if len(rows) != FRAMES or any(row.get("frame") != mapping[i]["carla_frame"]
                                      or row.get("time_s") != mapping[i]["time_s"] for i, row in enumerate(rows)):
            raise ValueError("Participant or device time join differs: " + name)

    plan, contract = _read(package / "case-plan.json"), _read(package / "measurement-contract.json")
    validate(contract, plan["requirement_dispositions"], (package / "finalizer.py").read_text(), case_id)
    analysis_path = attempt / "analysis-report.json"
    analysis = _read(analysis_path)
    if analysis.get("case_id") != case_id or analysis.get("physical_acceptance_claimed") is not False:
        raise ValueError("Analysis case or physical-acceptance claim differs")
    measurements = verify_report(contract, analysis, attempt)
    if len(measurements) != 4:
        raise ValueError("Four exact source-hashed measurements required")
    entry = measurements["signal_at_entry"]["value"]["at_body_entry"]
    if entry["ego"]["native_state"] != CASES[case_id]:
        raise ValueError("Measured Native state differs from selected case")
    checks = result.get("target_checks")
    if (not isinstance(checks, list) or len(checks) != 1 or checks[0].get("target") != "ego_native_signal_state_at_body_entry"
            or checks[0].get("matched") is not True or checks[0].get("measured") != CASES[case_id]):
        raise ValueError("Saved Native signal target is missing or unmatched")
    for name in ("head_visibility_review.json", "other_head_visibility_review.json"):
        review = _read(attempt / name)
        source = review.get("camera", "") + ".mkv"
        if source not in CAMERAS or review.get("source_video_sha256") != _sha(attempt / source):
            raise ValueError("Signal-head review lacks current source camera: " + name)

    if set(result.get("video_references", [])) != set(CAMERAS):
        raise ValueError("Saved result lacks all four named original cameras")
    if receipt_dir is not None:
        receipt_dir = Path(receipt_dir)
        receipt_dir.mkdir(parents=True, exist_ok=True)
    decodes = {}
    for index, name in enumerate(CAMERAS):
        receipt = audit_video(attempt / name, FRAMES, mapping_sha256=_sha(mapping_path),
                              receipt=(receipt_dir / f"{index}-{name}.json") if receipt_dir else None)
        if receipt["dimensions"] != list(SIZES[name.removesuffix(".mkv")]):
            raise ValueError("Original camera dimensions differ: " + name)
        decodes[name] = {"video_sha256": receipt["video_sha256"], "frames": receipt["frames"],
                         "rgb_sequence_sha256": receipt["rgb_sequence_sha256"]}
    return {"format": "worker-c125751-independent-delivery-audit", "case_id": case_id,
            "original_frame_map_sha256": _sha(mapping_path), "analysis_sha256": _sha(analysis_path),
            "result_sha256": _sha(attempt / "result.json"), "verified_measurements": sorted(measurements),
            "source_decodes": decodes, "software_audit_passed": True,
            "actual_pixels_reviewed_for_physical_truth": False, "physical_acceptance_claimed": False,
            "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit_delivery(args.case, args.attempt, args.package, args.receipt_dir)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": result["case_id"], "software_audit_passed": True,
                      "physical_acceptance_claimed": False}))
