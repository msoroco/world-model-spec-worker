"""Independent source-integrity audit for one original C110969 attempt.

This is a CPU audit of saved evidence bindings. It never asserts video pixels,
legal necessity, or physical completion from a diagnostic fixture.
"""

import argparse
import hashlib
import json
from pathlib import Path

from measure_gap import measure


PREFIX = "testing__C110969__LVMC-11-52-130-A11__motor_vehicle_driver__"
SUFFIXES = {"stop_14ft", "stop_15ft", "stop_16ft", "stand_14ft",
            "traffic_14ft", "police_14ft", "device_14ft"}
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _source(root, binding):
    relative = Path(binding["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Source path escapes attempt")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Required source missing or outside attempt")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != binding["sha256"]:
        raise ValueError("Required source hash mismatch")
    return path


def _rows(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _frame_ids(rows, name, world_frames):
    if len(rows) != 900 or [row.get("frame") for row in rows] != list(range(900)):
        raise ValueError(name + " needs exact 900 frame indices")
    if [row.get("world_frame") for row in rows] != world_frames:
        raise ValueError(name + " world frame join mismatch")


def audit(attempt_path, *, allow_diagnostic=False):
    attempt_path = Path(attempt_path)
    packet = json.loads(attempt_path.read_text(encoding="utf-8"))
    case_id = packet.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(PREFIX) or \
            case_id.removeprefix(PREFIX) not in SUFFIXES:
        raise ValueError("Wrong exact case")
    if not packet.get("attempt_id") or not packet.get("recording_id"):
        raise ValueError("Attempt or recording identity missing")
    if packet.get("acquisition_kind") != "original_native" and not allow_diagnostic:
        raise ValueError("Diagnostic source cannot satisfy delivery audit")
    root = attempt_path.parent
    measurement_path = _source(root, packet["measurement_packet"])
    measurement_packet = json.loads(measurement_path.read_text(encoding="utf-8"))
    pose_path = _source(measurement_path.parent, measurement_packet["pose_source"])
    map_path = _source(measurement_path.parent, measurement_packet["map_source"])
    source_map_path = _source(root, packet["map_packet"])
    map_geometry = json.loads(map_path.read_text(encoding="utf-8"))
    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    if map_geometry.get("map_source_sha256") != packet["map_packet"]["sha256"] or \
            map_geometry.get("opendrive_sha256") != source_map.get("opendrive_sha256") or \
            map_geometry.get("map_id") != source_map.get("map_name") or \
            case_id not in source_map.get("case_ids", []):
        raise ValueError("Map source and measurement geometry binding mismatch")
    measurement = measure(measurement_path)
    pose_rows = _rows(pose_path)
    world_frames = [row.get("world_frame") for row in pose_rows]
    if any(not isinstance(value, int) for value in world_frames) or \
            world_frames != list(range(world_frames[0], world_frames[0] + 900)):
        raise ValueError("Original Native world frames are not contiguous")
    frame_map_path = _source(root, packet["frame_map"])
    frame_rows = _rows(frame_map_path)
    _frame_ids(frame_rows, "Frame map", world_frames)
    if any(abs(row.get("time_s", -1) - row["frame"] / 20) > 1e-6
           for row in frame_rows):
        raise ValueError("Frame map timing mismatch")
    context_path = _source(root, packet["context"])
    context_rows = _rows(context_path)
    _frame_ids(context_rows, "Original context", world_frames)
    if any(not isinstance(row.get("participants"), list) or
           not isinstance(row.get("directions"), dict) for row in context_rows):
        raise ValueError("Original context observation fields missing")
    camera_bindings = packet.get("cameras", {})
    if set(camera_bindings) != set(CAMERAS):
        raise ValueError("Four named camera sources required")
    camera_hashes = {}
    for name in CAMERAS:
        path = _source(root, camera_bindings[name])
        rows = _rows(path)
        _frame_ids(rows, name, world_frames)
        for row in rows:
            if row.get("camera") != name or not row.get("original_frame_sha256") or \
                    not row.get("original_frame_path"):
                raise ValueError(name + " original camera frame receipt missing")
            frame_path = _source(root, {"path": row["original_frame_path"],
                                        "sha256": row["original_frame_sha256"]})
            with frame_path.open("rb") as stream:
                if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(name + " original camera frame is not PNG")
        camera_hashes[name] = camera_bindings[name]["sha256"]
    suffix = case_id.removeprefix(PREFIX)
    expected_gap_ft = int(suffix.split("_")[1].removesuffix("ft")) if suffix in SUFFIXES else None
    if packet.get("requested_front_body_gap_ft") != expected_gap_ft:
        raise ValueError("Exact case requested gap mismatch")
    return {
        "format": "worker-saved-source-audit",
        "case_id": case_id,
        "attempt_id": packet["attempt_id"],
        "recording_id": packet["recording_id"],
        "native_source": packet.get("acquisition_kind") == "original_native",
        "time_join": True,
        "four_camera_receipts": True,
        "original_frame_count": 900,
        "measurement": measurement,
        "frame_map_sha256": packet["frame_map"]["sha256"],
        "context_sha256": packet["context"]["sha256"],
        "camera_receipt_sha256": camera_hashes,
        "full_video_decode": False,
        "actual_pixels": False,
        "all_participants": False,
        "physical_completion": False,
        "legal_necessity": "unresolved",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, allow_diagnostic=args.allow_diagnostic), sort_keys=True))
