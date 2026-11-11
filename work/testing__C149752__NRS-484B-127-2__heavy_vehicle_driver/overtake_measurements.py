"""Source-bound physical passing sequence for NRS 484B.127(2).

The overtaking permission and conditions-permit qualifier remain legal review
questions. This module reports body ordering and lateral separation only.
"""

import hashlib
import json
import math
from pathlib import Path


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + name)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path) -> dict:
    root = Path(root)
    names = ("passing_history.jsonl", "road_context.json", "video_frames.jsonl")
    hashes = {}
    for name in names:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "road_context.json").read_text())
    for name in ("native_map_id", "highway_source", "lane_count_source", "road_id", "lane_forward_xy"):
        if name not in context or context[name] is None or context[name] == "":
            raise ValueError("Missing road context: " + name)
    count = context.get("same_direction_lane_count")
    if type(count) is not int or count < 1:
        raise ValueError("Invalid same-direction lane count")
    tangent = context["lane_forward_xy"]
    if not isinstance(tangent, list) or len(tangent) != 2:
        raise ValueError("Missing lane tangent")
    tx, ty = (_finite(v, "lane tangent") for v in tangent)
    norm = math.hypot(tx, ty)
    if norm == 0:
        raise ValueError("Zero lane tangent")
    tx, ty = tx/norm, ty/norm
    rows = _rows(root / "passing_history.jsonl")
    frames = _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete passing history")
    samples, prior = [], (-1, -math.inf)
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= prior[0] or time <= prior[1]:
            raise ValueError("Nonmonotone original history")
        prior = fid, time
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        bodies = {}
        for role in ("ego", "lead"):
            body = row.get(role)
            if not isinstance(body, dict) or body.get("road_id") != context["road_id"]:
                raise ValueError("Participant road identity mismatch: " + role)
            if body.get("truck_or_combination") is not True:
                raise ValueError("Unqualified truck source: " + role)
            width = _finite(body.get("overall_width_m"), "truck width")
            if width < 80 * .0254:
                raise ValueError("Truck below statutory 80-inch width")
            vertices = body.get("body_vertices_xy_m")
            if not isinstance(vertices, list) or len(vertices) < 4:
                raise ValueError("Missing complete body: " + role)
            points = []
            for vertex in vertices:
                if not isinstance(vertex, list) or len(vertex) != 2:
                    raise ValueError("Invalid body vertex")
                x, y = (_finite(v, "body vertex") for v in vertex)
                points.append((x*tx+y*ty, -x*ty+y*tx))
            bodies[role] = {"along": [min(p[0] for p in points), max(p[0] for p in points)],
                            "lateral": [min(p[1] for p in points), max(p[1] for p in points)],
                            "lane_id": body.get("lane_id"), "width_m": width}
        ego, lead = bodies["ego"], bodies["lead"]
        behind = ego["along"][1] < lead["along"][0]
        ahead = ego["along"][0] > lead["along"][1]
        lateral_clearance = max(ego["lateral"][0]-lead["lateral"][1], lead["lateral"][0]-ego["lateral"][1])
        samples.append({"frame": fid, "time_s": time, "ego_behind": behind,
                        "ego_ahead": ahead, "lateral_body_clearance_m": lateral_clearance,
                        "ego_lane_id": ego["lane_id"], "lead_lane_id": lead["lane_id"]})
    first_behind = next((i for i, sample in enumerate(samples) if sample["ego_behind"]), None)
    first_ahead = next((i for i, sample in enumerate(samples) if first_behind is not None and i > first_behind and sample["ego_ahead"]), None)
    if first_ahead is None or not any(sample["lateral_body_clearance_m"] > 0 for sample in samples[first_behind+1:first_ahead]):
        raise ValueError("No sourced lateral pass from behind to ahead")
    return {"format": "worker-truck-overtake-observations", "sources": hashes,
            "same_direction_lane_count": count, "two_lane_exemption_observed": count >= 2,
            "first_behind_frame": samples[first_behind]["frame"],
            "first_ahead_frame": samples[first_ahead]["frame"], "samples": samples,
            "overtaking_exception_judgment": "unresolved", "conditions_permit_judgment": "unresolved",
            "safe_occupancy_judgment": "unresolved", "legal_conclusion": "unresolved"}
