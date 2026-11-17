"""Original Native heavy-vehicle footprint and marked-lane source capture.

The caller supplies a source-hashed three-lane survey. This module records
measured geometry without deciding lane containment or either legal exception.
"""

from __future__ import annotations

import hashlib
import json
from math import atan2, isfinite
from pathlib import Path


def _xy(value):
    point = (float(value.x), float(value.y))
    if not all(isfinite(v) for v in point):
        raise ValueError("Nonfinite Native position")
    return point


def _body(actor):
    vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
    if len(vertices) != 8 or any(not isfinite(float(v.z)) for v in vertices):
        raise ValueError("Heavy component needs eight finite body vertices")
    lower = sorted(vertices, key=lambda v: float(v.z))[:4]
    points = [_xy(v) for v in lower]
    if len(set(points)) != 4:
        raise ValueError("Degenerate heavy component footprint")
    center = (sum(p[0] for p in points) / 4, sum(p[1] for p in points) / 4)
    points.sort(key=lambda p: atan2(p[1] - center[1], p[0] - center[0]))
    return [list(p) for p in points]


def _lane(waypoint):
    width = float(waypoint.lane_width)
    if not isfinite(width) or width <= 0:
        raise ValueError("Invalid Native lane width")
    left = getattr(waypoint, "left_lane_marking", None)
    right = getattr(waypoint, "right_lane_marking", None)
    if left is None or right is None:
        raise ValueError("Missing Native lane marking")
    types = [str(left.type), str(right.type)]
    if any(t.rsplit(".", 1)[-1].lower() == "none" for t in types):
        raise ValueError("Unmarked Native lane")
    center = _xy(waypoint.transform.location)
    forward = _xy(waypoint.transform.get_forward_vector())
    norm = (forward[0] ** 2 + forward[1] ** 2) ** 0.5
    if norm == 0:
        raise ValueError("Zero Native lane heading")
    heading = [forward[0] / norm, forward[1] / norm]
    return {"road_id": int(waypoint.road_id), "lane_id": int(waypoint.lane_id),
            "width_m": width, "center_xy_m": list(center),
            "heading_xy": heading, "left_marking": types[0],
            "right_marking": types[1]}


def _survey(path, expected_sha256):
    source = Path(path)
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("Three-lane survey source hash changed")
    survey = json.loads(data)
    lanes = survey.get("lanes")
    if not isinstance(lanes, list) or len(lanes) != 3:
        raise ValueError("Source survey must enumerate three governed lanes")
    identities = set()
    for lane in lanes:
        identity = (lane.get("road_id"), lane.get("lane_id"))
        if None in identity or identity in identities or not lane.get("direction"):
            raise ValueError("Survey lane identity or directional allocation missing")
        identities.add(identity)
        if not lane.get("left_marking") or not lane.get("right_marking"):
            raise ValueError("Survey marked boundary missing")
    return survey


def select_three_lane_site(native_map, *, spacing_m=2.0):
    """Select and inventory one exact three-lane Native road cross section.

    This is a CPU-testable site proposal. The GPU run must remeasure the actual
    chosen route and preserve the emitted survey as an original source.
    """
    if not isfinite(spacing_m) or spacing_m <= 0:
        raise ValueError("Invalid Native route survey spacing")
    samples = sorted(native_map.generate_waypoints(spacing_m),
                     key=lambda wp: (int(wp.road_id), int(wp.lane_id),
                                     float(getattr(wp, "s", 0))))
    for origin in samples:
        road_id = int(origin.road_id)
        queue = [origin]
        lanes = {}
        while queue:
            waypoint = queue.pop(0)
            if waypoint is None or int(waypoint.road_id) != road_id:
                continue
            if str(waypoint.lane_type).rsplit(".", 1)[-1].lower() != "driving":
                continue
            lane_id = int(waypoint.lane_id)
            if lane_id in lanes:
                continue
            lanes[lane_id] = waypoint
            queue.extend((waypoint.get_left_lane(), waypoint.get_right_lane()))
        if len(lanes) != 3:
            continue
        try:
            geometry = [_lane(wp) for wp in lanes.values()]
        except ValueError:
            continue
        subject = _lane(origin)
        survey = {"native_map_name": str(native_map.name),
                  "route_road_id": road_id, "subject_lane_id": subject["lane_id"],
                  "spacing_m": spacing_m, "lanes": [
                      {"road_id": lane["road_id"], "lane_id": lane["lane_id"],
                       "direction": "forward" if sum(a * b for a, b in zip(
                           lane["heading_xy"], subject["heading_xy"])) > 0 else "opposing",
                       "left_marking": lane["left_marking"],
                       "right_marking": lane["right_marking"],
                       "width_m": lane["width_m"],
                       "heading_xy": lane["heading_xy"]}
                      for lane in sorted(geometry, key=lambda item: item["lane_id"])]}
        return origin, survey
    raise ValueError("No source-measured exact three-driving-lane road cross section")


