"""CPU observations for the selected NRS 484B.267(2)(c) movement branch.

The probe records visible movement and driver response without creating an
unsupported legal threshold for preparedness or requiring an actual stop.
"""

from math import hypot, isfinite


def measure(site, frames):
    required_site = {"ego_id", "emergency_id", "emergency_class",
                     "authorization_source", "qualifying_lights_source",
                     "light_rule_source", "route_source", "officer_direction_source"}
    if required_site - site.keys() or not all(site[k] for k in
                                          ("ego_id", "emergency_id", "authorization_source",
                                           "qualifying_lights_source", "light_rule_source",
                                           "route_source", "officer_direction_source")):
        raise ValueError("missing emergency authority or route source")
    if site["ego_id"] == site["emergency_id"]:
        raise ValueError("approaching vehicle must be distinct")
    if site["emergency_class"] not in ("authorized_emergency", "regulatory_official"):
        raise ValueError("unqualified vehicle class")
    required = {"original_frame", "time_s", "ego_xy", "emergency_xy",
                "flashing_light_on", "movement_visible", "ego_speed_mps",
                "ego_brake", "officer_direction", "motion_source",
                "light_source", "visibility_source", "control_source"}
    if len(frames) < 4 or any(required - f.keys() for f in frames):
        raise ValueError("missing original motion, light or control history")
    if any(not all(f[k] for k in ("motion_source", "light_source",
                                     "visibility_source", "control_source")) for f in frames):
        raise ValueError("unbound original source")
    if any(frames[i]["original_frame"] >= frames[i + 1]["original_frame"] or
           frames[i]["time_s"] >= frames[i + 1]["time_s"]
           for i in range(len(frames) - 1)):
        raise ValueError("nonmonotone original frames")
    if any(not 0 <= f["ego_brake"] <= 1 or f["ego_speed_mps"] < 0 or
           not all(isfinite(v) for v in (*f["ego_xy"], *f["emergency_xy"]))
           for f in frames):
        raise ValueError("invalid physical sample")
    moving = [i for i in range(1, len(frames)) if
              hypot(frames[i]["emergency_xy"][0] - frames[i - 1]["emergency_xy"][0],
                    frames[i]["emergency_xy"][1] - frames[i - 1]["emergency_xy"][1]) > 0]
    visible_movement = [i for i in moving if frames[i]["movement_visible"]]
    if not visible_movement:
        raise ValueError("visible actual vehicle movement not established")
    if not any(f["flashing_light_on"] for f in frames):
        raise ValueError("qualifying flashing-light use not observed")
    approaching = [i for i in visible_movement if
                   hypot(*tuple(frames[i]["ego_xy"][j] - frames[i]["emergency_xy"][j]
                                for j in (0, 1))) <
                   hypot(*tuple(frames[0]["ego_xy"][j] - frames[0]["emergency_xy"][j]
                                for j in (0, 1)))]
    if not approaching:
        raise ValueError("approach during visible movement not established")
    return {
        "visible_movement_original_frames": [frames[i]["original_frame"] for i in approaching],
        "brake_observations_after_cue": [(f["original_frame"], f["ego_brake"])
                                        for f in frames[approaching[0]:]],
        "officer_directions": [(f["original_frame"], f["officer_direction"])
                               for f in frames if f["officer_direction"]],
        "prepared_to_stop": "unresolved",
        "actual_stop_required_by_clause": False,
        "source_refs": sorted(set(f[k] for f in frames for k in
                                  ("motion_source", "light_source", "visibility_source", "control_source"))),
    }
