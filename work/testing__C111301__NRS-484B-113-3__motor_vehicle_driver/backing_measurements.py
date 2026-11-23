"""Original-frame measurements and source-bound controlled comparison.

The measured timeline preserves uncertainty about statutory right of way.
"""
from math import hypot


def _xy(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("original XY sample required")
    return float(value[0]), float(value[1])


def measure(frames, *, source_id, map_sha256, vehicle_actor_id, pedestrian_actor_id):
    if not source_id or len(map_sha256) != 64 or not frames:
        raise ValueError("original source and map hash required")
    if vehicle_actor_id == pedestrian_actor_id or vehicle_actor_id is None or pedestrian_actor_id is None:
        raise ValueError("distinct original actors required")
    rows = []
    previous_frame, previous_time = -1, -1.0
    for sample in frames:
        required = ("frame", "time_s", "vehicle_actor_id", "pedestrian_actor_id",
                    "vehicle_xy", "pedestrian_xy", "vehicle_velocity_xy",
                    "vehicle_forward_xy", "pedestrian_velocity_xy", "brake",
                    "reverse_gear", "pedestrian_in_corridor")
        if any(k not in sample for k in required):
            raise ValueError("missing original frame measurement")
        index, now = int(sample["frame"]), float(sample["time_s"])
        if index <= previous_frame or now <= previous_time:
            raise ValueError("original frame and time must increase")
        if sample["vehicle_actor_id"] != vehicle_actor_id or sample["pedestrian_actor_id"] != pedestrian_actor_id:
            raise ValueError("original actor identity changed")
        previous_frame, previous_time = index, now
        car, person = _xy(sample["vehicle_xy"]), _xy(sample["pedestrian_xy"])
        velocity, forward = _xy(sample["vehicle_velocity_xy"]), _xy(sample["vehicle_forward_xy"])
        pedestrian_velocity = _xy(sample["pedestrian_velocity_xy"])
        reverse_speed = -(velocity[0]*forward[0]+velocity[1]*forward[1])
        rows.append({"frame": index, "time_s": now, "pedestrian_gap_m": hypot(car[0]-person[0], car[1]-person[1]),
                     "reverse_speed_mps": reverse_speed, "brake": float(sample["brake"]),
                     "reverse_gear": bool(sample["reverse_gear"]),
                     "pedestrian_speed_mps": hypot(*pedestrian_velocity),
                     "pedestrian_in_corridor": bool(sample["pedestrian_in_corridor"])})
    if not any(r["reverse_gear"] and r["reverse_speed_mps"] > .05 for r in rows):
        raise ValueError("backing not observed in original frames")
    if not any(r["pedestrian_in_corridor"] and r["pedestrian_speed_mps"] > .05 for r in rows):
        raise ValueError("moving pedestrian conflict not observed")
    return {"source_id": source_id, "map_sha256": map_sha256, "frames": rows,
            "vehicle_actor_id": vehicle_actor_id, "pedestrian_actor_id": pedestrian_actor_id,
            "legal_judgment": "unresolved"}


def compare(left, right):
    if left["map_sha256"] != right["map_sha256"] or left["source_id"] == right["source_id"]:
        raise ValueError("comparison needs common map and distinct original sources")
    a, b = left["frames"], right["frames"]
    if len(a) != len(b) or [r["frame"] for r in a] != [r["frame"] for r in b]:
        raise ValueError("comparison frame window differs")
    fixed = ("pedestrian_in_corridor", "pedestrian_speed_mps", "pedestrian_gap_m")
    if any(any(abs(x[key]-y[key]) > .02 if isinstance(x[key], float) else x[key] != y[key]
               for key in fixed) for x,y in zip(a,b)):
        raise ValueError("pedestrian exposure differs across yield comparison")
    if not any(x["reverse_speed_mps"] != y["reverse_speed_mps"] or x["brake"] != y["brake"]
               for x,y in zip(a,b)):
        raise ValueError("no observed driver-response difference")
    return {"sources": [left["source_id"], right["source_id"]],
            "fixed_observables": list(fixed), "changed_observables": ["reverse_speed_mps", "brake"],
            "legal_judgment": "unresolved"}
