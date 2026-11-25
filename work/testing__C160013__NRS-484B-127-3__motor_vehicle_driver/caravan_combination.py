"""Measure a sourced drawing-and-drawn pair on original caravan frames.

This diagnostic requires two real actor bodies and a reviewed relationship
source. It does not infer towing from proximity or declare a legal gap.
"""
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


def _polygon(record):
    points = record.get("body_vertices_xy_m")
    if not isinstance(points, list) or len(points) < 4:
        raise ValueError("Complete original body required")
    if any(not isinstance(p, list) or len(p) != 2 or
           any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
           for p in points):
        raise ValueError("Finite original body vertices required")
    polygon = MultiPoint(points).convex_hull
    if polygon.area <= 0:
        raise ValueError("Degenerate original body")
    return polygon


def analyze(root, *, drawing_actor_id, drawn_actor_id):
    root = Path(root).resolve()
    if type(drawing_actor_id) is not int or type(drawn_actor_id) is not int or drawing_actor_id == drawn_actor_id:
        raise ValueError("Distinct original drawing and drawn actor IDs required")
    context_path = root / "road_context.json"
    history_path = root / "caravan_history.jsonl"
    map_path = root / "video_frames.jsonl"
    for path in (context_path, history_path, map_path):
        if not path.is_file():
            raise ValueError("Original combination source missing: " + path.name)
    context = json.loads(context_path.read_text(encoding="utf-8"))
    ref = context.get("towing_relationship_source")
    if not isinstance(ref, dict) or ref.get("review_status") != "reviewed_native_relationship":
        raise ValueError("Reviewed original towing relationship source required")
    rel = Path(ref.get("path", ""))
    if not rel.parts or rel.is_absolute() or ".." in rel.parts or rel == Path("."):
        raise ValueError("Unsafe towing relationship source")
    source = (root / rel).resolve()
    if not source.is_relative_to(root) or not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Original towing relationship source missing")
    source_data = source.read_bytes()
    source_data.decode("utf-8")
    source_hash = hashlib.sha256(source_data).hexdigest()
    if source_hash != ref.get("sha256"):
        raise ValueError("Changed original towing relationship source")
    relationship = json.loads(source_data)
    if relationship.get("drawing_actor_id") != drawing_actor_id or relationship.get("drawn_actor_id") != drawn_actor_id:
        raise ValueError("Original towing relationship identity mismatch")
    if relationship.get("drawn_unit_has_motive_power") is not False:
        raise ValueError("Drawn unit must lack motive power")
    forward = context.get("road_forward_xy")
    if not isinstance(forward, list) or len(forward) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in forward):
        raise ValueError("Original road direction required")
    magnitude = math.hypot(*forward)
    if magnitude <= 0:
        raise ValueError("Nonzero road direction required")
    ux, uy = forward[0] / magnitude, forward[1] / magnitude
    rows = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines() if line]
    frames = [json.loads(line) for line in map_path.read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != len(frames):
        raise ValueError("Complete original combination frame join required")
    samples = []
    previous = None
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time_s = row.get("frame"), row.get("time_s")
        if type(fid) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError("Original combination frame identity required")
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time_s:
            raise ValueError("Original combination frame join failed")
        if row.get("towing_relationship") != {"drawing_actor_id": drawing_actor_id,
                                               "drawn_actor_id": drawn_actor_id}:
            raise ValueError("Original per-frame towing relationship mismatch")
        if previous is not None and (fid != previous[0] + 1 or abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError("Original combination 20 Hz cadence required")
        previous = fid, time_s
        members = row.get("caravan_members")
        if not isinstance(members, list) or len(members) < 3:
            raise ValueError("Three caravan members required")
        actors = members + [row.get("entering_vehicle")]
        actors += row.get("drawn_units", [])
        if any(not isinstance(actor, dict) for actor in actors):
            raise ValueError("Original actor record required")
        ids = [actor.get("actor_id") for actor in actors]
        if len(ids) != len(set(ids)):
            raise ValueError("Distinct original actor identities required")
        by_id = {actor["actor_id"]: actor for actor in actors}
        if drawing_actor_id not in by_id or drawn_actor_id not in by_id:
            raise ValueError("Original towing pair missing from frame")
        drawing = _polygon(by_id[drawing_actor_id])
        drawn = _polygon(by_id[drawn_actor_id])
        if drawing.intersects(drawn):
            raise ValueError("Original drawing and drawn bodies intersect")
        if (drawing.centroid.x - drawn.centroid.x) * ux + (drawing.centroid.y - drawn.centroid.y) * uy <= 0:
            raise ValueError("Drawn unit must follow drawing vehicle")
        hull = MultiPoint(list(drawing.exterior.coords) + list(drawn.exterior.coords)).convex_hull
        projected = [x * ux + y * uy for x, y in hull.exterior.coords]
        front_edge = max(projected)
        following = []
        for member in members:
            if member["actor_id"] in (drawing_actor_id, drawn_actor_id):
                continue
            member_poly = _polygon(member)
            member_rear = min(x * ux + y * uy for x, y in member_poly.exterior.coords)
            if member_rear >= front_edge:
                following.append((member_rear, member["actor_id"]))
        if not following:
            raise ValueError("Following caravan member missing")
        following_rear, following_id = min(following)
        samples.append({"frame": fid, "time_s": time_s, "combination_front_m": max(projected),
                        "combination_rear_m": min(projected), "combination_length_m": max(projected) - min(projected),
                        "drawbar_clearance_m": drawing.distance(drawn),
                        "following_actor_id": following_id,
                        "following_gap_opening_m": following_rear - front_edge})
    return {"format": "worker-original-combination-observations", "drawing_actor_id": drawing_actor_id,
            "drawn_actor_id": drawn_actor_id, "towing_relationship_source_sha256": source_hash,
            "original_source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                       for path in (context_path, history_path, map_path)},
            "samples": samples, "physical_acceptance_claimed": False,
            "without_danger_judgment": "unresolved"}
