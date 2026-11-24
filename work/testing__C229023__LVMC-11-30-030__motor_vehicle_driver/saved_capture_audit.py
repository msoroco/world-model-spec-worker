"""Independently reopen the original Native clock and actor source packet."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from crosswalk_measurements import ASSIGNMENT_ID
from native_crosswalk_capture import FRAME_COUNT


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def audit(*, directory: str | Path, case_id: str, fixture_mode: bool = False) -> dict:
    root = Path(directory)
    receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
    if receipt.get("assignment_id") != ASSIGNMENT_ID or receipt.get("case_id") != case_id or receipt.get("diagnostic_fixture") is not fixture_mode:
        raise ValueError("original exact-case receipt required")
    if receipt.get("fps") != 20 or receipt.get("frame_count") != FRAME_COUNT:
        raise ValueError("complete original capture profile required")
    for name, field in (("context.json", "context_sha256"), ("trace.jsonl", "trace_sha256"),
                        ("frame-map.jsonl", "frame_map_sha256")):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != receipt.get(field):
            raise ValueError(f"changed original {name} bytes")
    context = json.loads((root / "context.json").read_text(encoding="utf-8"))
    if context.get("case_id") != case_id:
        raise ValueError("original context case differs")
    trace, mapping = _rows(root / "trace.jsonl"), _rows(root / "frame-map.jsonl")
    if len(trace) != FRAME_COUNT or len(mapping) != FRAME_COUNT:
        raise ValueError("incomplete original Native tick and camera map")
    ids = {"ego": context.get("ego_vehicle_identity"), "lead": context.get("lead_vehicle_identity"),
           "pedestrian": context.get("pedestrian_identity")}
    if any(not isinstance(v, str) or not v for v in ids.values()) or len(set(ids.values())) != 3:
        raise ValueError("three distinct original actor identities required")
    first = trace[0].get("frame")
    if type(first) is not int or first < 0:
        raise ValueError("original Native starting frame required")
    for index, (row, frame_map) in enumerate(zip(trace, mapping)):
        frame = first + index
        if (type(row.get("frame")) is not int or type(frame_map.get("carla_frame")) is not int
                or type(frame_map.get("video_frame")) is not int
                or row["frame"] != frame or frame_map["carla_frame"] != frame
                or frame_map["video_frame"] != index):
            raise ValueError("actor and camera frame join differs")
        time_s = index / 20
        if any(type(value) not in (int, float) or not math.isfinite(value) or abs(value - time_s) > 1e-6
               for value in (row.get("time_s"), frame_map.get("time_s"))):
            raise ValueError("actor and camera 20 Hz clock differs")
        sources = row.get("actor_sources")
        if not isinstance(sources, dict) or set(sources) != set(ids) or any(
            not isinstance(sources[role], str) or str(frame) not in sources[role] for role in ids
        ):
            raise ValueError("original actor source join missing")
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id, "frame_count": FRAME_COUNT,
            "first_native_frame": first, "last_native_frame": first + FRAME_COUNT - 1,
            "trace_sha256": receipt["trace_sha256"],
            "frame_map_sha256": receipt["frame_map_sha256"],
            "camera_status": "same_tick_identity_only_saved_media_decode_required",
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}
