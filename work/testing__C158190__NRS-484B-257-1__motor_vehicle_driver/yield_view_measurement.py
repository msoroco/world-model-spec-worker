"""Original-frame measurements for the no-line/no-crosswalk yield branch.

This reports the nearest sampled view station, ego slowdown, and through
traffic encounter. It does not invent an immediate-hazard time cutoff.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C158190__NRS-484B-257-1__motor_vehicle_driver"


def measure(path: str | Path) -> dict:
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("original_trace_id"):
        raise ValueError("original assignment and trace identity required")
    site = packet.get("site")
    if not isinstance(site, dict) or site.get("control") != "yield_sign":
        raise ValueError("original yield sign site required")
    if site.get("stop_line_present") is not False or site.get("near_crosswalk_present") is not False:
        raise ValueError("this branch requires no stop line and no near crosswalk")
    if site.get("police_control_active") is not False or site.get("traffic_signal_control_active") is not False:
        raise ValueError("police and traffic-signal exception state required")
    stations = site.get("approach_view_stations")
    if not isinstance(stations, list) or not stations:
        raise ValueError("original approach view stations required")
    visible = []
    for s in stations:
        if not isinstance(s.get("view_of_through_traffic"), bool):
            raise ValueError("view readback required at every station")
        distance = s.get("distance_to_intersection_m")
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance) or distance < 0:
            raise ValueError("finite nonnegative station distance required")
        if not s.get("station_id"):
            raise ValueError("station identity required")
        if s["view_of_through_traffic"]:
            visible.append(s)
    if not visible:
        raise ValueError("no through-traffic view station")
    nearest = min(visible, key=lambda s: s["distance_to_intersection_m"])
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original motion frames required")
    for i, f in enumerate(frames):
        for key in ("time_s", "ego_speed_mps", "distance_to_intersection_m"):
            v = f.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"original finite {key} required")
        if i and not 0 < f["time_s"] - frames[i - 1]["time_s"] <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        if not isinstance(f.get("ego_within_intersection"), bool):
            raise ValueError("original intersection occupancy required")
        if not isinstance(f.get("through_vehicle_ids"), list):
            raise ValueError("original through vehicle identities required")
    entry = next((i for i, f in enumerate(frames) if f["ego_within_intersection"]), None)
    if entry is None or entry == 0:
        raise ValueError("original intersection entry bracket required")
    before = frames[:entry]
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "nearest_visible_station_id": nearest["station_id"],
            "nearest_visible_station_distance_m": nearest["distance_to_intersection_m"],
            "entry_bracket_indices": [entry - 1, entry],
            "minimum_pre_entry_speed_mps": min(f["ego_speed_mps"] for f in before),
            "speed_reduction_before_entry_mps": before[0]["ego_speed_mps"] - min(f["ego_speed_mps"] for f in before),
            "through_vehicle_ids_at_entry": frames[entry]["through_vehicle_ids"],
            "review_limit": "Observed slowdown and nearest sampled view do not establish that the legal yield point or immediate-hazard duty was satisfied; inspect original through-vehicle motion during crossing."}
