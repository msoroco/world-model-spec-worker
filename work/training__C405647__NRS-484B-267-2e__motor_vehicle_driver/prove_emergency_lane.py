"""Pinned-source synthetic CPU proof of emergency lane observations."""
import hashlib
import json
from pathlib import Path
from emergency_lane_measure import ASSIGNMENT, measure

ASSIGNMENT_SHA = "d199d33786c97f6e4c8cd288f10bf3ea2cfce673f1c05afaa75c462fc34d15dd"
WITNESS_SHA = "38d969186e2789ef3b5525a0c069c55bfaff6e76f8e6fd3e0ace3488846a9f2a"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def enc(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sample(move_over):
    context = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
               "fixed_cell": {"layout": "road", "maneuver": "travel",
                              "control": "emergency_vehicle"},
               "emergency_vehicle": {"authorization_source_id": "synthetic-authority",
                                     "equipment_source_id": "synthetic-equipment",
                                     "vehicle_class": "authorized_emergency",
                                     "flashing_qualification_source_id": "synthetic-484a480-3",
                                     "flashing_lamp_source_id": "synthetic-lamps"},
               "lanes": {"topology_source_id": "synthetic-lanes", "emergency_lane_id": "lane-0",
                         "adjacent_lane_ids": ["lane-1"], "nonadjacent_lane_ids": ["lane-2"]},
               "conditions": {"roadway_source_id": "synthetic-road", "traffic_source_id": "synthetic-traffic",
                              "weather_source_id": "synthetic-weather",
                              "officer_direction_source_id": "synthetic-no-officer"}}
    frames = [{"frame": i, "t_s": i / 20, "ego_id": "ego", "emergency_id": "emergency",
               "lane_source_id": "synthetic-lanes", "emergency_lane_id": "lane-0",
               "ego_lane_id": "lane-2" if move_over and i >= 300 else "lane-1",
               "ego_approaching": 100 <= i < 500,
               "flashing_lamps_observed": 100 <= i < 500,
               "visible_preparation_observed": False,
               "emergency_velocity_xyz_mps": [2.0, 0.0, 0.0]}
              for i in range(600)]
    return context, {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
                     "ego_id": "ego", "emergency_id": "emergency", "frames": frames}


def reject(context, trace, expected):
    try:
        measure(enc(context), enc(trace))
    except ValueError as exc:
        require(str(exc) == expected, "wrong rejection: " + str(exc))
        return
    raise ValueError("invalid source accepted")


def main():
    source = Path(__file__).resolve().parents[2] / "inputs" / ASSIGNMENT
    require(hashlib.sha256((source / "assignment.json").read_bytes()).hexdigest() == ASSIGNMENT_SHA,
            "assignment source changed")
    require(hashlib.sha256((source / "witnesses.json").read_bytes()).hexdigest() == WITNESS_SHA,
            "witness source changed")
    law = json.loads((source / "assignment.json").read_text())["law"]["text"]
    require("If possible" in law and "flashing lights" in law
            and "law enforcement officer" in law and "preparing to move" in law,
            "statutory activation or exceptions changed")
    context, trace = sample(True)
    moved = measure(enc(context), enc(trace))
    require(moved["active_adjacent_frames"] == list(range(100, 300))
            and moved["active_nonadjacent_frames"] == list(range(300, 500))
            and moved["lane_change_possible"] is None and moved["legal_result"] is None,
            "moving-emergency lane contrast failed")
    context, trace = sample(False)
    stayed = measure(enc(context), enc(trace))
    require(stayed["active_nonadjacent_frames"] == [] and stayed["legal_result"] is None,
            "adjacent-lane diagnostic failed")
    context["emergency_vehicle"]["flashing_qualification_source_id"] = ""
    reject(context, trace, "qualifying emergency vehicle or lamps source missing")
    context, trace = sample(False)
    context["conditions"]["weather_source_id"] = ""
    reject(context, trace, "safety or officer context source missing")
    context, trace = sample(False)
    trace["frames"][200]["emergency_velocity_xyz_mps"] = []
    reject(context, trace, "Native lane, approach, lamp or motion source missing")
    print(json.dumps({"passed": True, "assignment_sha256": ASSIGNMENT_SHA,
                      "witness_sha256": WITNESS_SHA,
                      "moved_trace_sha256": moved["trace_sha256"],
                      "stayed_trace_sha256": stayed["trace_sha256"],
                      "checks": ["30s_20hz", "active_flashing_moving_approach",
                                 "adjacent_nonadjacent_observation", "possible_and_safe_unknown",
                                 "lamp_source_rejection", "weather_source_rejection",
                                 "motion_source_rejection"]}, sort_keys=True))


if __name__ == "__main__":
    main()
