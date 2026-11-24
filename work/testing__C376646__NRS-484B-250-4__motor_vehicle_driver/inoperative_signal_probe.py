"""CPU source-bound observations for NRS 484B.250(4).

Engineering observations do not decide whether a driver proceeded cautiously.
"""

from math import isfinite


def stop_reference(site):
    required = {"installed_signal_id", "governed_approach", "stop_line_m",
                "near_crosswalk_m", "nearest_view_point_m", "intersection_entry_m",
                "through_highway_source", "sightline_source"}
    if required - site.keys() or not all(site[k] for k in
                                         ("installed_signal_id", "governed_approach",
                                          "through_highway_source", "sightline_source")):
        raise ValueError("missing installed signal or surveyed intersection context")
    if site["stop_line_m"] is not None:
        return "stop_line", site["stop_line_m"]
    if site["near_crosswalk_m"] is not None:
        return "near_crosswalk", site["near_crosswalk_m"]
    if site["nearest_view_point_m"] is None:
        raise ValueError("missing nearest-view stopping point")
    return "nearest_view_point", site["nearest_view_point_m"]


def measure(site, ego_frames, other_frames):
    kind, reference = stop_reference(site)
    if len(ego_frames) < 3:
        raise ValueError("missing original ego history")
    required = {"original_frame", "time_s", "front_m", "speed_mps", "signal_id",
                "signal_uncovered", "signal_operating", "approach_id", "source_ref"}
    if any(required - f.keys() or not f["source_ref"] for f in ego_frames):
        raise ValueError("missing bound ego or signal source")
    if any(ego_frames[i]["original_frame"] >= ego_frames[i + 1]["original_frame"] or
           ego_frames[i]["time_s"] >= ego_frames[i + 1]["time_s"]
           for i in range(len(ego_frames) - 1)):
        raise ValueError("nonmonotone original ego frames")
    if any(not isfinite(f["front_m"]) or not isfinite(f["speed_mps"]) or
           f["speed_mps"] < 0 for f in ego_frames):
        raise ValueError("invalid ego motion")
    if any(f["signal_id"] != site["installed_signal_id"] or
           f["approach_id"] != site["governed_approach"] for f in ego_frames):
        raise ValueError("signal governance mismatch")
    entry = next((f for f in ego_frames if f["front_m"] >= site["intersection_entry_m"]), None)
    if entry is None:
        raise ValueError("intersection entry not observed")
    if not entry["signal_uncovered"] or entry["signal_operating"]:
        raise ValueError("uncovered inoperative signal at entry not established")
    stopped = [f for f in ego_frames if f["speed_mps"] == 0 and f["front_m"] <= reference]
    first_stop = stopped[0] if stopped else None
    required_other = {"vehicle_id", "original_frame", "time_s", "completed_stop_time_s",
                      "within_intersection", "source_ref"}
    if any(required_other - f.keys() or not f["source_ref"] for f in other_frames):
        raise ValueError("missing bound interacting vehicle history")
    if any(f["vehicle_id"] == site.get("ego_id") for f in other_frames):
        raise ValueError("interacting vehicle must be distinct")
    priority_others = [f["vehicle_id"] for f in other_frames
                       if (f["completed_stop_time_s"] is not None and first_stop is not None
                           and f["completed_stop_time_s"] < first_stop["time_s"])
                       or f["within_intersection"]]
    return {"reference_kind": kind, "reference_m": reference,
            "stop_original_frame": None if first_stop is None else first_stop["original_frame"],
            "entry_original_frame": entry["original_frame"],
            "prior_stop_or_within_intersection_vehicle_ids": sorted(set(priority_others)),
            "cautious_proceeding": "unresolved",
            "source_refs": sorted(set(f["source_ref"] for f in (*ego_frames, *other_frames)))}
