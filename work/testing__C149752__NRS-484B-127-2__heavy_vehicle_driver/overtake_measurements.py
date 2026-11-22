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


def analyze_following(root: Path) -> dict:
    """Measure every joined body gap; leave road and safety judgments open.

    The 1 mm band labels sampled equality at the precision of the diagnostic
    coordinates. It is a measurement tolerance, not a legal safe harbor.
    """
    root = Path(root)
    names = ("following_history.jsonl", "road_context.json", "video_frames.jsonl")
    sources = {}
    for name in names:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "road_context.json").read_text())
    for name in ("native_map_id", "highway_source", "lane_count_source", "road_id", "lane_forward_xy"):
        if context.get(name) in (None, ""):
            raise ValueError("Missing road context: " + name)
    lane_count = context.get("same_direction_lane_count")
    if type(lane_count) is not int or lane_count < 1:
        raise ValueError("Invalid same-direction lane count")
    tangent = context["lane_forward_xy"]
    if not isinstance(tangent, list) or len(tangent) != 2:
        raise ValueError("Missing lane tangent")
    tx, ty = (_finite(v, "lane tangent") for v in tangent)
    length = math.hypot(tx, ty)
    if length == 0:
        raise ValueError("Zero lane tangent")
    tx, ty = tx / length, ty / length
    history = _rows(root / "following_history.jsonl")
    frames = _rows(root / "video_frames.jsonl")
    if len(history) < 3 or len(history) != len(frames):
        raise ValueError("Incomplete following history")
    observations = []
    identities = None
    previous = (-1, -math.inf)
    for index, (row, frame) in enumerate(zip(history, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        if index and abs(time - previous[1] - .05) > .01:
            raise ValueError("Missing 20 Hz following sample")
        previous = fid, time
        bodies = {}
        ids = []
        for role in ("ego", "lead"):
            body = row.get(role)
            if not isinstance(body, dict) or body.get("road_id") != context["road_id"]:
                raise ValueError("Participant road identity mismatch: " + role)
            actor_id = body.get("actor_id")
            if type(actor_id) is not int:
                raise ValueError("Missing participant actor ID: " + role)
            ids.append(actor_id)
            if body.get("truck_or_combination") is not True:
                raise ValueError("Unqualified truck source: " + role)
            width = _finite(body.get("overall_width_m"), "truck width")
            if width < 80 * .0254:
                raise ValueError("Truck below statutory 80-inch width")
            vertices = body.get("body_vertices_xy_m")
            if not isinstance(vertices, list) or len(vertices) < 4:
                raise ValueError("Missing complete body: " + role)
            projections = []
            for vertex in vertices:
                if not isinstance(vertex, list) or len(vertex) != 2:
                    raise ValueError("Invalid body vertex")
                x, y = (_finite(v, "body vertex") for v in vertex)
                projections.append((x * tx + y * ty, -x * ty + y * tx))
            lateral_width = max(p[1] for p in projections) - min(p[1] for p in projections)
            if abs(lateral_width - width) > .05:
                raise ValueError("Body width and declared width disagree: " + role)
            bodies[role] = (min(p[0] for p in projections), max(p[0] for p in projections), body.get("lane_id"))
        if ids[0] == ids[1] or (identities is not None and tuple(ids) != identities):
            raise ValueError("Participant actor identity changed")
        identities = tuple(ids)
        ego, lead = bodies["ego"], bodies["lead"]
        if ego[2] is None or ego[2] != lead[2]:
            raise ValueError("Participants are not in the same sourced lane")
        gap_m = lead[0] - ego[1]
        if gap_m < 0:
            raise ValueError("Subject body no longer follows lead body")
        delta_m = gap_m - 500 * .3048
        relation = "at_sampled_precision" if abs(delta_m) <= .001 else ("below" if delta_m < 0 else "above")
        observations.append({"frame": fid, "time_s": time, "body_gap_m": gap_m,
                             "body_gap_ft": gap_m / .3048, "delta_from_500_ft_m": delta_m,
                             "sample_relation": relation})
    return {"format": "worker-truck-following-observations", "sources": sources,
            "actor_ids": {"ego": identities[0], "lead": identities[1]},
            "same_direction_lane_count": lane_count,
            "two_lane_nonapplication_context": lane_count >= 2,
            "sampled_gap_min_m": min(o["body_gap_m"] for o in observations),
            "sampled_gap_max_m": max(o["body_gap_m"] for o in observations),
            "all_samples_at_or_above_500_ft": all(o["delta_from_500_ft_m"] >= -.001 for o in observations),
            "sample_precision_m": .001, "samples": observations,
            "between_sample_gap": "unresolved", "conditions_permit_judgment": "unresolved",
            "safe_occupancy_judgment": "unresolved", "legal_conclusion": "unresolved"}
