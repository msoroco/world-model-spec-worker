"""Require reviewed original island, map, routes and camera sources before Native use."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from island_measurements import ASSIGNMENT_ID, SUFFIXES, validate_map

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
              "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def route(points, role):
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError("reviewed original connected route requires three samples")
    for index, point in enumerate(points):
        if not isinstance(point, dict) or not all(
                type(point.get(key)) in (int, float) and math.isfinite(point[key])
                for key in ("x", "y", "speed_mps")):
            raise ValueError("finite original route sample required")
        if not 0 < point["speed_mps"] <= 20 or not point.get("lane_id"):
            raise ValueError("reviewed route speed and lane required")
        if index:
            previous = points[index - 1]
            distance = math.hypot(point["x"] - previous["x"], point["y"] - previous["y"])
            if not .15 <= distance <= 8:
                raise ValueError("reviewed route samples disconnected")
    if not any(point["lane_id"] == role for point in points):
        raise ValueError("requested circulation lane has no original route sample")
    return points


def load_reviewed(review_path, case_id):
    review_path = Path(review_path).resolve()
    if case_id not in {ASSIGNMENT_ID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact rotary-island case")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review.get("case_id") != case_id or review.get("review_status") != "reviewed_original":
        raise ValueError("exact independently reviewed original source required")
    refs = review.get("sources")
    if not isinstance(refs, dict) or set(refs) != {"opendrive", "island_packet", "camera_placement"}:
        raise ValueError("original map, island packet and camera placement sources required")
    sources = {}
    for name, ref in refs.items():
        path = Path(ref["path"])
        path = (path if path.is_absolute() else review_path.parent / path).resolve()
        if not path.is_file() or sha(path) != ref.get("sha256"):
            raise ValueError("reviewed original source hash changed: " + name)
        sources[name] = path
    packet = json.loads(sources["island_packet"].read_text(encoding="utf-8"))
    validate_map(packet, case_id)
    if (packet.get("map_sha256") != sha(sources["opendrive"]) or
            packet.get("native_map_sha256") != packet.get("map_sha256") or
            not packet.get("map_name")):
        raise ValueError("original OpenDRIVE/map identity mismatch")
    selected_role, selected_side = case_id.rsplit("__", 1)[1].split("_")
    if packet.get("selected_lane_role") != selected_role or packet.get("requested_reference_corner") != selected_side:
        raise ValueError("reviewed route does not match exact case variables")
    lanes = {lane["role"]: lane["lane_id"] for lane in packet["circulation_lanes"]}
    route(packet.get("ego_route"), lanes[selected_role])
    if packet["ego_route"][0]["lane_id"] != packet.get("entry_lane_id") or packet["ego_route"][-1]["lane_id"] != packet.get("exit_lane_id"):
        raise ValueError("original entry and exit route identity mismatch")
    if not packet.get("route_source_sha256") or not packet.get("ego_spawn") or not str(packet.get("ego_blueprint", "")).startswith("vehicle."):
        raise ValueError("source-selected route, spawn and motor vehicle required")
    if not packet.get("left_route_physical_review") and selected_side == "left":
        raise ValueError("left-of-island contrast lacks reviewed physical route and clearance")
    placement = json.loads(sources["camera_placement"].read_text(encoding="utf-8"))
    if set(placement.get("cameras", {})) != set(CAMERAS):
        raise ValueError("all four reviewed original camera poses required")
    for name in CAMERAS:
        row = placement["cameras"][name]
        for key in ("location_xyz_m", "pitch_yaw_roll_deg"):
            values = row.get(key)
            if not isinstance(values, list) or len(values) != 3 or any(
                    type(value) not in (int, float) or not math.isfinite(value) for value in values):
                raise ValueError("finite original camera placement required: " + name)
    return {"review_sha256": sha(review_path), "sources": sources,
            "packet": packet, "placement": placement}
