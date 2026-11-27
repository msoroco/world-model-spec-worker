"""Convert original Native pose/control rows and explicit pixel review to a trace.

The reviewer supplies every frame-bound visibility fact. Geometry and braking
come only from original Native observations. This conversion makes no verdict.
"""

import argparse
import json
import math
from pathlib import Path

from measure_readiness import ASSIGNMENT, CAMERAS, FRAMES, lines
from audit_capture import audit as audit_capture
from scene import CASES, request


FLAGS = ("emergency_flashing_visible", "emergency_motion_visible",
         "hand_signal_visible")


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _surface_gap(first, second):
    def bounds(points):
        if not isinstance(points, list) or len(points) < 4 or any(len(point) != 2 or
                                  not all(_finite(coordinate) for coordinate in point)
                                  for point in points):
            raise ValueError("Original Native body vertices missing")
        return (min(p[0] for p in points), max(p[0] for p in points),
                min(p[1] for p in points), max(p[1] for p in points))
    a, b = bounds(first), bounds(second)
    dx = max(0, a[0] - b[1], b[0] - a[1])
    dy = max(0, a[2] - b[3], b[2] - a[3])
    return math.hypot(dx, dy)


def convert(frames, observed, annotations):
    if len(frames) != FRAMES or len(observed) != FRAMES or len(annotations) != FRAMES:
        raise ValueError("Original frame, actor and pixel-review counts must be 600")
    output = []
    for index, (frame, row, note) in enumerate(zip(frames, observed, annotations)):
        native = frame.get("native_frame")
        if (frame.get("video_frame") != index or type(native) is not int or
                row.get("frame") != index or row.get("native_frame") != native or
                note.get("video_frame") != index):
            raise ValueError("Original Native, video and review frame join failed")
        if row.get("source_kind") != "original_native_motion":
            raise ValueError("Motion provenance must be original Native")
        if note.get("source_camera") not in CAMERAS or note.get("source_native_frame") != native:
            raise ValueError("Frame-bound original pixel source missing")
        if any(type(note.get(flag)) is not bool for flag in FLAGS):
            raise ValueError("Frame-bound visibility review missing")
        actors = row.get("actors", {})
        ego, emergency = actors.get("ego", {}), actors.get("emergency", {})
        for name, actor in (("ego", ego), ("emergency", emergency)):
            if not _finite(actor.get("native_speed_mps")) or actor["native_speed_mps"] < 0:
                raise ValueError(name + " original speed missing")
        brake = row.get("ego_brake_observed")
        if not _finite(brake) or not 0 <= brake <= 1:
            raise ValueError("Original Native ego brake readback missing")
        output.append({"video_frame": index, "native_frame": native,
                       "source_kind": "original_native_motion",
                       "ego_speed_mps": ego["native_speed_mps"],
                       "emergency_speed_mps": emergency["native_speed_mps"],
                       "surface_gap_m": _surface_gap(ego.get("native_body_xy_m"),
                                                     emergency.get("native_body_xy_m")),
                       "ego_brake": brake,
                       **{flag: note[flag] for flag in FLAGS}})
    return output


def process(directory):
    directory = Path(directory).resolve()
    if ".runtime-work" not in directory.parts:
        raise ValueError("Original attempt must be under .runtime-work")
    frame_path, actor_path = directory / "video_frames.jsonl", directory / "observed-actors.jsonl"
    review_path = directory / "emergency_review.json"
    request_path = directory / "native-request.json"
    for path in (frame_path, actor_path, review_path, request_path):
        if not path.is_file():
            raise ValueError("Missing original source: " + path.name)
    captured_request = json.loads(request_path.read_text())
    condition = captured_request.get("requested_setting")
    if condition not in CASES or captured_request != request(condition):
        raise ValueError("Original attempt request differs from exact construction")
    capture_audit = audit_capture(directory, condition)
    review = json.loads(review_path.read_text())
    if review.get("assignment_id") != ASSIGNMENT or review.get("review_kind") != "original_source_review":
        raise ValueError("Independent original-source review required")
    trace = convert(lines(frame_path), lines(actor_path), review.get("frame_annotations", []))
    destination = directory / "approach_trace.jsonl"
    with destination.open("x") as stream:
        for row in trace:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    return {"trace": str(destination), "rows": len(trace),
            "case_id": captured_request["case_id"],
            "capture_audit_sources": capture_audit["source_sha256"],
            "source_kind": "original_native_motion", "legal_verdict": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("original_attempt_dir")
    args = parser.parse_args()
    print(json.dumps(process(args.original_attempt_dir), sort_keys=True))
