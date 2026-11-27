"""Source-gated roundabout direction construction and original-frame measurement.

Positive polar-angle change around a surveyed island centre is counterclockwise
in the native map's XY frame. Engineering tolerances reject sensor jitter; they
do not define a legal amount of permissible clockwise travel.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C238432__LVMC-11-43-010-A__motor_vehicle_driver"
CASE_DIRECTIONS = {
    ASSIGNMENT + "__counterclockwise": 1,
    ASSIGNMENT + "__clockwise": -1,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_source(path, expected_sha256, case_id):
    """Require an original source-reviewed map packet before Native operation."""
    path = Path(path)
    require(sha(path) == expected_sha256, "reviewed map packet hash mismatch")
    packet = json.loads(path.read_text())
    require(case_id in CASE_DIRECTIONS, "wrong exact case")
    require(packet.get("source_kind") == "native_map_readback", "original map readback absent")
    require(packet.get("jurisdiction") == "Las Vegas, Nevada", "jurisdiction unverified")
    require(packet.get("layout") == "roundabout", "roundabout topology unverified")
    require(packet.get("map_name") and packet.get("opendrive_sha256"), "map identity absent")
    require(packet.get("central_island") and packet.get("entry_yield_control") and
            packet.get("outer_boundary") and packet.get("circulatory_roadway"),
            "roundabout constituent geometry absent")
    center = packet.get("island_center")
    require(isinstance(center, dict) and all(type(center.get(k)) in (int, float)
            and math.isfinite(center[k]) for k in ("x", "y")), "island centre absent")
    routes = packet.get("connected_routes")
    require(isinstance(routes, dict) and set(routes) == {"counterclockwise", "clockwise"},
            "both map-connected direction routes required")
    for name, route in routes.items():
        require(isinstance(route, list) and len(route) >= 5, "mapped route too short")
        require(route[0].get("section") == "entry" and route[-1].get("section") == "exit" and
                sum(p.get("section") == "ring" for p in route) >= 3,
                "entry, circulating road and exit required")
        for point in route:
            require(all(type(point.get(k)) in (int, float) and math.isfinite(point[k])
                        for k in ("x", "y")) and point.get("lane_id"),
                    "original mapped waypoint absent")
        for a, b in zip(route, route[1:]):
            require(0.05 < math.hypot(b["x"]-a["x"], b["y"]-a["y"]) <= 12,
                    "mapped route disconnected")
        ring = [p for p in route if p["section"] == "ring"]
        angles = [math.atan2(p["y"]-center["y"], p["x"]-center["x"]) for p in ring]
        steps = [wrap(b-a) for a, b in zip(angles, angles[1:])]
        sign = 1 if name == "counterclockwise" else -1
        require(all(sign*step > 0.01 for step in steps) and sign*sum(steps) > 0.7,
                "mapped direction or arc absent")
    require(routes["counterclockwise"][0]["lane_id"] == routes["clockwise"][0]["lane_id"],
            "comparison entry lane changed")
    return packet


def wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


def measure_history(packet, history, case_id, *, expected_frames=900):
    """Measure actual signed ring travel; never trust a requested route label."""
    require(case_id in CASE_DIRECTIONS and history.get("case_id") == case_id,
            "original history case mismatch")
    require(history.get("source_kind") == "sealed_native_original_history",
            "sealed original history absent")
    require(history.get("map_name") == packet["map_name"] and
            history.get("opendrive_sha256") == packet["opendrive_sha256"],
            "original map binding changed")
    require(history.get("actor_role") == "motor_vehicle_driver" and history.get("actor_id"),
            "motor vehicle operator identity absent")
    frames = history.get("frames")
    require(isinstance(frames, list) and len(frames) == expected_frames,
            "complete original frame history required")
    first_frame=frames[0].get("frame")
    require(type(first_frame) is int and
            [row.get("frame") for row in frames] == list(range(first_frame,first_frame+expected_frames)),
            "original frame sequence discontinuity")
    first_time=frames[0].get("time_s")
    require(type(first_time) in (int,float) and math.isfinite(first_time),
            "original start time absent")
    center = packet["island_center"]
    ring = []
    for index, row in enumerate(frames):
        require(row.get("actor_id") == history["actor_id"] and
                type(row.get("time_s")) in (int, float) and
                math.isfinite(row["time_s"]) and
                abs(row["time_s"] - first_time - index * .05) < .002,
                "original actor or 20 Hz time changed")
        require(all(type(row.get(k)) in (int, float) and math.isfinite(row[k])
                    for k in ("x", "y")), "original XY missing")
        if row.get("section") == "ring":
            require(row.get("lane_id") in packet["circulatory_roadway"]["lane_ids"],
                    "original ring lane unverified")
            ring.append(row)
    require(len(ring) >= 3 and ring[-1]["frame"] > ring[0]["frame"],
            "actual circular travel absent")
    angles = [math.atan2(row["y"]-center["y"], row["x"]-center["x"]) for row in ring]
    steps = [wrap(b-a) for a, b in zip(angles, angles[1:])]
    require(all(abs(step) < .4 for step in steps), "original ring sampling aliases direction")
    signed = sum(steps)
    require(abs(signed) > .7, "observed circular arc too short to classify")
    direction = "counterclockwise" if signed > 0 else "clockwise"
    return {"case_id": case_id, "map_name": packet["map_name"],
            "actor_id": history["actor_id"], "source_frames": len(frames),
            "ring_frames": len(ring), "signed_arc_rad": signed,
            "observed_direction": direction, "requested_direction":
            "counterclockwise" if CASE_DIRECTIONS[case_id] == 1 else "clockwise",
            "legal_judgment": "unresolved"}


def compare(left, right):
    require({left["case_id"], right["case_id"]} == set(CASE_DIRECTIONS),
            "comparison exact cases differ")
    require(left["map_name"] == right["map_name"] and
            left["source_frames"] == right["source_frames"] == 900,
            "comparison changed map or duration")
    require(left["observed_direction"] != right["observed_direction"],
            "observed direction did not change")
    return {"case_ids": [left["case_id"], right["case_id"]],
            "observed_directions": [left["observed_direction"], right["observed_direction"]],
            "legal_judgment": "unresolved"}
