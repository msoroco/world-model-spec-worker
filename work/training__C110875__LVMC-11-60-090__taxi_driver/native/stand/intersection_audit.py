"""Check first street-intersection ordering against a separately hashed route survey.

The diagnostic survey is authored. Original street identity, jurisdiction and
official stand/sign designation still require independent local source review.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def measure(actor_path: Path, route_path: Path, *, actor_sha256: str,
            route_sha256: str, expected_first_station_m: float = 80.0) -> dict:
    actor_raw, route_raw = actor_path.read_bytes(), route_path.read_bytes()
    if hashlib.sha256(actor_raw).hexdigest() != actor_sha256 or \
            hashlib.sha256(route_raw).hexdigest() != route_sha256:
        raise ValueError("saved actor or route-survey hash mismatch")
    route = json.loads(route_raw)
    if route.get("source_kind") != "synthetic_native_sample" or \
            route.get("route_survey_complete") is not False or \
            route.get("stand_exit_station_m") != 5.0:
        raise ValueError("route-survey source or authority changed")
    intersections = route.get("street_intersections")
    if not isinstance(intersections, list) or len(intersections) < 2:
        raise ValueError("first and later street intersections required")
    stations = []
    ids = []
    for entry in intersections:
        if (not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or
                not entry["id"] or type(entry.get("station_m")) not in (int, float) or
                entry.get("kind") != "street_intersection"):
            raise ValueError("invalid street-intersection survey entry")
        stations.append(float(entry["station_m"]))
        ids.append(entry["id"])
    if len(set(ids)) != len(ids) or stations != sorted(stations) or \
            any(s <= 5.0 for s in stations):
        raise ValueError("ambiguous or unordered street intersections")
    first = stations[0]
    if first != expected_first_station_m:
        raise ValueError("earlier or changed first street intersection")
    rows = [json.loads(line) for line in actor_raw.splitlines() if line.strip()]
    if len(rows) != 600:
        raise ValueError("full 600-frame actor source required")
    prev_x = None
    first_frame = None
    right_after = False
    straight_after = False
    for i, row in enumerate(rows):
        xy = row.get("ego_xy_m")
        if (row.get("frame") != i or not isinstance(xy, list) or len(xy) != 2 or
                type(xy[0]) not in (int, float) or type(xy[1]) not in (int, float) or
                row.get("time_s") != (i + 1) / 20):
            raise ValueError("saved actor/frame route join failed")
        x, y = xy
        if first_frame is None:
            if prev_x is not None and (x < prev_x or x - prev_x > 0.26):
                raise ValueError("approach route discontinuity")
            if x < first and y != 0:
                raise ValueError("actor left approach before first intersection")
            if x >= first:
                first_frame = i
        else:
            right_after |= x == first and y < 0 and row.get("heading_deg") == -90
            straight_after |= x > first and y == 0 and row.get("heading_deg") == 0
        prev_x = x
    if first_frame is None or right_after == straight_after:
        raise ValueError("first-intersection path contrast not observed")
    return {"format": "c110875-first-intersection-source-v1",
            "actor_sha256": actor_sha256, "route_sha256": route_sha256,
            "survey_first_intersection_id": ids[0],
            "survey_first_station_m": first, "later_station_m": stations[1],
            "observed_first_approach_frame": first_frame,
            "observed_departure": "right" if right_after else "straight",
            "route_survey_complete": False, "original_street_identity_verified": False,
            "legal_verdict": None}
