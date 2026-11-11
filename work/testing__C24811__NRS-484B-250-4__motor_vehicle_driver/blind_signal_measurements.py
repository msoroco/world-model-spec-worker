"""Original-frame observations for a wholly inoperative signal and three vehicles.

Native Off, actual installed/uncovered status, and timing are retained separately;
this reports no legal conclusion about cautious proceeding or yielding.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED = ("junction_context.json", "vehicle_signal_history.jsonl", "video_frames.jsonl")


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _body(actor):
    vertices = actor.get("body_vertices_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Missing complete vehicle body")
    points = []
    for vertex in vertices:
        if not isinstance(vertex, list) or len(vertex) != 2:
            raise ValueError("Invalid body vertex")
        points.append((_number(vertex[0], "body x"), _number(vertex[1], "body y")))
    return MultiPoint(points).convex_hull


def analyze(root: Path):
    root = Path(root)
    hashes = {}
    for name in REQUIRED:
        path = root/name
        if not path.is_file():
            raise ValueError("Missing required original source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    ctx = json.loads((root/"junction_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "signal_head_video_source",
                "all_entrances_source", "stop_line_source", "occluder_geometry_source",
                "sight_ray_source"):
        if not ctx.get(key):
            raise ValueError("Missing sourced junction context: " + key)
    if ctx.get("stop_line_exists") is not True:
        raise ValueError("Selected stop-line branch lacks marked line")
    heads = ctx.get("signal_heads")
    if not isinstance(heads, list) or len(heads) < 2:
        raise ValueError("All governing signal heads required")
    ids = []
    for head in heads:
        if not head.get("native_id") or not head.get("entrance_id") or head.get("installed") is not True or head.get("uncovered") is not True:
            raise ValueError("Installed uncovered head identity missing")
        ids.append(head["native_id"])
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate governing signal head")
    polygon = Polygon(ctx.get("intersection_polygon_xy_m", []))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid intersection polygon")
    history, frames = _rows(root/"vehicle_signal_history.jsonl"), _rows(root/"video_frames.jsonl")
    if len(history) < 4 or len(history) != len(frames):
        raise ValueError("Incomplete three-vehicle history")
    samples, previous = [], (-1, -math.inf)
    first_stop = {role: None for role in ("ego", "earlier", "occupant")}
    first_entry = {role: None for role in first_stop}
    for i, (row, frame) in enumerate(zip(history, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = fid, time
        if frame.get("video_frame") != i or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original frame join failed")
        states = row.get("signal_states")
        if not isinstance(states, dict) or set(states) != {str(v) for v in ids} or any(v != "Off" for v in states.values()):
            raise ValueError("All governing heads must be observed Off at every original frame")
        sample = {"frame": fid, "time_s": time, "all_heads_off": True}
        for role in first_stop:
            actor = row.get(role)
            if not isinstance(actor, dict) or actor.get("intersection_id") != ctx["intersection_id"]:
                raise ValueError("Participant junction mismatch: " + role)
            speed = _number(actor.get("speed_mps"), "speed")
            signed = _number(actor.get("front_to_stop_line_signed_m"), "stop-line distance")
            if speed < 0:
                raise ValueError("Negative speed")
            inside = _body(actor).intersects(polygon)
            if i == 0 and inside:
                raise ValueError("Missing pre-entry history")
            if speed == 0 and signed >= 0 and first_stop[role] is None:
                first_stop[role] = {"frame": fid, "time_s": time}
            if inside and first_entry[role] is None:
                first_entry[role] = {"frame": fid, "time_s": time}
            sample[role] = {"speed_mps": speed, "front_to_stop_line_signed_m": signed,
                            "body_in_intersection": inside}
        samples.append(sample)
    def before(a, b):
        return bool(a and b and a["time_s"] < b["time_s"])
    ego_stop_before_entry = before(first_stop["ego"], first_entry["ego"])
    earlier_stop_precedes_ego = before(first_stop["earlier"], first_stop["ego"])
    occupant_inside_at_ego_entry = bool(first_entry["ego"] and any(
        s["frame"] == first_entry["ego"]["frame"] and s["occupant"]["body_in_intersection"]
        for s in samples))
    return {"format": "worker-blind-inoperative-signal-observations", "sources": hashes,
            "signal_head_ids": ids, "first_full_halt": first_stop, "first_body_entry": first_entry,
            "ego_stopped_before_entry_observed": ego_stop_before_entry,
            "distinct_other_stopped_earlier_observed": earlier_stop_precedes_ego,
            "distinct_occupant_inside_at_ego_entry_observed": occupant_inside_at_ego_entry,
            "samples": samples, "cautious_proceeding_judgment": "unresolved",
            "yield_judgment": "unresolved", "legal_conclusion": "unresolved"}