def save_three_lane_survey(path, survey):
    """Materialize the selected site inventory and return its source hash."""
    target = Path(path)
    target.write_text(json.dumps(survey, indent=2, allow_nan=False) + "\n")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    _survey(target, digest)
    return digest


def measure_footprint(row):
    """Signed lateral clearances of every original body corner in its lane.

    A negative value means a measured corner lies beyond the local geometric
    lane boundary. It is not a statutory tolerance or legal classification.
    """
    lane = row["lane"]
    cx, cy = lane["center_xy_m"]
    fx, fy = lane["heading_xy"]
    width = float(lane["width_m"])
    if not isfinite(width) or width <= 0 or abs(fx * fx + fy * fy - 1) > 1e-6:
        raise ValueError("Invalid original lane geometry")
    bodies = row["heavy_vehicle_components"]
    if not bodies:
        raise ValueError("Missing original heavy body")
    measurements = []
    for body in bodies:
        corners = body["corners_xy_m"]
        if len(corners) != 4:
            raise ValueError("Incomplete original component footprint")
        lateral = []
        for x, y in corners:
            x, y = float(x), float(y)
            if not isfinite(x) or not isfinite(y):
                raise ValueError("Nonfinite original body corner")
            lateral.append((x - cx) * -fy + (y - cy) * fx)
        measurements.append({"actor_id": body["actor_id"],
                             "left_clearance_m": width / 2 - max(lateral),
                             "right_clearance_m": width / 2 + min(lateral)})
    return {"frame": row["frame"], "component_clearances": measurements,
            "minimum_clearance_m": min(min(m["left_clearance_m"],
                                           m["right_clearance_m"])
                                       for m in measurements)}


class HeavyLaneSourceRecorder:
    """One retained JSON row per original simulation tick, including all bodies."""

    def __init__(self, directory, ego_components, *, survey_path, survey_sha256,
                 overtaken=None):
        if not ego_components or any(a.id is None for a in ego_components):
            raise ValueError("Heavy vehicle body components required")
        ids = [int(a.id) for a in ego_components]
        if len(set(ids)) != len(ids) or overtaken is not None and (
                overtaken.id is None or int(overtaken.id) in ids):
            raise ValueError("Distinct Native body and participant IDs required")
        self.survey = _survey(survey_path, survey_sha256)
        self.survey_sha256 = survey_sha256
        self.ego_components = list(ego_components)
        self.overtaken = overtaken
        self.path = Path(directory) / "heavy_lane_sources.jsonl"
        self.stream = self.path.open("x", encoding="utf-8")
        self.previous = None

    def append(self, frame, time_s, waypoint):
        if type(frame) is not int or type(time_s) not in (int, float) or not isfinite(time_s):
            raise ValueError("Invalid Native frame or time")
        if self.previous is not None and (
                frame != self.previous[0] + 1 or time_s <= self.previous[1]):
            raise ValueError("Missing or unordered Native heavy-lane frame")
        lane = _lane(waypoint)
        if (lane["road_id"], lane["lane_id"]) not in {
                (x["road_id"], x["lane_id"]) for x in self.survey["lanes"]}:
            raise ValueError("Native lane is outside source-surveyed three-lane route")
        bodies = [{"actor_id": int(a.id), "corners_xy_m": _body(a),
                   "velocity_xy_mps": list(_xy(a.get_velocity()))}
                  for a in self.ego_components]
        row = {"frame": frame, "time_s": time_s, "survey_sha256": self.survey_sha256,
               "heavy_vehicle_components": bodies, "lane": lane,
               "overtaken": None}
        if self.overtaken is not None:
            row["overtaken"] = {"actor_id": int(self.overtaken.id),
                                 "corners_xy_m": _body(self.overtaken),
                                 "velocity_xy_mps": list(_xy(self.overtaken.get_velocity()))}
        self.stream.write(json.dumps(row, allow_nan=False) + "\n")
        self.stream.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
