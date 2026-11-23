"""Source-gated roundabout route and original-frame measurement helpers.

This module has no CARLA import. A Native runner supplies map-derived lane samples
and a sealed 20 Hz participant history; neither a case name nor a target lane
establishes what the vehicle actually did.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class SourceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SourceError(message)


def _vector(a: dict, b: dict) -> tuple[float, float]:
    return float(b["x"]) - float(a["x"]), float(b["y"]) - float(a["y"])


def _unit(v: tuple[float, float]) -> tuple[float, float]:
    norm = math.hypot(*v)
    _require(math.isfinite(norm) and norm > 0.01, "degenerate route direction")
    return v[0] / norm, v[1] / norm


def _cross(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _dot(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def verify_topology(source: dict, lane_role: str) -> dict:
    """Select a mapped, connected U-turn route after checking both lane positions.

    Source shape is a map readback, not a worker-authored lane declaration. Each
    route has its own connected waypoint positions through the circular section.
    A geometric 0.95 dot margin checks that the mapped exit is opposite the
    entry; it does not decide any legal meaning or recorded maneuver outcome.
    """
    _require(source.get("source_kind") == "native_map_readback", "missing Native map readback")
    _require(source.get("layout") == "multilane_roundabout", "wrong map layout")
    _require(source.get("jurisdiction") == "Las Vegas, Nevada", "jurisdiction unverified")
    lanes = source.get("lanes", {})
    _require(set(lanes) >= {"left", "outer"}, "both allocated lanes required")
    _require(lane_role in ("left", "outer"), "unknown lane role")
    _require(lanes["left"]["lane_id"] != lanes["outer"]["lane_id"], "lanes not distinct")
    tangent = _unit(_vector(lanes["left"]["sample0"], lanes["left"]["sample1"]))
    lateral = _unit(_vector(lanes["outer"]["sample0"], lanes["left"]["sample0"]))
    _require(_cross(tangent, lateral) > 0.2, "left lane not left of travel")
    entry = _unit(_vector(source["entry"]["prior"], source["entry"]["junction"]))
    departure = _unit(_vector(source["exit"]["junction"], source["exit"]["after"]))
    _require(_dot(entry, departure) < -0.95, "mapped exit not opposite entry")
    route = lanes[lane_role]["route"]
    _require(len(route) >= 5, "roundabout route too short")
    _require(route[0]["section"] == "entry" and route[-1]["section"] == "exit", "route endpoints absent")
    _require(sum(p["section"] == "ring" for p in route) >= 3, "circular lane missing")
    _require(all(p.get("lane_id") == lanes[lane_role]["lane_id"] for p in route if p["section"] == "ring"), "ring lane switch")
    center = source["center"]
    ring_points = [p for p in route if p["section"] == "ring"]
    radii = [math.hypot(*_vector(center, p)) for p in ring_points]
    _require(min(radii) > 1.0 and max(radii) - min(radii) < 0.5 * min(radii), "ring geometry not circular")
    bearings = [math.atan2(p["y"]-center["y"], p["x"]-center["x"]) for p in ring_points]
    turns = [((b-a+math.pi) % (2*math.pi))-math.pi for a, b in zip(bearings, bearings[1:])]
    _require(sum(turns) >= math.pi-0.15 and all(t > 0 for t in turns), "U-turn circular path incomplete")
    for current, following in zip(route, route[1:]):
        gap = math.hypot(*_vector(current, following))
        _require(0.05 < gap <= 12.0, "disconnected mapped route")
    return {"lane_role": lane_role, "lane_id": lanes[lane_role]["lane_id"], "route": route,
            "entry_heading": entry, "exit_heading": departure,
            "map_id": source["map_id"], "map_sha256": source["map_sha256"]}


def verify_original_history(history: dict, topology: dict, case_id: str) -> dict:
    """Measure observed ring-lane occupation and actual departure from Native frames."""
    _require(history.get("source_kind") == "sealed_native_original_history", "missing original Native history")
    _require(history.get("case_id") == case_id, "case source mismatch")
    _require(history.get("map_id") == topology["map_id"] and
             history.get("map_sha256") == topology["map_sha256"], "map source mismatch")
    _require(history.get("actor_role") == "motor_vehicle_driver" and history.get("actor_id"), "operator identity absent")
    _require(history.get("intended_departure") == "opposite_direction", "intended departure not sourced")
    fixed_keys = ("vehicle_blueprint", "entry_id", "exit_id", "controller_sha256", "weather_sha256", "camera_plan_sha256")
    _require(all(history.get(key) for key in fixed_keys), "comparison fixed-condition source missing")
    frames = history.get("frames", [])
    _require(len(frames) == 900, "full 900-frame original history required")
    _require([f.get("frame") for f in frames] == list(range(900)), "original frame discontinuity")
    _require(all(f.get("actor_id") == history["actor_id"] for f in frames), "actor changed")
    times = [f.get("time_s") for f in frames]
    _require(all(isinstance(t, (int, float)) and math.isfinite(t) for t in times), "nonfinite time")
    _require(all(0.049 <= b-a <= 0.051 for a, b in zip(times, times[1:])), "not a contiguous 20 Hz source")
    ring = [f for f in frames if f.get("section") == "ring"]
    _require(len(ring) >= 3 and any(f.get("section") == "exit" for f in frames), "roundabout traversal absent")
    occupied = {f.get("lane_id") for f in ring}
    _require(None not in occupied, "ring lane identity missing")
    last_ring = ring[-1]["frame"]
    exit_frames = [f for f in frames if f.get("section") == "exit" and f["frame"] > last_ring]
    _require(exit_frames, "departure after ring absent")
    heading = _unit((float(exit_frames[-1]["heading_x"]), float(exit_frames[-1]["heading_y"])))
    return {"case_id": case_id, "map_id": topology["map_id"], "actor_id": history["actor_id"],
            "fixed_conditions": {key: history[key] for key in fixed_keys},
            "requested_lane_id": topology["lane_id"], "occupied_ring_lane_ids": sorted(occupied),
            "requested_lane_observed": topology["lane_id"] in occupied,
            "other_ring_lane_observed": bool(occupied - {topology["lane_id"]}),
            "opposite_departure_observed": _dot(topology["entry_heading"], heading) < -0.95,
            "ring_frame_count": len(ring), "source_frame_count": len(frames)}


def compare(a: dict, b: dict) -> dict:
    _require(a["map_id"] == b["map_id"], "comparison changed map")
    _require(a["fixed_conditions"] == b["fixed_conditions"], "comparison changed fixed conditions")
    _require(a["requested_lane_id"] != b["requested_lane_id"], "lane variable did not change")
    _require(a["source_frame_count"] == b["source_frame_count"] == 900, "comparison source incomplete")
    return {"case_ids": [a["case_id"], b["case_id"]], "same_map": True,
            "both_departures_observed": a["opposite_departure_observed"] and b["opposite_departure_observed"],
            "observed_lane_ids": [a["occupied_ring_lane_ids"], b["occupied_ring_lane_ids"]]}


def load_sealed_json(path: str | Path, expected_sha256: str) -> dict:
    payload = Path(path).read_bytes()
    _require(hashlib.sha256(payload).hexdigest() == expected_sha256, "source hash mismatch")
    value = json.loads(payload)
    _require(isinstance(value, dict), "source object required")
    return value
