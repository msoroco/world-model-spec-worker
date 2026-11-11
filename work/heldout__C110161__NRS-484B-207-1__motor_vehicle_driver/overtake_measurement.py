"""Measure original-frame left-pass clearance and return order.

These are physical observations for later review. No gap or time value is a
statutory definition of "safe distance" or "safely clear".
"""

from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


def _vector(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Missing original " + label)
    x, y = (float(part) for part in value)
    if not (isfinite(x) and isfinite(y)):
        raise ValueError("Nonfinite original " + label)
    length = hypot(x, y)
    if length < 1e-6:
        raise ValueError("Degenerate original " + label)
    return x / length, y / length


def _corners(row, key):
    value = row.get(key)
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("Missing four-corner original footprint: " + key)
    corners = [(float(x), float(y)) for x, y in value]
    if any(not (isfinite(x) and isfinite(y)) for x, y in corners):
        raise ValueError("Nonfinite original footprint: " + key)
    return corners


def _projection(corners, axis):
    values = [x * axis[0] + y * axis[1] for x, y in corners]
    return min(values), max(values)


def measure(source):
    path = Path(source)
    if not path.is_file():
        raise ValueError("Missing required source: participant_footprints.jsonl")
    raw = path.read_bytes()
    if not raw:
        raise ValueError("Empty original overtake source")
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid original overtake source") from error
    if len(rows) < 3:
        raise ValueError("Overtake needs approach, abreast and return frames")
    first_ids = (rows[0].get("ego_id"), rows[0].get("other_id"))
    if not all(first_ids) or first_ids[0] == first_ids[1]:
        raise ValueError("Overtake needs two stable actor identities")
    observations = []
    previous = None
    for index, row in enumerate(rows):
        if (row.get("ego_id"), row.get("other_id")) != first_ids:
            raise ValueError("Original participant identity changed")
        frame, time_s = row.get("frame"), row.get("time_s")
        if type(frame) is not int or type(time_s) not in (int, float):
            raise ValueError("Original frame/time identity missing")
        if not isfinite(time_s):
            raise ValueError("Nonfinite original frame time")
        if previous is not None and (frame != previous[0] + 1 or
                                     abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError("Original overtake frames are not joined at 20 Hz")
        previous = frame, time_s
        tangent = _vector(row.get("road_tangent_xy"), "road tangent")
        ego_heading = _vector(row.get("ego_heading_xy"), "ego heading")
        other_heading = _vector(row.get("other_heading_xy"), "other heading")
        if (ego_heading[0] * other_heading[0] + ego_heading[1] * other_heading[1] < .95
                or ego_heading[0] * tangent[0] + ego_heading[1] * tangent[1] < .95):
            raise ValueError("Actors are not observed proceeding in the same direction")
        left = -tangent[1], tangent[0]
        ego, other = _corners(row, "ego_corners"), _corners(row, "other_corners")
        ego_long, other_long = _projection(ego, tangent), _projection(other, tangent)
        ego_lat, other_lat = _projection(ego, left), _projection(other, left)
        abreast = ego_long[0] <= other_long[1] and other_long[0] <= ego_long[1]
        lateral_gap = ego_lat[0] - other_lat[1]
        ahead_clearance = ego_long[0] - other_long[1]
        ego_centre_lat = (ego_lat[0] + ego_lat[1]) / 2
        observations.append({"frame": frame, "time_s": time_s,
                             "abreast": abreast, "left_side_gap_m": lateral_gap,
                             "left_of_other": ego_centre_lat > (other_lat[0] + other_lat[1]) / 2,
                             "ahead_clearance_m": ahead_clearance,
                             "ego_centre_lateral_m": ego_centre_lat})
    active = [row for row in observations if row["abreast"]]
    if not active:
        raise ValueError("No observed abreast phase")
    if not any(row["ahead_clearance_m"] > 0 for row in observations):
        raise ValueError("Trace ends before subject is completely ahead")
    first_abreast = min(i for i, row in enumerate(observations) if row["abreast"])
    returns = [observations[i] for i in range(first_abreast + 1, len(observations))
               if observations[i]["ego_centre_lateral_m"] < observations[i - 1]["ego_centre_lateral_m"] - .1]
    if not returns:
        raise ValueError("No measured rightward return after passing")
    return {"format": "worker-overtake-observation",
            "source_sha256": sha256(raw).hexdigest(),
            "actor_ids": list(first_ids), "frame_count": len(rows),
            "abreast_frames": [row["frame"] for row in active],
            "all_abreast_left": all(row["left_of_other"] for row in active),
            "min_abreast_lateral_gap_m": min(row["left_side_gap_m"] for row in active),
            "first_return_frame": returns[0]["frame"],
            "clearance_at_first_return_m": returns[0]["ahead_clearance_m"],
            "observations": observations,
            "legal_acceptance_claimed": False}
