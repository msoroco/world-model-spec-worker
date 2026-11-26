"""Source-gated C150979 speed construction and original-history measurement.

This module is CARLA-lazy. A packet is a reviewable site inventory, not proof of
municipal authority or a legal posting rule. No expected legal label is emitted.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


LAW = "LVMC-11-16-060"
ASSIGNMENT = "testing__C150979__LVMC-11-16-060__motor_vehicle_driver"
MPH_TO_MPS = 0.44704
TARGETS = {
    "unposted_below": ("unposted", 20.0),
    "unposted_at": ("unposted", 25.0),
    "unposted_above": ("unposted", 30.0),
    "same25_below": ("same25", 20.0),
    "same25_at": ("same25", 25.0),
    "same25_above": ("same25", 30.0),
    "different35": ("different35", 30.0),
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_site(packet, case_key, expected_map_sha256):
    """Reject incomplete site authority/geometry before spawning or measuring."""
    _require(case_key in TARGETS, "unknown exact case")
    _require(packet.get("law_id") == LAW and packet.get("cell_id") == "C150979", "site identity mismatch")
    _require(packet.get("map_sha256") == expected_map_sha256 and len(expected_map_sha256) == 64, "map seal mismatch")
    _require(packet.get("municipal_jurisdiction_source"), "municipal jurisdiction source missing")
    _require(packet.get("covered_street_source") and packet.get("road_kind") in ("street", "highway"), "covered street source missing")
    route = packet.get("route", {})
    _require(route.get("one_way_source") and route.get("lane_id") is not None and route.get("road_id") is not None, "one-way route source missing")
    _require(isinstance(route.get("spawn_station_m"), (int, float)) and isinstance(route.get("end_station_m"), (int, float)), "route stations missing")
    _require(route["end_station_m"] - route["spawn_station_m"] >= 100.0, "route too short to observe governed travel")
    _require(packet.get("sign_inventory_complete_source") and packet.get("sign_inventory_extent_m") == [route["spawn_station_m"], route["end_station_m"]], "complete sign inventory missing")
    _require(packet.get("title_posting_review_source"), "Title posting review missing")
    signs = packet.get("signs", [])
    _require(isinstance(signs, list), "sign inventory invalid")
    for sign in signs:
        _require(sign.get("source") and sign.get("direction") == "route" and sign.get("governed_start_station_m") is not None and sign.get("governed_end_station_m") is not None, "sign scope/source missing")
        _require(sign["governed_start_station_m"] < sign["governed_end_station_m"], "sign scope invalid")
        _require(sign.get("value_mph") in (25, 35), "unreviewed posted value")
        _require(sign.get("time_conditions_source"), "sign time conditions missing")
    if TARGETS[case_key][0] == "unposted":
        _require(not signs, "unposted case has sign")
    elif TARGETS[case_key][0] == "same25":
        _require(len(signs) == 1 and signs[0]["value_mph"] == 25, "same-value sign missing")
    else:
        _require(len(signs) == 1 and signs[0]["value_mph"] == 35, "different posted limit missing")
    return route


def construct(world, packet, case_key, expected_map_sha256, ego_blueprint="vehicle.tesla.model3"):
    """Spawn on a source-checked map waypoint; caller owns actor cleanup/capture."""
    route = validate_site(packet, case_key, expected_map_sha256)
    _require(world.get_map().name == packet["map_name"], "native map name mismatch")
    start = packet.get("start_xyz")
    _require(isinstance(start, list) and len(start) == 3 and all(math.isfinite(x) for x in start), "source start location missing")
    import carla  # imported only during Native execution
    waypoint = world.get_map().get_waypoint(carla.Location(*start), project_to_road=False)
    _require(waypoint is not None and waypoint.road_id == route["road_id"] and waypoint.lane_id == route["lane_id"], "source route does not match Native lane")
    blueprint = world.get_blueprint_library().find(ego_blueprint)
    _require(blueprint is not None, "ego blueprint unavailable")
    actor = world.try_spawn_actor(blueprint, waypoint.transform)
    _require(actor is not None, "ego spawn failed")
    return {"actor": actor, "target_mps": TARGETS[case_key][1] * MPH_TO_MPS,
            "route": route, "signs": packet["signs"], "case_id": f"{ASSIGNMENT}__{case_key}"}


def control_tick(actor, target_mps):
    """Apply bounded feedback from actual velocity; target is never measurement."""
    _require(math.isfinite(target_mps) and target_mps > 0, "invalid requested speed")
    velocity = actor.get_velocity()
    observed_mps = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    _require(math.isfinite(observed_mps), "Native velocity invalid")
    error = target_mps - observed_mps
    import carla
    throttle = min(0.65, max(0.0, 0.25 + 0.09 * error)) if error > 0 else 0.0
    brake = min(0.65, max(0.0, -0.12 * error)) if error < 0 else 0.0
    actor.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=0.0))
    return {"requested_mps": target_mps, "observed_mps": observed_mps,
            "throttle": throttle, "brake": brake}


def measure(packet, case_key, expected_map_sha256, frames, diagnostic_fixture=False):
    """Audit original 20 Hz samples and observed sign passage, never command speed."""
    route = validate_site(packet, case_key, expected_map_sha256)
    minimum_frames = 9 if diagnostic_fixture else 400
    _require(len(frames) >= minimum_frames, "insufficient original frames")
    observations = []
    for i, frame in enumerate(frames):
        _require(frame.get("frame_index") == i, "original frame gap")
        _require(abs(frame.get("time_s", -1) - i / 20.0) <= 0.002, "20 Hz original time join failed")
        _require(frame.get("ego_alive") is True and frame.get("driver_role") == "motor_vehicle_driver", "driver identity/alive readback missing")
        _require(frame.get("map_sha256") == expected_map_sha256, "frame map seal mismatch")
        station = frame.get("route_station_m")
        speed = frame.get("speed_mps")
        _require(isinstance(station, (int, float)) and math.isfinite(station), "route station missing")
        _require(isinstance(speed, (int, float)) and math.isfinite(speed) and speed >= 0, "observed speed missing")
        if i:
            _require(station >= frames[i - 1]["route_station_m"] - 0.1, "route progress reversed")
        if route["spawn_station_m"] + 20 <= station <= route["end_station_m"] - 10:
            observations.append({"frame_index": i, "time_s": frame["time_s"], "station_m": station,
                                 "speed_mph": speed / MPH_TO_MPS})
    _require(len(observations) >= (3 if diagnostic_fixture else 100),
             "governed travel interval missing")
    signs = packet["signs"]
    if signs:
        sign = signs[0]
        _require(frames[0]["route_station_m"] < sign["governed_start_station_m"] < frames[-1]["route_station_m"], "physical sign passage not observed")
        _require(any(x["station_m"] >= sign["governed_start_station_m"] and x["station_m"] <= sign["governed_end_station_m"] for x in observations), "posted governed portion not traveled")
        _require(all(f.get("sign_id") == sign["sign_id"] and f.get("sign_value_mph") == sign["value_mph"] for f in frames if f["route_station_m"] >= sign["governed_start_station_m"]), "sign Native readback mismatch")
    return {"case_id": f"{ASSIGNMENT}__{case_key}", "law_id": LAW,
            "target_mph": TARGETS[case_key][1], "posting_context": TARGETS[case_key][0],
            "map_sha256": expected_map_sha256, "route": route,
            "observed_speed_mph_min": min(x["speed_mph"] for x in observations),
            "observed_speed_mph_max": max(x["speed_mph"] for x in observations),
            "governed_original_samples": observations, "original_frame_count": len(frames),
            "legal_status": "unresolved_prima_facie_and_title_posting_review"}


def compare(reports, case_keys, varying_posting=False, diagnostic_fixture=False):
    """Reject missing members and changed posting context in linked speed probes."""
    _require(len(reports) == len(case_keys), "comparison member missing")
    expected_context = TARGETS[case_keys[0]][0]
    expected_map = reports[0].get("map_sha256")
    expected_route = reports[0].get("route")
    for report, key in zip(reports, case_keys):
        _require(report.get("case_id") == f"{ASSIGNMENT}__{key}", "comparison case mismatch")
        _require(report.get("posting_context") == TARGETS[key][0], "comparison posting context mismatches case")
        if not varying_posting:
            _require(report.get("posting_context") == expected_context, "comparison posting context changed")
        _require(report.get("map_sha256") == expected_map and report.get("route") == expected_route, "comparison map or route changed")
        _require(report.get("governed_original_samples") and
                 report.get("original_frame_count") >= (9 if diagnostic_fixture else 400),
                 "comparison original evidence missing")
    if varying_posting:
        _require(len(set(r["posting_context"] for r in reports)) == len(reports), "posting exception contrast missing")
        _require(len(set(r["target_mph"] for r in reports)) == 1, "posting comparison changed target speed")
    return {"case_ids": [r["case_id"] for r in reports], "measured_speed_ranges_mph":
            [[r["observed_speed_mph_min"], r["observed_speed_mph_max"]] for r in reports],
            "legal_status": "unresolved"}
