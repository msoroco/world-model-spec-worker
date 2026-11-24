"""Measure original left-turn traces only after their source bytes are sealed.

This is a saved-only step. It never starts CARLA or infers a legal verdict.
The receipt is an acquisition join, not evidence that a simulated maneuver
actually satisfied the statutory condition or that its pixels were accepted.
"""

import hashlib
import json
from pathlib import Path

from left_turn_measurements import measure
from native_intersection import validate


ASSIGNMENT_ID = "testing__C109749__NRS-484B-253__motor_vehicle_driver"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def process(*, case_id, map_path, trace_path, receipt_path, allow_diagnostic=False):
    """Return measured histories with exact map/trace/receipt source bindings."""
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case ID required")
    receipt = _load(receipt_path)
    for key in ("assignment_id", "case_id", "map_sha256", "trace_sha256", "native_map_sha256", "source_id",
                "frame_count", "simulator_frame_rate_hz", "diagnostic_fixture"):
        if key not in receipt:
            raise ValueError("acquisition receipt missing " + key)
    if receipt["assignment_id"] != ASSIGNMENT_ID or receipt["case_id"] != case_id:
        raise ValueError("acquisition receipt identity mismatch")
    if receipt["diagnostic_fixture"] and not allow_diagnostic:
        raise ValueError("diagnostic fixture cannot establish delivered original measurement")
    if receipt["simulator_frame_rate_hz"] != 20:
        raise ValueError("original trace must use 20 Hz fixed timestep")
    if _sha(map_path) != receipt["map_sha256"] or _sha(trace_path) != receipt["trace_sha256"]:
        raise ValueError("sealed source bytes changed")
    map_packet = _load(map_path)
    validate(map_packet)
    if map_packet["map_sha256"] != receipt["native_map_sha256"]:
        raise ValueError("Native map identity changed")
    samples = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(samples) != receipt["frame_count"] or not samples:
        raise ValueError("original trace frame count mismatch")
    for first, second in zip(samples, samples[1:]):
        if second["frame"] != first["frame"] + 1:
            raise ValueError("original trace dropped or duplicated frames")
        if abs((second["time_s"] - first["time_s"]) - 0.05) > 0.002:
            raise ValueError("original trace timestamp cadence differs from 20 Hz")
    if "frame_map_sha256" in receipt:
        frame_map_path = Path(receipt_path).parent / "original-frame-map.json"
        if _sha(frame_map_path) != receipt["frame_map_sha256"]:
            raise ValueError("sealed camera frame map changed")
        frame_map = _load(frame_map_path)
        if frame_map.get("case_id") != case_id or len(frame_map.get("frames", [])) != len(samples):
            raise ValueError("original camera frame map identity/count mismatch")
        for sample, camera_row in zip(samples, frame_map["frames"]):
            if sample["frame"] != camera_row.get("frame") or sample["time_s"] != camera_row.get("time_s"):
                raise ValueError("original camera frame join mismatch")
            cameras = camera_row.get("cameras", {})
            if set(cameras) != {"overview", "approach", "reference_corner", "driver_reference"}:
                raise ValueError("four original cameras required")
            for entry in cameras.values():
                relative = Path(entry["path"])
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("original camera path escapes attempt")
                if _sha(Path(receipt_path).parent / relative) != entry["sha256"]:
                    raise ValueError("sealed original camera bytes changed")
    measured = measure(samples, map_packet["intersection_polygon"],
                       source_id=receipt["source_id"], map_sha256=map_packet["map_sha256"])
    measured.update({"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
                     "source_bindings": {"map_packet_sha256": receipt["map_sha256"],
                                         "original_trace_sha256": receipt["trace_sha256"],
                                         "acquisition_receipt_sha256": _sha(receipt_path)},
                     "diagnostic_fixture": receipt["diagnostic_fixture"],
                     "physical_acceptance": "unverified", "legal_judgment": "unresolved"})
    return measured
