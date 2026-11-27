"""Descriptive, source-bound bridge-approach measurements; no legal verdict."""
from __future__ import annotations

import math

FEET_100_M = 30.48


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"missing finite {name}")
    return float(value)


def measure(packet):
    road = packet["road"]
    if road.get("structure_type") != "bridge":
        raise ValueError("reviewed bridge identity required")
    entrance = _number(road.get("bridge_entrance_station_m"), "bridge entrance station")
    if road.get("one_way_highway") not in (True, False):
        raise ValueError("reviewed one-way highway status required")
    if not road.get("centerline_source_sha256") or not road.get("bridge_source_sha256"):
        raise ValueError("reviewed centerline and bridge sources required")
    frames = packet["frames"]
    if not frames:
        raise ValueError("original body and ray history required")
    output = []
    prior = None
    for index, row in enumerate(frames):
        if row.get("original_frame") != index:
            raise ValueError("original frame discontinuity")
        time_s = _number(row.get("time_s"), "original time")
        if prior is not None and time_s <= prior:
            raise ValueError("original time not increasing")
        prior = time_s
        ego = row.get("actors", {}).get("ego", {})
        front = _number(ego.get("front_station_m"), "ego front station")
        rear = _number(ego.get("rear_station_m"), "ego rear station")
        center = _number(ego.get("station_m"), "ego center station")
        if not rear <= center <= front:
            raise ValueError("ego body station ordering invalid")
        left_edge = _number(ego.get("centerline_signed_body_edge_m"), "ego left body edge")
        rays = row.get("left_side_rays")
        if not isinstance(rays, list) or not rays:
            raise ValueError("original view rays required")
        ray_values = []
        for ray in rays:
            length = _number(ray.get("clear_distance_m"), "ray distance")
            if length < 0 or ray.get("censored") not in (True, False):
                raise ValueError("invalid original ray bracket")
            ray_values.append({"clear_distance_m": length, "censored": ray["censored"],
                               "hit_kind": ray.get("hit_kind")})
        output.append({"original_frame": index, "time_s": time_s,
                       "bridge_distance_front_m": entrance-front,
                       "bridge_distance_center_m": entrance-center,
                       "bridge_distance_rear_m": entrance-rear,
                       "within_100ft_front_reference": -1e-9 <= entrance-front <= FEET_100_M+1e-9,
                       "left_body_edge_m": left_edge,
                       "left_of_center_body": left_edge > 0,
                       "ray_brackets": ray_values})
    return {"law_id": "NRS-484B-213-2c", "statutory_distance_m": FEET_100_M,
            "distance_reference_unresolved": "front, center and rear retained for review",
            "one_way_highway": road["one_way_highway"],
            "bridge_entrance_station_m": entrance,
            "per_frame": output, "view_obstructed_judgment": "unresolved",
            "legal_result": "unresolved"}
