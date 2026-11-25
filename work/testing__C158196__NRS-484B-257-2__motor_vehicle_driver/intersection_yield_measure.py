"""Saved-source observations for the signed-entrance and hazard branches.

The input rows are original capture measurements. This module does not decide
whether a separation is an immediate hazard or whether conduct was cautious.
"""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


SOURCES = ("entrance_inventory.json", "crossing_history.jsonl", "video_frames.jsonl")
DEVICES = {"stop", "yield", "none"}


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + name)
    return float(value)


def _read_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) < 3:
        raise ValueError("Incomplete original crossing history")
    return rows


def analyze(root: Path) -> dict:
    root = Path(root)
    hashes = {}
    for name in SOURCES:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    inventory = json.loads((root / SOURCES[0]).read_text())
    if inventory.get("non_through_highway") is not True:
        raise ValueError("Non-through intersection source missing")
    if inventory.get("all_entrances_inventoried") is not True:
        raise ValueError("All entrance signs must be inventoried")
    entrances = inventory.get("entrances")
    if not isinstance(entrances, list) or len(entrances) < 2:
        raise ValueError("Missing multiple intersection entrances")
    by_lane = {}
    for entrance in entrances:
        lane = entrance.get("lane_key")
        device = entrance.get("device")
        if not isinstance(lane, str) or not lane or lane in by_lane:
            raise ValueError("Missing or duplicate entrance lane")
        if device not in DEVICES or not entrance.get("device_source"):
            raise ValueError("Unsourced entrance device")
        by_lane[lane] = device
    ego_lane = inventory.get("ego_lane_key")
    other_lane = inventory.get("other_lane_key")
    if by_lane.get(ego_lane) not in {"stop", "yield"}:
        raise ValueError("Ego entrance is not signed")
    if by_lane.get(other_lane) != "none":
        raise ValueError("Other vehicle is not established as non-obligated")
    if (not inventory.get("intersection_boundary_source") or
            not inventory.get("conflict_point_source") or
            not inventory.get("complete_body_observation_source")):
        raise ValueError("Intersection geometry is unsourced")
    polygon_points = inventory.get("intersection_polygon_xy_m", [])
    polygon = Polygon(polygon_points) if isinstance(polygon_points, list) and len(polygon_points) >= 3 else Polygon()
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid intersection polygon")

    history = _read_rows(root / SOURCES[1])
    frames = _read_rows(root / SOURCES[2])
    if len(history) != len(frames):
        raise ValueError("Original frame count mismatch")
    samples = []
    previous = (-1, -math.inf)
    first_entry = None
    for index, (row, frame) in enumerate(zip(history, frames)):
        fid = row.get("frame")
        time = _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone crossing history")
        previous = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original frame join failed")
        if row.get("ego_lane_key") != ego_lane or row.get("other_lane_key") != other_lane:
            raise ValueError("Entrance identity changed")
        bodies = []
        for party in ("ego", "other"):
            vertices = row.get(party + "_body_vertices_xy_m")
            if not isinstance(vertices, list) or len(vertices) < 4:
                raise ValueError("Missing complete " + party + " body")
            points = []
            for vertex in vertices:
                if not isinstance(vertex, (list, tuple)) or len(vertex) != 2:
                    raise ValueError("Malformed " + party + " body vertex")
                points.append((_finite(vertex[0], party + " body x"),
                               _finite(vertex[1], party + " body y")))
            body = MultiPoint(points).convex_hull
            if body.geom_type != "Polygon" or body.area <= 0:
                raise ValueError("Degenerate " + party + " body")
            bodies.append(body)
        ego_inside, other_inside = (body.intersects(polygon) for body in bodies)
        controls = row.get("signal_controls_ego")
        if type(controls) is not bool:
            raise ValueError("Missing original signal observation")
        state = row.get("signal_state")
        if state not in {"Red", "Yellow", "Green", "Off"}:
            raise ValueError("Missing original signal state")
        ego_speed = _finite(row.get("ego_speed_mps"), "ego speed")
        other_speed = _finite(row.get("other_speed_mps"), "other speed")
        ego_distance = _finite(row.get("ego_distance_to_conflict_m"), "ego conflict distance")
        other_distance = _finite(row.get("other_distance_to_conflict_m"), "other conflict distance")
        if min(ego_speed, other_speed, ego_distance, other_distance) < 0:
            raise ValueError("Negative motion measurement")
        if index == 0 and ego_inside:
            raise ValueError("Missing pre-entry approach")
        ego_ttc = ego_distance / ego_speed if ego_speed > 0 else None
        other_ttc = other_distance / other_speed if other_speed > 0 else None
        sample = {"frame": fid, "time_s": time, "ego_body_in_intersection": ego_inside,
                  "other_body_in_intersection": other_inside, "signal_state": state,
                  "signal_controls_ego": controls, "ego_speed_mps": ego_speed,
                  "other_speed_mps": other_speed, "ego_time_to_conflict_s": ego_ttc,
                  "other_time_to_conflict_s": other_ttc,
                  "time_to_conflict_difference_s": abs(ego_ttc - other_ttc)
                  if ego_ttc is not None and other_ttc is not None else None}
        samples.append(sample)
        if ego_inside and first_entry is None:
            first_entry = sample
    if first_entry is None:
        raise ValueError("No observed ego entry")
    before_entry = [row for row in samples if row["time_s"] < first_entry["time_s"]]
    stopped_before_entry = any(row["ego_speed_mps"] == 0 for row in before_entry)
    active_control = first_entry["signal_controls_ego"] and first_entry["signal_state"] != "Off"
    return {"format": "worker-signed-entrance-yield-observations", "sources": hashes,
            "ego_entrance_device": by_lane[ego_lane], "other_entrance_device": by_lane[other_lane],
            "first_ego_entry_frame": first_entry["frame"],
            "stopped_before_entry_observed": stopped_before_entry,
            "other_inside_at_ego_entry": first_entry["other_body_in_intersection"],
            "operative_signal_controls_ego_at_entry_observed": active_control,
            "signed_duty_candidate": not active_control,
            "samples": samples, "immediate_hazard_judgment": "unresolved",
            "cautious_proceeding_judgment": "unresolved", "legal_conclusion": "unresolved"}
