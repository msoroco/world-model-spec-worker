"""Source-bound engineering completion of an alley parking episode.

No returned status determines whether the vehicle legally blocked access.
Original pixels and legal facts remain separate independent review.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _check(status, method, sources, details=None, missing=None):
    return {"status": status, "method": method, "sources": sources,
            "details": details or {}, "missing_evidence": missing or [],
            "legal_verdict_claimed": False, "physical_causation_claimed": False}


def assess(attempt: Path, config: dict, measurement: dict) -> dict:
    root = Path(attempt)
    source = root / "original-attempt"
    required = [source / "inventory.json", source / "frame_map.json",
                source / "activity.json", source / "vehicle_footprint.json",
                root / "trace.jsonl", root / "video_frames.jsonl"]
    present = {str(p.relative_to(root)): _sha(p) for p in required if p.is_file()}
    missing = [str(p.relative_to(root)) for p in required if not p.is_file()]
    method = "original frame-joined approach, parked hold and departure assessment"
    if missing:
        unknown = _check("unverified", method, present, missing=missing)
        return {"physical_checks": {name: unknown.copy() for name in ("setup", "target", "maneuver")},
                "setup_confirmed": False, "behavior_attempted": False,
                "maneuver_completed": False, "realized_observables": {}}
    try:
        inventory = json.loads((source / "inventory.json").read_text())
        diagnostic = inventory.get("diagnostic_fixture") is True
        frames = json.loads((source / "frame_map.json").read_text())["frames"]
        activity = json.loads((source / "activity.json").read_text())["samples"]
        footprints = json.loads((source / "vehicle_footprint.json").read_text())["samples"]
        trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines() if line.strip()]
        mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines() if line.strip()]
        count = 9 if diagnostic else 900
        if not all(len(seq) == count for seq in (frames, activity, footprints, trace, mapping)):
            raise ValueError("original parking frame inventory incomplete")
        for i, (frame, state, body, event, video) in enumerate(zip(frames, activity, footprints, trace, mapping)):
            if (frame["frame"] != state["frame"] or frame["frame"] != body["frame"] or
                    frame["frame"] != event["frame"] or frame["frame"] != video["carla_frame"] or
                    frame["time_s"] != state["time_s"] or frame["time_s"] != body["time_s"] or
                    abs(frame["time_s"] - event["time_s"]) > 1e-4 or
                    frame["time_s"] != video["time_s"] or video["video_frame"] != i):
                raise ValueError("original parking frame/time join differs")
        states = [row["state"] for row in activity]
        speeds = [row["speed_mps"] for row in activity]
        if any(type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0 for speed in speeds):
            raise ValueError("original parking speed missing")
        centers = [[sum(p[0] for p in row["polygon_m"]) / len(row["polygon_m"]),
                    sum(p[1] for p in row["polygon_m"]) / len(row["polygon_m"])]
                   for row in footprints]
        if any(not all(math.isfinite(value) for value in center) for center in centers):
            raise ValueError("original parking footprint center missing")
        path_m = sum(math.dist(a, b) for a, b in zip(centers, centers[1:]))
        parked = [i for i, state in enumerate(states) if state == "parked"]
        first_park = parked[0] if parked else None
        last_park = parked[-1] if parked else None
        ordered = (first_park is not None and
                   any(state == "approaching" for state in states[:first_park]) and
                   any(state == "stopping" for state in states[:first_park]) and
                   any(state == "departing" for state in states[last_park + 1:]))
        hold = len(parked) >= (3 if diagnostic else 400)
        stationary = all(speeds[i] <= .1 for i in parked)
        position = (measurement["max_access_intrusion_area_m2"] == 0 if
                    config["parking_position"] == "clear" else
                    measurement["max_access_intrusion_area_m2"] > 0)
        motion = path_m > (0 if diagnostic else 10)
        setup = _check("met", "complete original 20 Hz source/frame inventory", present,
                       {"frames": count, "diagnostic_fixture": diagnostic})
        target = _check("met" if position else "not_met",
                        "measured body/access overlap versus engineered target", present,
                        {"intrusion_area_m2": measurement["max_access_intrusion_area_m2"],
                         "requested_position": config["parking_position"],
                         "not_a_legal_blocking_cutoff": True})
        maneuver_met = ordered and hold and stationary and motion and position
        maneuver = _check("met" if maneuver_met else "not_met", method, present,
                          {"ordered_approach_stop_hold_depart": ordered,
                           "parked_frames": len(parked), "stationary_parked": stationary,
                           "sampled_body_path_m": path_m,
                           "engineering_hold_min_s": 20,
                           "not_a_legal_threshold": True})
        observables = {"access_intrusion_area_m2": {
            "value": measurement["max_access_intrusion_area_m2"], "unit": "m2",
            "method": "original body/access convex intersection", "time_window": "parked episode",
            "statistic": "max", "reference": "original-attempt/vehicle_footprint.json"},
            "sampled_body_path_m": {"value": path_m, "unit": "m",
                                    "method": "original frame-joined footprint centers",
                                    "time_window": "full episode", "statistic": "sum",
                                    "reference": "original-attempt/vehicle_footprint.json"}}
        return {"physical_checks": {"setup": setup, "target": target, "maneuver": maneuver},
                "setup_confirmed": True, "behavior_attempted": ordered,
                "maneuver_completed": maneuver_met, "realized_observables": observables}
    except (OSError, KeyError, TypeError, ValueError, IndexError, ZeroDivisionError) as error:
        unknown = _check("unverified", method, present, {"error": str(error)})
        return {"physical_checks": {name: unknown.copy() for name in ("setup", "target", "maneuver")},
                "setup_confirmed": False, "behavior_attempted": False,
                "maneuver_completed": False, "realized_observables": {}}
