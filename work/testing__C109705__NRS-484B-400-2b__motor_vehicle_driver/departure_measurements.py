"""Measure a complete body's left-turn exit right of the destination centerline.

Source files are retained original-frame inputs. This is a geometric observation,
not a legal conclusion or a substitute for camera review of map references.
"""
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import LineString, MultiPoint, Point, Polygon

REQUIRED = ("road_context.json", "turn_history.jsonl", "video_frames.jsonl")


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _points(values, label, minimum):
    if not isinstance(values, list) or len(values) < minimum:
        raise ValueError("Missing " + label)
    result = []
    for value in values:
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("Invalid " + label)
        result.append((_finite(value[0], label + " x"), _finite(value[1], label + " y")))
    return result


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path) -> dict:
    root = Path(root)
    hashes = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    ctx = json.loads((root / "road_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "approach_road_id", "outgoing_road_id",
                "opposing_lane_source", "destination_centerline_source", "destination_right_half_source",
                "junction_source", "left_turn_route_source"):
        if ctx.get(key) is None:
            raise ValueError("Missing sourced road context: " + key)
    if ctx.get("both_highways_two_directional") is not True or ctx.get("intended_turn") != "left":
        raise ValueError("Two-directional left-turn activation not sourced")
    centerline = LineString(_points(ctx.get("destination_centerline_xy_m"), "destination centerline", 2))
    right_half = Polygon(_points(ctx.get("destination_right_half_polygon_xy_m"), "destination right half", 3))
    junction = Polygon(_points(ctx.get("junction_polygon_xy_m"), "junction", 3))
    if centerline.length <= 0 or not right_half.is_valid or right_half.area <= 0 or not junction.is_valid or junction.area <= 0:
        raise ValueError("Invalid road reference geometry")
    rows, frames = _rows(root / "turn_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete turn/frame history")
    samples = []
    previous = (-1, -math.inf)
    entered = False
    exited = False
    for i, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = fid, time
        if frame.get("video_frame") != i or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original frame join failed")
        body = MultiPoint(_points(row.get("ego_body_vertices_xy_m"), "ego body", 4)).convex_hull
        if body.area <= 0:
            raise ValueError("Degenerate vehicle body")
        intersects = body.intersects(junction)
        if intersects:
            entered = True
        if entered and not intersects and not exited:
            if row.get("road_id") != ctx["outgoing_road_id"]:
                raise ValueError("Exit is not on sourced destination road")
            exited = True
            samples.append({"frame": fid, "time_s": time, "road_id": row["road_id"],
                            "complete_body_right_of_destination_centerline": right_half.covers(body) and not body.intersects(centerline),
                            "body_in_destination_right_half": right_half.covers(body),
                            "body_intersects_centerline": body.intersects(centerline),
                            "body_centroid_distance_to_centerline_m": centerline.distance(body.centroid),
                            "minimum_vertex_distance_to_centerline_m": min(centerline.distance(Point(p)) for p in _points(row["ego_body_vertices_xy_m"], "ego body", 4))})
    if not entered or not exited:
        raise ValueError("No observed intersection entry then complete-body exit")
    return {"format": "worker-left-turn-destination-exit-observations", "sources": hashes,
            "native_road_context": ctx, "exit_sample": samples[0],
            "legal_conclusion": "unresolved pending source geometry and physical review"}
