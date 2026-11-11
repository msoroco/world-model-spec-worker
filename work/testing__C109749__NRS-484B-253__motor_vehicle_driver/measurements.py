"""Source-bound left-turn interaction measurements for NRS 484B.253.

No time-to-conflict value in this module is a legal definition of immediate
hazard. The output preserves quantities for later human review.
"""

import hashlib
import json
import math
from pathlib import Path


REQUIRED = ("intersection_geometry.json", "interaction_history.jsonl", "video_frames.jsonl")


def _read_required(root: Path, name: str) -> tuple[Path, str]:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_pair(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
        not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x)
        for x in value
    ):
        raise ValueError("Invalid " + label)
    return value


def _inside(point, polygon):
    # Even-odd crossing rule; a point on the edge is recorded as inside.
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        ax, ay = a
        bx, by = b
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if abs(cross) <= 1e-9 and min(ax, bx) - 1e-9 <= x <= max(ax, bx) + 1e-9 and min(ay, by) - 1e-9 <= y <= max(ay, by) + 1e-9:
            return True
        if (ay > y) != (by > y):
            at_x = ax + (y - ay) * (bx - ax) / (by - ay)
            if x < at_x:
                inside = not inside
    return inside


def _body_intersects(body, polygon):
    if not isinstance(body, list) or len(body) < 4:
        raise ValueError("Missing participant body geometry")
    points = [_finite_pair(p, "body vertex") for p in body]
    from shapely.geometry import MultiPoint, Polygon
    return MultiPoint(points).convex_hull.intersects(Polygon(polygon))


def _first_frame(rows, predicate):
    return next((r["frame"] for r in rows if predicate(r)), None)


def analyze(root: Path) -> dict:
    root = Path(root)
    sources = {}
    for name in REQUIRED:
        path, digest = _read_required(root, name)
        sources[name] = digest
    context = json.loads((root / REQUIRED[0]).read_text())
    polygon = context.get("intersection_polygon_xy_m")
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("Intersection polygon missing")
    polygon = [_finite_pair(v, "intersection polygon vertex") for v in polygon]
    conflict = _finite_pair(context.get("conflict_point_xy_m"), "conflict point")
    approaching = _finite_pair(context.get("oncoming_direction_xy"), "oncoming direction")
    norm = math.hypot(*approaching)
    if abs(norm - 1) > 1e-4:
        raise ValueError("Oncoming direction must be unit length")
    if context.get("ego_intended_maneuver") != "left_turn":
        raise ValueError("Sourced left-turn intention missing")
    rows = []
    for line in (root / REQUIRED[1]).read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if len(rows) < 2:
        raise ValueError("At least two interaction samples required")
    frame_map = [json.loads(line) for line in (root / REQUIRED[2]).read_text().splitlines() if line.strip()]
    if len(frame_map) != len(rows):
        raise ValueError("Original frame map/sample count mismatch")
    previous_frame = -1
    previous_time = -math.inf
    for index, row in enumerate(rows):
        frame, time = row.get("frame"), row.get("time_s")
        if type(frame) is not int or frame <= previous_frame or not isinstance(time, (int, float)) or isinstance(time, bool) or not math.isfinite(time) or time <= previous_time:
            raise ValueError("Nonmonotone frame/time source")
        previous_frame, previous_time = frame, time
        mapping = frame_map[index]
        if mapping.get("video_frame") != index or mapping.get("carla_frame") != frame or abs(mapping.get("time_s", -math.inf) - time) > 1e-4:
            raise ValueError("Original frame/time join failed")
        for who in ("ego", "oncoming"):
            actor = row.get(who)
            if not isinstance(actor, dict):
                raise ValueError("Missing participant: " + who)
            _finite_pair(actor.get("position_xy_m"), who + " position")
            _finite_pair(actor.get("velocity_xy_mps"), who + " velocity")
            _body_intersects(actor.get("body_vertices_xy_m"), polygon)
        if type(row.get("ego_left_indicator")) is not bool:
            raise ValueError("Missing measured left-indicator state")

    ego_inside = [r["frame"] for r in rows if _body_intersects(r["ego"]["body_vertices_xy_m"], polygon)]
    oncoming_inside = [r["frame"] for r in rows if _body_intersects(r["oncoming"]["body_vertices_xy_m"], polygon)]
    conflict_samples = []
    for row in rows:
        position = row["oncoming"]["position_xy_m"]
        velocity = row["oncoming"]["velocity_xy_mps"]
        remaining = sum((conflict[i] - position[i]) * approaching[i] for i in (0, 1))
        closing = sum(velocity[i] * approaching[i] for i in (0, 1))
        conflict_samples.append({
            "frame": row["frame"],
            "remaining_distance_m": remaining,
            "closing_speed_mps": closing,
            "kinematic_time_to_conflict_s": remaining / closing if remaining >= 0 and closing > 0 else None,
        })
    return {
        "format": "worker-left-turn-measurements",
        "sources": sources,
        "ego_first_in_intersection_frame": ego_inside[0] if ego_inside else None,
        "oncoming_first_in_intersection_frame": oncoming_inside[0] if oncoming_inside else None,
        "oncoming_presence_frames": oncoming_inside,
        "ego_low_speed_frames": [r["frame"] for r in rows if math.hypot(*r["ego"]["velocity_xy_mps"]) < 0.1],
        "ego_left_indicator_frames": [r["frame"] for r in rows if r["ego_left_indicator"]],
        "opposing_conflict_samples": conflict_samples,
        "judgment_unresolved": "immediate hazard and right-of-way unresolved; no numeric legal cutoff asserted",
    }
