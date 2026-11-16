"""Independent CPU audit of the operative/Off source-controlled pair.

This checks original-source equality and declared signal differences. It does
not infer official-device status, statutory inoperability, or legal yielding.
"""
import argparse
import hashlib
import json
from pathlib import Path


PREFIX = "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__"
CASES = (PREFIX + "signal_operative", PREFIX + "signal_off")
FIXED = ("road_geometry.json", "turn_route_context.json", "stop_context.json", "road.xodr")
OBSERVED = ("crossing_history.jsonl", "stop_history.jsonl", "video_frames.jsonl",
            "trace.jsonl", "signal_context.json", "signal_history.jsonl", "capture/evidence.jsonl",
            "overview.mkv", "approach.mkv", "reference_corner.mkv",
            "driver_reference.mkv", "head_visibility_review.json",
            "other_head_visibility_review.json")
SOURCE_HASHED = ("road_geometry.json", "turn_route_context.json", "crossing_history.jsonl",
                 "signal_context.json", "signal_history.jsonl", "stop_context.json",
                 "stop_history.jsonl", "video_frames.jsonl", "head_visibility_review.json",
                 "other_head_visibility_review.json", "approach.mkv", "reference_corner.mkv")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing comparison source: " + name)
    return json.loads(path.read_text())


def _rows(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing comparison source: " + name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _checked(root, case):
    result = _read(root, "result.json")
    config = _read(root, "config.json")
    if result.get("case_id") != case or config.get("selected_case_id") != case:
        raise ValueError("Exact comparison case identity differs")
    hashes = result.get("source_evidence_hashes")
    if not isinstance(hashes, dict) or any(name not in hashes for name in SOURCE_HASHED):
        raise ValueError("Saved result lacks original signal provenance")
    for name, expected in hashes.items():
        if not (root / name).is_file() or _sha(root / name) != expected:
            raise ValueError("Result source hash differs: " + name)
    if _sha(root / "capture/evidence.jsonl") != result.get("capture_evidence_sha256"):
        raise ValueError("Capture evidence hash differs")
    checks = result.get("target_checks", [])
    if len(checks) != 1 or checks[0].get("target") != "ego_native_signal_state_at_body_entry" or checks[0].get("matched") is not True:
        raise ValueError("Saved signal target is missing or unmatched")
    return config, result


def audit(operative, off):
    roots = [Path(operative), Path(off)]
    pairs = [_checked(root, case) for root, case in zip(roots, CASES)]
    compared_configs = [{key: value for key, value in config.items()
                         if key not in ("selected_case_id", "target_signal_state")}
                        for config, _ in pairs]
    if compared_configs[0] != compared_configs[1]:
        raise ValueError("Compared construction policy changed")
    fixed_hashes = {}
    for name in FIXED:
        paths = [root / name for root in roots]
        if any(not path.is_file() for path in paths):
            raise ValueError("Missing fixed comparison source: " + name)
        hashes = [_sha(path) for path in paths]
        if hashes[0] != hashes[1]:
            raise ValueError("Fixed comparison source differs: " + name)
        fixed_hashes[name] = hashes[0]
    histories = [_rows(root, "signal_history.jsonl") for root in roots]
    observed_hashes = {}
    for root, history in zip(roots, histories):
        frame_map = _rows(root, "video_frames.jsonl")
        context = _read(root, "signal_context.json")
        if not history or len(history) != len(frame_map):
            raise ValueError("Signal history lacks its original frame coverage")
        for index, (row, frame) in enumerate(zip(history, frame_map)):
            if set(row) != {"frame", "time_s", "native_signal_id", "state", "other_native_signal_id", "other_state"}:
                raise ValueError("Signal row contains an undeclared field")
            if (row["native_signal_id"] != context.get("native_signal_id") or
                    row["other_native_signal_id"] != context.get("other_native_signal_id")):
                raise ValueError("Signal identity differs from source context")
            if (frame.get("video_frame") != index or frame.get("carla_frame") != row["frame"]
                    or abs(frame.get("time_s", float("inf")) - row["time_s"]) > 1e-4):
                raise ValueError("Signal original frame join differs")
        observed_hashes[root.name] = {name: _sha(root / name) for name in OBSERVED}
    if len(histories[0]) != len(histories[1]):
        raise ValueError("Signal histories have different coverage")
    expected = (("Green", "Red"), ("Off", "Off"))
    for (config, result), root, states in zip(pairs, roots, expected):
        source = _rows(root, "signal_history.jsonl")
        entry = _read(root, "analysis-report.json")["measurements"]["signal_at_entry"]["value"]["at_body_entry"]
        at_entry = (entry["ego"]["native_state"], entry["other"]["native_state"])
        if at_entry != states or result["measured_values"]["ego_signal_state_at_entry"] != states[0]:
            raise ValueError("Compared Native states at entry differ from selected cases")
        if config.get("target_signal_state") != states[0]:
            raise ValueError("Selected signal request differs")
        by_frame = {row["frame"]: row for row in source}
        for role, state in zip(("ego", "other"), states):
            row = by_frame[entry[role]["frame"]]
            if row["state" if role == "ego" else "other_state"] != state:
                raise ValueError("Measured entry state lacks original frame")
    return {"format": "worker-c125751-independent-comparison-audit",
            "case_ids": list(CASES), "fixed_source_hashes": fixed_hashes,
            "deliberate_difference": "Native signal states at measured body entries",
            "operative_states": list(expected[0]), "off_states": list(expected[1]),
            "frames": len(histories[0]), "observed_source_hashes": observed_hashes,
            "passed": True,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--operative", required=True, type=Path)
    parser.add_argument("--off", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.operative, args.off), indent=2))
