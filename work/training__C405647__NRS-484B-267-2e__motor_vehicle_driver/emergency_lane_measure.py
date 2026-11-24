"""Source-bound emergency-vehicle approach and lane diagnostic.

Lane count never establishes whether a lane change is possible or safe. The
officer direction and adverse-condition exceptions remain explicit unknowns.
"""
import hashlib
import json
import math

ASSIGNMENT = "training__C405647__NRS-484B-267-2e__motor_vehicle_driver"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def measure(context_bytes, trace_bytes):
    context, trace = json.loads(context_bytes), json.loads(trace_bytes)
    require(context.get("assignment_id") == ASSIGNMENT and trace.get("assignment_id") == ASSIGNMENT,
            "assignment mismatch")
    require(context.get("source_kind") == trace.get("source_kind")
            and context.get("source_kind") in {"synthetic_native_sample", "original_native_observation"},
            "source kind mismatch")
    require(context.get("fixed_cell") == {"layout": "road", "maneuver": "travel",
                                           "control": "emergency_vehicle"}, "fixed cell mismatch")
    emergency = context.get("emergency_vehicle", {})
    require(emergency.get("authorization_source_id") and emergency.get("equipment_source_id")
            and emergency.get("vehicle_class") in {"authorized_emergency", "regulatory_official"}
            and emergency.get("flashing_qualification_source_id")
            and emergency.get("flashing_lamp_source_id"),
            "qualifying emergency vehicle or lamps source missing")
    lanes = context.get("lanes", {})
    require(lanes.get("topology_source_id") and lanes.get("emergency_lane_id")
            and isinstance(lanes.get("adjacent_lane_ids"), list)
            and isinstance(lanes.get("nonadjacent_lane_ids"), list)
            and lanes["nonadjacent_lane_ids"], "lane topology source missing")
    conditions = context.get("conditions", {})
    require(all(conditions.get(k) for k in ("roadway_source_id", "traffic_source_id",
                                              "weather_source_id", "officer_direction_source_id")),
            "safety or officer context source missing")
    frames = trace.get("frames", [])
    require(len(frames) >= 600 and all(f.get("frame") == i
            and abs(f.get("t_s", -1) - i / 20) < 1e-8 for i, f in enumerate(frames)),
            "30-second contiguous 20 Hz trace required")
    require(trace.get("ego_id") and trace.get("emergency_id")
            and trace["ego_id"] != trace["emergency_id"]
            and all(f.get("ego_id") == trace["ego_id"]
                    and f.get("emergency_id") == trace["emergency_id"] for f in frames),
            "participant identity source missing")
    require(all(f.get("lane_source_id") == lanes["topology_source_id"]
                and f.get("emergency_lane_id") == lanes["emergency_lane_id"]
                and isinstance(f.get("ego_lane_id"), str) and f["ego_lane_id"]
                and isinstance(f.get("ego_approaching"), bool)
                and isinstance(f.get("flashing_lamps_observed"), bool)
                and isinstance(f.get("visible_preparation_observed"), bool)
                and isinstance(f.get("emergency_velocity_xyz_mps"), list)
                and len(f["emergency_velocity_xyz_mps"]) == 3
                and all(isinstance(v, (int, float)) and math.isfinite(v)
                        for v in f["emergency_velocity_xyz_mps"]) for f in frames),
            "Native lane, approach, lamp or motion source missing")
    active = [f for f in frames if f["ego_approaching"] and f["flashing_lamps_observed"]
              and (math.sqrt(sum(v * v for v in f["emergency_velocity_xyz_mps"])) > 0.05
                   or f["visible_preparation_observed"])]
    require(active, "no observed qualifying approach interval")
    nonadjacent = set(lanes["nonadjacent_lane_ids"])
    adjacent = set(lanes["adjacent_lane_ids"])
    require(not nonadjacent.intersection(adjacent) and lanes["emergency_lane_id"] not in nonadjacent,
            "lane adjacency graph inconsistent")
    return {"format": "c405647-emergency-lane-diagnostic-v1", "assignment_id": ASSIGNMENT,
            "context_sha256": hashlib.sha256(context_bytes).hexdigest(),
            "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
            "source_kind": context["source_kind"], "frame_count": len(frames),
            "duration_s": len(frames) / 20,
            "qualifying_approach_frame_range": [active[0]["frame"], active[-1]["frame"]],
            "active_adjacent_frames": [f["frame"] for f in active if f["ego_lane_id"] in adjacent],
            "active_nonadjacent_frames": [f["frame"] for f in active if f["ego_lane_id"] in nonadjacent],
            "moving_measurement_tolerance_mps": 0.05,
            "lane_change_possible": None, "lane_change_safe": None,
            "officer_override": None, "legal_result": None,
            "physical_completion": False}
