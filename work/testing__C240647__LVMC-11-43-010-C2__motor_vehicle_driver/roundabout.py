"""Source-gated roundabout route and original lane/exit measurements."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

class SourceError(ValueError):
    pass

def need(value, message):
    if not value:
        raise SourceError(message)

def load_sealed_json(path, expected_sha256):
    raw = Path(path).read_bytes()
    need(hashlib.sha256(raw).hexdigest() == expected_sha256, "source hash mismatch")
    packet = json.loads(raw)
    need(isinstance(packet, dict), "source object required")
    return packet

def verify_topology(source, case):
    need(source.get("source_kind") == "native_map_readback", "original Native map required")
    need(source.get("jurisdiction") == "Las Vegas, Nevada", "jurisdiction unverified")
    need(source.get("layout") in ("multilane_roundabout", "single_lane_roundabout"), "roundabout missing")
    need(source.get("map_id") and len(source.get("map_sha256", "")) == 64, "map identity missing")
    role = case.get("roundabout_lane_request")
    need(role in ("right", "left", "left_then_right", "right_then_left", "single_right"), "lane control invalid")
    need(case.get("operator_intent_request") in ("right_exit", "through"), "intent control invalid")
    exit_role = case.get("actual_exit_request")
    need(exit_role in ("right_exit", "through_exit", "no_exit"), "exit control invalid")
    lanes = source.get("lanes", {})
    need("right" in lanes, "mapped right lane missing")
    if role == "single_right":
        need(source["layout"] == "single_lane_roundabout", "single lane source required")
    else:
        need(source["layout"] == "multilane_roundabout" and "left" in lanes, "two mapped lanes required")
        need(lanes["right"].get("lane_id") != lanes["left"].get("lane_id"), "lanes not distinct")
    for lane in lanes.values():
        need(lane.get("lane_id") and lane.get("source_waypoint_ids"), "source lane provenance missing")
    exits = source.get("exit_connectors", {})
    need(set(exits) >= {"right_exit", "through_exit"}, "right and through connectors required")
    for connector in ("right_exit", "through_exit"):
        need(exits[connector].get("connector_id") and exits[connector].get("source_waypoint_ids"), "connector source missing")
    need(exits["right_exit"]["connector_id"] != exits["through_exit"]["connector_id"], "connectors not distinct")
    route = source.get("routes", {}).get(case.get("case_id"))
    need(isinstance(route, list) and len(route) >= 5, "exact route missing")
    need(route[0].get("section") == "approach", "approach route missing")
    if exit_role == "no_exit":
        need(route[-1].get("section") == "circulating" and not any(p.get("section") == "exit" for p in route), "no-exit route departed")
    else:
        need(route[-1].get("section") == "exit" and route[-1].get("exit_connector_id") == exits[exit_role]["connector_id"], "connected exit differs")
    sequence = []
    for index, point in enumerate(route):
        need(point.get("source_waypoint_id"), "route waypoint source missing")
        x, y = point.get("x"), point.get("y")
        need(type(x) in (int, float) and type(y) in (int, float) and math.isfinite(x) and math.isfinite(y), "route geometry invalid")
        if index:
            prev = route[index-1]
            need(.05 < math.hypot(x-prev["x"], y-prev["y"]) <= 12, "mapped route disconnected")
        if point.get("section") == "circulating":
            lane_role = point.get("lane_role")
            need(lane_role in lanes and point.get("lane_id") == lanes[lane_role]["lane_id"], "circular lane source mismatch")
            if not sequence or sequence[-1] != lane_role:
                sequence.append(lane_role)
    expected = {"right":["right"], "left":["left"], "left_then_right":["left","right"], "right_then_left":["right","left"], "single_right":["right"]}[role]
    need(sequence == expected, "route lane sequence differs from selected control")
    return {"case_id":case["case_id"], "map_id":source["map_id"], "map_sha256":source["map_sha256"], "route":route,
            "right_lane_id":lanes["right"]["lane_id"], "left_lane_id":lanes.get("left",{}).get("lane_id"),
            "intended_exit_role":case["operator_intent_request"], "requested_exit_role":exit_role,
            "right_exit_connector_id":exits["right_exit"]["connector_id"],
            "through_exit_connector_id":exits["through_exit"]["connector_id"]}

def verify_original_history(history, topology, case_id, expected_frames=900):
    need(history.get("source_kind") == "sealed_native_original_history", "original history required")
    need(history.get("case_id") == case_id == topology["case_id"], "history case mismatch")
    need(history.get("map_id") == topology["map_id"] and history.get("map_sha256") == topology["map_sha256"], "map source changed")
    need(history.get("actor_role") == "motor_vehicle_driver" and history.get("actor_id"), "operator identity missing")
    need(history.get("independent_operator_intent_source_sha256") and history.get("operator_intended_exit_role") == topology["intended_exit_role"], "independent intent missing")
    for key in ("vehicle_blueprint","entry_id","controller_sha256","weather_sha256","camera_plan_sha256"):
        need(history.get(key), "fixed source missing: "+key)
    frames = history.get("frames")
    need(expected_frames in (9,900) and isinstance(frames,list) and len(frames) == expected_frames, "full frame history required")
    need([r.get("frame") for r in frames] == list(range(expected_frames)), "frame sequence incomplete")
    ring, first_exit = [], None
    for i, row in enumerate(frames):
        need(row.get("actor_id") == history["actor_id"], "actor changed")
        t = row.get("time_s")
        need(type(t) in (int,float) and math.isfinite(t) and abs(t-i/20) < .002, "20 Hz source cadence invalid")
        section = row.get("section")
        need(section in ("approach","circulating","exit"), "source section missing")
        connector = row.get("exit_connector_id")
        if section == "circulating":
            need(row.get("lane_id") in {topology["right_lane_id"],topology["left_lane_id"]}, "unmapped ring lane")
            need(connector is None, "premature connector")
            ring.append(row["lane_id"])
        elif section == "exit":
            need(connector in {topology["right_exit_connector_id"],topology["through_exit_connector_id"]}, "unmapped exit connector")
            if first_exit is None:
                first_exit = connector
        else:
            need(connector is None, "connector before roundabout")
        speed = row.get("speed_mps")
        need(type(speed) in (int,float) and math.isfinite(speed) and speed >= 0, "original speed missing")
        if expected_frames == 900:
            need(row.get("source_frame_id") is not None and isinstance(row.get("body_vertices_m"),list) and len(row["body_vertices_m"]) >= 4, "original body/source frame missing")
    need(ring, "roundabout operation unobserved")
    return {"case_id":case_id,"map_id":topology["map_id"],"actor_id":history["actor_id"],
            "operator_intended_exit_role":history["operator_intended_exit_role"],
            "right_lane_id":topology["right_lane_id"],"occupied_ring_lane_ids":sorted(set(ring)),
            "all_circulating_frames_right_lane":all(v == topology["right_lane_id"] for v in ring),
            "last_circulating_lane_id":ring[-1],"first_observed_exit_connector_id":first_exit,
            "right_exit_connector_id":topology["right_exit_connector_id"],
            "right_exit_observed":first_exit == topology["right_exit_connector_id"],
            "source_frame_count":expected_frames,
            "fixed_conditions":{key:history[key] for key in ("vehicle_blueprint","entry_id","controller_sha256","weather_sha256","camera_plan_sha256")},
            "legal_judgment":"unresolved"}
