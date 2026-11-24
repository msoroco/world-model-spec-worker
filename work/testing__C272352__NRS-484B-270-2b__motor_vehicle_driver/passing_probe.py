"""Source-bound geometry observations for NRS 484B.270(2)(b).

The clearance floor is statutory. Safe distance, due care, safely clear and
incorporated passing exceptions still require independent review.
"""

from math import hypot, isfinite


THREE_FEET_M = 0.9144


def rectangle_gap(a, b):
    """Shortest Euclidean gap between closed axis-aligned body envelopes."""
    if len(a) != 4 or len(b) != 4 or any(not isfinite(x) for x in (*a, *b)):
        raise ValueError("invalid body envelope")
    if a[0] > a[1] or a[2] > a[3] or b[0] > b[1] or b[2] > b[3]:
        raise ValueError("reversed body envelope")
    dx = max(a[0] - b[1], b[0] - a[1], 0)
    dy = max(a[2] - b[3], b[2] - a[3], 0)
    return hypot(dx, dy)


def measure_pass(site, frames):
    """Measure same-direction left pass, body gap and return ordering.

    Each saved frame binds original motion, lane and bicycle identity packets.
    Envelopes are (rear_x, front_x, right_y, left_y) in surveyed route axes.
    """
    required_site = {"highway_source", "lane_count_same_direction", "centerline_y",
                     "right_side_y", "vehicle_id", "bicycle_id", "bicycle_kind"}
    if required_site - site.keys() or not site["highway_source"]:
        raise ValueError("missing surveyed highway or participant context")
    if site["lane_count_same_direction"] != 1:
        raise ValueError("single same-direction lane not established")
    if site["bicycle_kind"] not in ("bicycle", "electric_bicycle", "electric_scooter"):
        raise ValueError("qualifying bicycle or scooter identity absent")
    if site["vehicle_id"] == site["bicycle_id"]:
        raise ValueError("participants must be distinct")
    required_frame = {"original_frame", "time_s", "vehicle_box", "bicycle_box",
                      "vehicle_speed_mps", "bicycle_speed_mps", "vehicle_source",
                      "bicycle_source", "lane_source"}
    if len(frames) < 3 or any(required_frame - f.keys() for f in frames):
        raise ValueError("missing original participant history")
    if any(not all(f[k] for k in ("vehicle_source", "bicycle_source", "lane_source"))
           for f in frames):
        raise ValueError("unbound original source")
    if any(frames[i]["original_frame"] >= frames[i + 1]["original_frame"] or
           frames[i]["time_s"] >= frames[i + 1]["time_s"]
           for i in range(len(frames) - 1)):
        raise ValueError("original frame history not monotone")
    if any(f["vehicle_speed_mps"] < 0 or f["bicycle_speed_mps"] < 0
           for f in frames):
        raise ValueError("speed direction missing")
    gaps = [rectangle_gap(f["vehicle_box"], f["bicycle_box"]) for f in frames]
    passing = [i for i, f in enumerate(frames)
               if f["vehicle_box"][1] >= f["bicycle_box"][0]
               and f["vehicle_box"][0] <= f["bicycle_box"][1]]
    if not passing:
        raise ValueError("no longitudinal passing overlap")
    left_during_overlap = all(frames[i]["vehicle_box"][2] > frames[i]["bicycle_box"][3]
                              for i in passing)
    return_indices = [i for i, f in enumerate(frames)
                      if i > passing[0] and f["vehicle_box"][2] <= site["right_side_y"]]
    first_return = return_indices[0] if return_indices else None
    clear_before_return = first_return is None or (
        frames[first_return]["vehicle_box"][0] >
        frames[first_return]["bicycle_box"][1])
    return {
        "minimum_body_gap_m": min(gaps[i] for i in passing),
        "three_foot_floor_observed": all(gaps[i] >= THREE_FEET_M for i in passing),
        "left_during_overlap": left_during_overlap,
        "passing_original_frames": [frames[i]["original_frame"] for i in passing],
        "first_return_original_frame": None if first_return is None else frames[first_return]["original_frame"],
        "longitudinal_clear_before_return": clear_before_return,
        "incorporated_exceptions": "unresolved",
        "safe_distance_and_due_care": "unresolved",
    }
