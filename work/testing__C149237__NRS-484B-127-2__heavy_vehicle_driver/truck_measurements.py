"""Source-bound geometric observations for NRS 484B.127(2).

Widths and longitudinal body gap are measured in metres. The statutory 80 inch
and 500 foot values are reported exactly; conditions-permit, safe occupancy and
the legal overtaking exception remain review questions.
"""

import hashlib
import json
import math
from pathlib import Path


MIN_WIDTH_M = 80 * 0.0254
REQUIRED_GAP_M = 500 * 0.3048
REQUIRED = ("truck_history.jsonl", "road_context.json", "video_frames.jsonl")


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _body_span(actor, label):
    vertices = actor.get("body_vertices_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Missing body vertices: " + label)
    projected = []
    for vertex in vertices:
        if not isinstance(vertex, list) or len(vertex) != 2:
            raise ValueError("Invalid body vertex: " + label)
        projected.append(tuple(_finite(v, "body vertex") for v in vertex))
    return projected


def analyze(root: Path) -> dict:
    root = Path(root)
    hashes = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "road_context.json").read_text())
    for key in ("native_map_id", "road_id", "lane_id", "same_direction_lane_count",
                "lane_forward_xy", "lane_count_source"):
        if key not in context:
            raise ValueError("Missing Native road context: " + key)
    count = context["same_direction_lane_count"]
    if type(count) is not int or count < 1:
        raise ValueError("Invalid same-direction lane count")
    tangent = context["lane_forward_xy"]
    if not isinstance(tangent, list) or len(tangent) != 2:
        raise ValueError("Missing lane tangent")
    tx, ty = (_finite(value, "lane tangent") for value in tangent)
    norm = math.hypot(tx, ty)
    if norm <= 0:
        raise ValueError("Zero lane tangent")
    tx, ty = tx / norm, ty / norm
    rows, frames = _rows(root / "truck_history.jsonl"), _rows(root / "video_frames.jsonl")
    if not rows or len(rows) != len(frames):
        raise ValueError("Incomplete history/frame map")
    samples, previous = [], (-1, -math.inf)
    for index, (row, frame) in enumerate(zip(rows, frames)):
        frame_id, time = row.get("frame"), row.get("time_s")
        time = _finite(time, "time")
        if type(frame_id) is not int or frame_id <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = (frame_id, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != frame_id or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        participants = {}
        for name in ("ego", "lead"):
            actor = row.get(name)
            if not isinstance(actor, dict) or actor.get("road_id") != context["road_id"] or actor.get("lane_id") != context["lane_id"]:
                raise ValueError("Participant not in sourced following lane: " + name)
            width = _finite(actor.get("overall_width_m"), "overall width")
            points = _body_span(actor, name)
            along = [x * tx + y * ty for x, y in points]
            participants[name] = {"width_m": width, "length_interval_m": [min(along), max(along)],
                                  "is_truck_or_combination": actor.get("is_truck_or_combination") is True}
        gap = participants["lead"]["length_interval_m"][0] - participants["ego"]["length_interval_m"][1]
        samples.append({"frame": frame_id, "time_s": time, "longitudinal_body_gap_m": gap,
                        "ego_behind_lead": gap >= 0,
                        "ego": participants["ego"], "lead": participants["lead"]})
    return {"format": "worker-truck-following-observations", "sources": hashes,
            "native_road_context": context, "minimum_qualifying_width_m": MIN_WIDTH_M,
            "statutory_space_m": REQUIRED_GAP_M, "samples": samples,
            "same_direction_two_lane_exemption_observed": count >= 2,
            "conditions_permit_judgment": "unresolved", "safe_overtaker_occupancy_judgment": "unresolved",
            "legal_conclusion": "unresolved"}
