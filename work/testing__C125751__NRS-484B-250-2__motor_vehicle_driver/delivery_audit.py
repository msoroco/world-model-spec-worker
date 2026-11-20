"""Independent source and measurement audit for the selected C125751 cases.

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
CASES = {PREFIX + "signal_operative": "Green", PREFIX + "signal_off": "Off",
         PREFIX + "opposite_left_turn": "Off",
         PREFIX + "opposite_straight_comparator": "Off"}
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
    opposite = case_id.endswith("__opposite_left_turn")
    straight = case_id.endswith("__opposite_straight_comparator")
    if not (opposite or straight) and config.get("target_signal_state") != CASES[case_id]:
        raise ValueError("Selected Native signal request differs")
    if result.get("provenance_kind") != "synthetic_fixture" or result.get("physical_acceptance_claimed") is not False:
        raise ValueError("Diagnostic fixture must not claim physical acceptance")
    hashes = result.get("source_evidence_hashes")
    required_sources = {"video_frames.jsonl", "signal_history.jsonl",
                        "crossing_history.jsonl", "stop_history.jsonl"}
    required_sources |= ({"body_history.jsonl", "turn_route_context.json",
                          "opposite-site-review.json"} if opposite else
                         {"body_history.jsonl", "turn_route_context.json",
                          "straight-route-source.json", "opposite-site-review.json"} if straight else
                         {"head_visibility_review.json", "other_head_visibility_review.json"})
    if not isinstance(hashes, dict) or not required_sources <= set(hashes):
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

    plan = _read(package / "case-plan.json")
    if opposite or straight:
        contract = _read(package / ("straight-measurement-contract.json" if straight else "opposite-measurement-contract.json"))
        construction = _read(package / ("straight-primary-construction.json" if straight else "opposite-primary-construction.json"))
        analyzer = next(item["content"] for item in construction["files"]
                        if item["path"] == "runner.py")
    else:
        contract = _read(package / "measurement-contract.json")
        analyzer = (package / "finalizer.py").read_text()
    validate(contract, plan["requirement_dispositions"], analyzer, case_id)
    analysis_path = attempt / "analysis-report.json"
    analysis = _read(analysis_path)
    if analysis.get("case_id") != case_id or analysis.get("physical_acceptance_claimed") is not False:
        raise ValueError("Analysis case or physical-acceptance claim differs")
    measurements = verify_report(contract, analysis, attempt)
    if len(measurements) != 4:
        raise ValueError("Four exact source-hashed measurements required")
    if straight:
        states = measurements["straight_signal_at_entry"]["value"]["states_at_body_entry"]
        if states["ego"]["state"] != CASES[case_id] or states["other"]["state"] != CASES[case_id]:
            raise ValueError("Measured Native state differs from selected case")
    else:
        entry = measurements["signal_at_entry"]["value"]
        if not opposite:
            entry = entry["at_body_entry"]
        if entry["ego"]["native_state"] != CASES[case_id]:
            raise ValueError("Measured Native state differs from selected case")
    checks = result.get("target_checks")
    if opposite or straight:
        if (not isinstance(checks, list) or len(checks) != 1 or
                checks[0].get("target") != ("opposing_straight_body_entries" if straight else "opposing_left_turn_body_entries") or
                checks[0].get("matched") is not True or
                checks[0].get("physical_cause_confirmed") is not False):
            raise ValueError("Saved opposing body-entry target is missing or unmatched")
        timing = measurements["straight_body_entry" if straight else "body_entry_timing"]["value"]["first_body_entry"]
        if not all(timing.get(role, {}).get("frame") in {row["carla_frame"] for row in mapping}
                   for role in ("ego", "other")):
            raise ValueError("Opposite-turn body entries lack original frame join")
    elif (not isinstance(checks, list) or len(checks) != 1 or checks[0].get("target") != "ego_native_signal_state_at_body_entry"
          or checks[0].get("matched") is not True or checks[0].get("measured") != CASES[case_id]):
        raise ValueError("Saved Native signal target is missing or unmatched")
    for name in (() if opposite or straight else ("head_visibility_review.json", "other_head_visibility_review.json")):
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
