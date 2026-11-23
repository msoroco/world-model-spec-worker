"""Portable original-tick adapter for the C158208 nearest-view branch.

The Native runner must supply raw actor vertices, velocity, snapshot time and a
retained visibility probe. This adapter computes the engineering measurements
from those values and seals them; it does not infer statutory right of way.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _point(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} must be an XY point")
    return [_number(value[0], label), _number(value[1], label)]


def _vertices(value, label):
    if not isinstance(value, list) or len(value) < 4:
        raise ValueError(f"{label} requires at least four body vertices")
    return [_point(p, label) for p in value]


def _project(point, origin, axis):
    return (point[0] - origin[0]) * axis[0] + (point[1] - origin[1]) * axis[1]


def validate_geometry(geometry):
    ego_origin = _point(geometry["ego_route_origin_xy_m"], "ego route origin")
    ego_axis = _point(geometry["ego_route_axis_xy"], "ego route axis")
    through_origin = _point(geometry["through_route_origin_xy_m"], "through route origin")
    through_axis = _point(geometry["through_route_axis_xy"], "through route axis")
    for axis in (ego_axis, through_axis):
        if abs(math.hypot(*axis) - 1.0) > 1e-4:
            raise ValueError("route axis must be a unit direction")
    entry = _number(geometry["ego_entry_station_m"], "ego entry station")
    polygon = _vertices(geometry["intersection_polygon_xy_m"], "intersection polygon")
    from shapely.geometry import Polygon
    shape = Polygon(polygon)
    if not shape.is_valid or shape.area <= 0:
        raise ValueError("intersection polygon must be nondegenerate")
    return ego_origin, ego_axis, through_origin, through_axis, entry, polygon


def derive(raw, geometry):
    ego_origin, ego_axis, through_origin, through_axis, entry, polygon = validate_geometry(geometry)
    frame = raw.get("frame")
    if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
        raise ValueError("original frame must be a nonnegative integer")
    time = _number(raw["time_s"], "time_s")
    ego = raw["ego"]
    through = raw["through_vehicle"]
    ego_body = _vertices(ego["body_vertices_xy_m"], "ego body")
    through_body = _vertices(through["body_vertices_xy_m"], "through body")
    through_center = _point(through["center_xy_m"], "through center")
    velocity = _point(ego["velocity_xy_mps"], "ego velocity")
    probe = raw["visibility_probe"]
    if probe.get("source") != "native_raycast" or not isinstance(probe.get("occluded"), bool):
        raise ValueError("retained Native visibility probe required")
    _point(probe["origin_xy_m"], "visibility origin")
    _point(probe["target_xy_m"], "visibility target")
    if not isinstance(raw.get("sign_present"), bool) or not raw["sign_present"]:
        raise ValueError("original governing sign observation required")
    from shapely.geometry import Polygon
    ego_shape = Polygon(ego_body)
    through_shape = Polygon(through_body)
    if not ego_shape.is_valid or ego_shape.area <= 0 or not through_shape.is_valid or through_shape.area <= 0:
        raise ValueError("original body polygons must be valid")
    occupied = through_shape.intersects(Polygon(polygon))
    front_station = max(_project(vertex, ego_origin, ego_axis) for vertex in ego_body)
    return {"frame": frame, "time_s": time,
            "ego_speed_mps": math.hypot(*velocity),
            "ego_front_station_m": front_station,
            "through_center_station_m": _project(through_center, through_origin, through_axis),
            "through_traffic_visible": not probe["occluded"],
            "intersection_entry": front_station >= entry,
            "through_vehicle_within_intersection": occupied,
            "original": raw}


class TickCapture:
    def __init__(self, attempt: Path, geometry: dict, reviewed_context: dict):
        self.attempt = Path(attempt).resolve()
        if "runtime" in self.attempt.parts:
            raise ValueError("capture output cannot be under frozen runtime")
        self.attempt.mkdir(parents=True, exist_ok=True)
        self.path = self.attempt / "nearest-view-original-ticks.jsonl"
        self.packet_path = self.attempt / "nearest-view-saved-packet.json"
        self.seal_path = self.attempt / "nearest-view-tick-seal.json"
        if any(p.exists() for p in (self.path, self.packet_path, self.seal_path)):
            raise ValueError("original attempt already used")
        validate_geometry(geometry)
        self.geometry = geometry
        self.context = reviewed_context
        self.rows = []
        self.closed = False

    def append(self, raw):
        if self.closed:
            raise ValueError("original tick capture closed")
        row = derive(raw, self.geometry)
        if self.rows:
            previous = self.rows[-1]
            if row["frame"] != previous["frame"] + 1:
                raise ValueError("original frames must be contiguous")
            if not 0.049 <= row["time_s"] - previous["time_s"] <= 0.051:
                raise ValueError("original tick time must be 20 Hz")
        self.rows.append(row)
        return row

    def close(self):
        if self.closed or len(self.rows) < 3:
            raise ValueError("capture cannot seal without three original ticks")
        self.closed = True
        raw_lines = "".join(json.dumps(row["original"], sort_keys=True) + "\n" for row in self.rows)
        self.path.write_text(raw_lines, encoding="utf-8")
        samples = [{key: value for key, value in row.items() if key != "original"} for row in self.rows]
        packet = {"reviewed_context": self.context, "samples": samples,
                  "geometry": self.geometry,
                  "original_ticks": {"path": self.path.name,
                                     "sha256": hashlib.sha256(raw_lines.encode()).hexdigest()}}
        packet_raw = json.dumps(packet, indent=2, sort_keys=True) + "\n"
        self.packet_path.write_text(packet_raw, encoding="utf-8")
        seal = {"format": "c158208-nearest-view-tick-seal-v1", "rate_hz": 20,
                "frame_count": len(samples), "first_frame": samples[0]["frame"],
                "last_frame": samples[-1]["frame"],
                "packet_sha256": hashlib.sha256(packet_raw.encode()).hexdigest(),
                "raw_ticks_sha256": packet["original_ticks"]["sha256"]}
        self.seal_path.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return seal


def verify_seal(attempt: Path) -> dict:
    """Rebuild every saved sample from sealed original ticks before analysis."""
    attempt = Path(attempt)
    raw_path = attempt / "nearest-view-original-ticks.jsonl"
    packet_path = attempt / "nearest-view-saved-packet.json"
    seal_path = attempt / "nearest-view-tick-seal.json"
    raw_bytes = raw_path.read_bytes()
    packet_bytes = packet_path.read_bytes()
    packet = json.loads(packet_bytes)
    seal = json.loads(seal_path.read_bytes())
    if seal.get("format") != "c158208-nearest-view-tick-seal-v1" or seal.get("rate_hz") != 20:
        raise ValueError("tick seal format or rate differs")
    if hashlib.sha256(raw_bytes).hexdigest() != seal["raw_ticks_sha256"]:
        raise ValueError("original tick source hash differs")
    if hashlib.sha256(packet_bytes).hexdigest() != seal["packet_sha256"]:
        raise ValueError("saved packet source hash differs")
    if packet["original_ticks"]["path"] != raw_path.name or packet["original_ticks"]["sha256"] != seal["raw_ticks_sha256"]:
        raise ValueError("saved packet original source binding differs")
    raw_rows = [json.loads(line) for line in raw_bytes.splitlines() if line]
    if len(raw_rows) < 3:
        raise ValueError("sealed source has fewer than three original ticks")
    rebuilt = [{key: value for key, value in derive(raw, packet["geometry"]).items() if key != "original"}
               for raw in raw_rows]
    if rebuilt != packet["samples"] or len(rebuilt) != seal["frame_count"]:
        raise ValueError("saved samples differ from original tick derivation")
    if rebuilt[0]["frame"] != seal["first_frame"] or rebuilt[-1]["frame"] != seal["last_frame"]:
        raise ValueError("sealed frame endpoints differ")
    for earlier, later in zip(rebuilt, rebuilt[1:]):
        if later["frame"] != earlier["frame"] + 1 or not 0.049 <= later["time_s"] - earlier["time_s"] <= 0.051:
            raise ValueError("sealed frame/time continuity differs")
    return packet
