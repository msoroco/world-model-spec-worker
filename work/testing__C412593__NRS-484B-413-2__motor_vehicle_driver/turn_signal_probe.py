"""Source-bound distance and continuous-signal probe for NRS 484B.413(2)."""

from math import hypot, isfinite


FEET_TO_METERS = 0.3048


def required_distance_m(district):
    if district in ("business", "residential"):
        return 100 * FEET_TO_METERS
    if district == "other":
        return 300 * FEET_TO_METERS
    raise ValueError("district class is not source-bound")


def measure(context, frames):
    required_context = {"district", "district_source", "weather_source",
                        "maneuver", "route_source", "vehicle_id"}
    if required_context - context.keys() or not all(context[k] for k in
                                                   ("district_source", "weather_source",
                                                    "route_source", "vehicle_id")):
        raise ValueError("missing district, route or weather source")
    required = {"original_frame", "time_s", "xy", "signal", "course_changed",
                "motion_source", "signal_source", "vehicle_id"}
    if len(frames) < 3 or any(required - f.keys() or not f["motion_source"] or
                              not f["signal_source"] for f in frames):
        raise ValueError("missing original motion or signal history")
    if any(f["vehicle_id"] != context["vehicle_id"] for f in frames):
        raise ValueError("vehicle source mismatch")
    if any(frames[i + 1]["original_frame"] != frames[i]["original_frame"] + 1 or
           abs((frames[i + 1]["time_s"] - frames[i]["time_s"]) - 0.05) > 0.001
           for i in range(len(frames) - 1)):
        raise ValueError("original 20 Hz frame/time join missing or nonconsecutive")
    if any(len(f["xy"]) != 2 or not all(isfinite(v) for v in f["xy"]) for f in frames):
        raise ValueError("invalid route coordinate")
    turns = [i for i, f in enumerate(frames) if f["course_changed"]]
    if len(turns) != 1:
        raise ValueError("exact course-change onset required")
    turn = turns[0]
    if turn == 0:
        raise ValueError("missing pre-turn route")
    expected_signal = {"right_turn": "right", "left_turn": "left",
                       "other_turn": context.get("intended_signal")}.get(context["maneuver"])
    if expected_signal not in ("right", "left"):
        raise ValueError("unresolved intended signal")
    distances = [0.0]
    for i in range(1, turn + 1):
        distances.append(distances[-1] + hypot(frames[i]["xy"][0] - frames[i - 1]["xy"][0],
                                                frames[i]["xy"][1] - frames[i - 1]["xy"][1]))
    continuous_start = turn
    if frames[turn]["signal"] == expected_signal:
        while continuous_start > 0 and frames[continuous_start - 1]["signal"] == expected_signal:
            continuous_start -= 1
    continuous_distance = distances[turn] - distances[continuous_start]
    required_distance = required_distance_m(context["district"])
    return {"course_change_original_frame": frames[turn]["original_frame"],
            "continuous_start_original_frame": frames[continuous_start]["original_frame"],
            "continuous_signal_distance_m": continuous_distance,
            "required_distance_m": required_distance,
            "distance_floor_observed": continuous_distance >= required_distance,
            "weather": context.get("weather"),
            "source_refs": sorted(set([context["district_source"], context["weather_source"],
                                       context["route_source"]] +
                                      [f[k] for f in frames for k in ("motion_source", "signal_source")]))}
