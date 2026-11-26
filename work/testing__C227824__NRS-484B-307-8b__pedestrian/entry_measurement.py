"""Saved-source measurement of pedestrian entry while facing a steady red signal.

This module measures source events. It does not decide legal permission or infer
that an authored signal/device was visible in the recorded pixels.
"""
from __future__ import annotations

import math


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("expected a two-coordinate point")
    pair = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in pair):
        raise ValueError("nonfinite point")
    return pair


def _polygon(value):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("polygon needs at least three vertices")
    return [_point(v) for v in value]


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p):
    return abs(_orient(a, b, p)) <= 1e-9 and min(a[0], b[0]) - 1e-9 <= p[0] <= max(a[0], b[0]) + 1e-9 and min(a[1], b[1]) - 1e-9 <= p[1] <= max(a[1], b[1]) + 1e-9


def _segments_meet(a, b, c, d):
    x, y, z, w = (_orient(a, b, c), _orient(a, b, d),
                  _orient(c, d, a), _orient(c, d, b))
    if (x > 0 > y or y > 0 > x) and (z > 0 > w or w > 0 > z):
        return True
    return any((_on_segment(a, b, c), _on_segment(a, b, d),
                _on_segment(c, d, a), _on_segment(c, d, b)))


def _contains(polygon, point):
    inside = False
    for index, a in enumerate(polygon):
        b = polygon[(index + 1) % len(polygon)]
        if _on_segment(a, b, point):
            return True
        if (a[1] > point[1]) != (b[1] > point[1]):
            x = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < x:
                inside = not inside
    return inside


def polygons_overlap(first, second):
    """Boundary contact counts as entry; the highway includes its boundary."""
    a, b = _polygon(first), _polygon(second)
    if any(_contains(b, p) for p in a) or any(_contains(a, p) for p in b):
        return True
    return any(_segments_meet(a[i], a[(i + 1) % len(a)], b[j], b[(j + 1) % len(b)])
               for i in range(len(a)) for j in range(len(b)))


def measure_entry(rows, highway_polygon):
    """Return first full-body entry event from original synchronized samples.

    Each row must carry the source frame, time, body outline, facing traffic
    signal, and inventory of other governing devices. Missing indication data
    fails closed. The first row must be wholly outside the highway.
    """
    highway = _polygon(highway_polygon)
    if not rows:
        raise ValueError("original frame samples missing")
    previous_frame = -1
    previous_time = -math.inf
    first_entry = None
    first_clear_after_entry = None
    first_countdown_zero = None
    outside_initially = False
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("invalid original frame sample")
        frame = row.get("frame")
        time_s = row.get("time_s")
        if not isinstance(frame, int) or isinstance(frame, bool) or frame <= previous_frame:
            raise ValueError("frames must be strictly increasing")
        if not isinstance(time_s, (float, int)) or not math.isfinite(time_s) or time_s <= previous_time:
            raise ValueError("times must be strictly increasing")
        previous_frame, previous_time = frame, time_s
        overlap = polygons_overlap(row.get("body_polygon_xy_m"), highway)
        if index == 0:
            outside_initially = not overlap
            if not outside_initially:
                raise ValueError("first original body sample is already inside highway")
        traffic = row.get("facing_traffic_signal")
        if not isinstance(traffic, dict) or traffic.get("indication") not in {"steady_red_alone", "other"} or traffic.get("official") is not True:
            raise ValueError("facing official traffic signal source missing")
        devices = row.get("other_devices")
        if not isinstance(devices, list):
            raise ValueError("other governing device inventory missing")
        for device in devices:
            if not isinstance(device, dict) or device.get("indication") not in {"walk", "flashing_hand_countdown", "flashing_hand_no_countdown", "steady_hand", "other"} or not isinstance(device.get("official"), bool):
                raise ValueError("other device indication source missing")
            if device["indication"] == "flashing_hand_countdown":
                count = device.get("countdown_s")
                if not isinstance(count, (int, float)) or not math.isfinite(count) or count < 0:
                    raise ValueError("countdown source missing")
                if count == 0 and first_countdown_zero is None:
                    first_countdown_zero = {"frame": frame, "time_s": time_s}
        if overlap and first_entry is None:
            first_entry = {"frame": frame, "time_s": time_s,
                           "facing_traffic_signal": traffic.copy(),
                           "other_devices": [d.copy() for d in devices]}
        if first_entry is not None and not overlap and first_clear_after_entry is None:
            first_clear_after_entry = {"frame": frame, "time_s": time_s}
    return {"outside_highway_at_start": outside_initially,
            "first_entry": first_entry,
            "first_clear_after_entry": first_clear_after_entry,
            "first_countdown_zero": first_countdown_zero,
            "cleared_before_countdown_zero": (
                first_clear_after_entry["frame"] < first_countdown_zero["frame"]
                if first_clear_after_entry is not None and first_countdown_zero is not None
                else None),
            "entry_observed": first_entry is not None,
            "sample_count": len(rows),
            "measurement_only": True,
            "legal_permission_determined": False}


def measure_walking_speed(rows, *, start_s=6.0, end_s=12.0):
    """Mean observed body-center speed after startup from original 20 Hz rows.

    Returns None when a short diagnostic source cannot cover the evaluation
    window. Setpoints and legal permission are not inferred from this value.
    """
    if not rows:
        raise ValueError("original walker body history missing")
    origin = rows[0].get("time_s")
    if type(origin) not in (float, int) or not math.isfinite(origin):
        raise ValueError("original walker time missing")
    selected = []
    previous_frame = -1
    for row in rows:
        frame, time_s = row.get("frame"), row.get("time_s")
        if type(frame) is not int or frame <= previous_frame or type(time_s) not in (float, int) or not math.isfinite(time_s):
            raise ValueError("original walker frame/time invalid")
        previous_frame = frame
        polygon = _polygon(row.get("body_polygon_xy_m"))
        center = (sum(p[0] for p in polygon) / len(polygon),
                  sum(p[1] for p in polygon) / len(polygon))
        elapsed = time_s - origin
        if start_s <= elapsed <= end_s:
            selected.append((frame, time_s, center))
    if len(selected) < 3 or selected[-1][1] - selected[0][1] < 1.0:
        return None
    speeds = []
    for previous, current in zip(selected, selected[1:]):
        if current[0] != previous[0] + 1 or abs((current[1] - previous[1]) - .05) > .005:
            raise ValueError("original walker speed window has a frame/time gap")
        speeds.append(math.dist(current[2], previous[2]) / (current[1] - previous[1]))
    return {"value": sum(speeds) / len(speeds), "unit": "m/s", "statistic": "mean",
            "method": "original 20 Hz walker body-center displacement",
            "time_window": "original seconds 6 through 12 excluding startup transient",
            "sample_window_s": [selected[1][1], selected[-1][1]],
            "first_frame": selected[0][0], "last_frame": selected[-1][0],
            "sample_count": len(speeds), "legal_permission_determined": False}
