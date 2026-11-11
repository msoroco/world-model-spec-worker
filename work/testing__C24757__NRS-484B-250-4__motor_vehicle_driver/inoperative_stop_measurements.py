"""Observe inoperative-signal stop and priority history without legal verdicts."""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED = ("vehicle_signal_history.jsonl", "video_frames.jsonl", "junction_context.json")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite numeric source")
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _body_inside(actor, polygon):
    vertices = actor.get("body_vertices_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Missing complete vehicle body")
    body = MultiPoint([(_number(v[0]), _number(v[1])) for v in vertices]).convex_hull
    return body.intersects(polygon)


def analyze(root: Path) -> dict:
    root = Path(root)
    hashes = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "junction_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "native_signal_id",
                "signal_head_video_source", "lane_governance_source", "stop_line_source"):
        if not context.get(key):
            raise ValueError("Missing sourced junction context: " + key)
    if context.get("installed_uncovered_vehicular_heads") is not True:
        raise ValueError("Uncovered vehicular heads not sourced")
    if context.get("stop_line_exists") is not True:
        raise ValueError("This stop-line branch requires a sourced marked line")
    vertices = context.get("intersection_polygon_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise ValueError("Missing intersection polygon")
    polygon = Polygon([(_number(v[0]), _number(v[1])) for v in vertices])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid intersection polygon")
    history, frames = _rows(root / "vehicle_signal_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(history) < 3 or len(history) != len(frames):
        raise ValueError("Incomplete stopped-vehicle history")
    previous = (-1, -math.inf)
    first_stop, first_entry = {"ego": None, "other": None}, {"ego": None, "other": None}
    prior_inside = {"ego": False, "other": False}
    samples = []
    for index, (row, frame) in enumerate(zip(history, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"))
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        if row.get("native_signal_id") != context["native_signal_id"] or row.get("signal_state") != "Off":
            raise ValueError("No observed Off state on identified signal")
        sample = {"frame": fid, "time_s": time, "signal_state": "Off"}
        for who in ("ego", "other"):
            actor = row.get(who)
            if not isinstance(actor, dict) or actor.get("intersection_id") != context["intersection_id"]:
                raise ValueError("Vehicle on wrong junction")
            speed = _number(actor.get("speed_mps"))
            signed = _number(actor.get("front_to_stop_line_signed_m"))
            inside = _body_inside(actor, polygon)
            if index == 0 and inside:
                raise ValueError("No pre-entry approach observation")
            if speed == 0 and signed >= 0 and first_stop[who] is None:
                first_stop[who] = {"frame": fid, "time_s": time, "front_to_stop_line_signed_m": signed}
            if inside and not prior_inside[who] and first_entry[who] is None:
                first_entry[who] = {"frame": fid, "time_s": time}
            prior_inside[who] = inside
            sample[who] = {"speed_mps": speed, "front_to_stop_line_signed_m": signed,
                           "body_in_intersection": inside}
        samples.append(sample)
    return {"format": "worker-inoperative-signal-stop-history", "sources": hashes,
            "intersection_id": context["intersection_id"],
            "first_full_halt_before_or_at_line": first_stop,
            "first_body_entry": first_entry,
            "ego_stopped_before_entry_observed": bool(first_stop["ego"] and first_entry["ego"] and first_stop["ego"]["time_s"] < first_entry["ego"]["time_s"]),
            "other_completed_stop_before_ego_observed": bool(first_stop["other"] and first_stop["ego"] and first_stop["other"]["time_s"] < first_stop["ego"]["time_s"]),
            "samples": samples,
            "cautious_proceeding_judgment": "unresolved", "yield_judgment": "unresolved",
            "statutory_inoperative_judgment": "unresolved; Native Off and source declarations require physical review"}
