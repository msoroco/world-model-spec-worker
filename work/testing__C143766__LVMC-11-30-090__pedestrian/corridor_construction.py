"""Portable engineering corridor for the selected sidewalk and trail branch.

Coordinates are an authored CPU candidate, not a reviewed municipal map.
"""
from __future__ import annotations

import math

from corridor_map import BANDS, map_sha256
ROUTES = {"roadway": 1.5, "shoulder": 3.5, "sidewalk": 5.0}


def make_scene(case_id, route_band):
    if route_band not in ROUTES:
        raise ValueError("unknown pedestrian route band")
    y = ROUTES[route_band]
    scene = {
        "case_id": case_id,
        "map_kind": "authored_cpu_candidate",
        "map_source_sha256": map_sha256(),
        "bounds_xy_m": {name: [0.0, low, 30.0, high] for name, (low, high) in BANDS.items()},
        "sidewalk_provided_claim": "authored_geometry_only",
        "sidewalk_adjacent_to_roadway": True,
        "trail_access_status": "unreviewed_nonmotorized_context",
        "pedestrian_route_xy_m": [[2.0, y], [15.0, y], [28.0, y]],
        "pedestrian_body_half_width_m": 0.25,
        "route_band": route_band,
        "legal_judgment": "unresolved",
        "physical_acceptance_claimed": False,
    }
    validate_scene(scene)
    return scene


def validate_scene(scene):
    if scene.get("map_source_sha256") != map_sha256():
        raise ValueError("authored corridor map source hash differs")
    bounds = scene["bounds_xy_m"]
    if set(bounds) != set(BANDS):
        raise ValueError("roadway, shoulder, sidewalk, buffer and trail required")
    bands = sorted((rect[1], rect[3], name) for name, rect in bounds.items())
    if any(low >= high for low, high, _ in bands):
        raise ValueError("empty corridor band")
    for (_, high, _), (low, _, _) in zip(bands, bands[1:]):
        if abs(high-low) > 1e-9:
            raise ValueError("corridor bands have an overlap or gap")
    if [name for _, _, name in bands] != ["roadway", "shoulder", "sidewalk", "buffer", "nonmotorized_trail"]:
        raise ValueError("sidewalk is not adjacent to shoulder and roadway")
    route = scene["pedestrian_route_xy_m"]
    half = scene["pedestrian_body_half_width_m"]
    if len(route) < 3 or not 0 < half < .5:
        raise ValueError("invalid pedestrian route or body width")
    if any(not all(math.isfinite(v) for v in point) for point in route):
        raise ValueError("nonfinite route point")
    if any(b[0] <= a[0] for a, b in zip(route, route[1:])):
        raise ValueError("pedestrian route does not walk along corridor")
    target = bounds[scene["route_band"]]
    if any(not (target[0] <= x <= target[2] and target[1] <= y-half and y+half <= target[3])
           for x, y in route):
        raise ValueError("pedestrian body leaves its authored route band")
    if scene["legal_judgment"] != "unresolved" or scene["physical_acceptance_claimed"]:
        raise ValueError("engineering candidate cannot claim legal or physical acceptance")
    return True


def request_next_target(scene, x, y, target_index=1):
    """Return a walker target request; original movement is audited separately."""
    validate_scene(scene)
    route = scene["pedestrian_route_xy_m"]
    if not 1 <= target_index < len(route):
        raise ValueError("invalid target index")
    if math.hypot(x-route[target_index][0], y-route[target_index][1]) < .5 and target_index < len(route)-1:
        target_index += 1
    tx, ty = route[target_index]
    distance = math.hypot(tx-x, ty-y)
    return {"target_index": target_index, "target_xy_m": [tx, ty],
            "direction_xy": [0.0, 0.0] if distance == 0 else [(tx-x)/distance, (ty-y)/distance],
            "speed_mps": 0.0 if distance < .5 and target_index == len(route)-1 else 1.2}


def measure_original(scene, frames):
    """Classify original full-body footprints, without deciding legal sufficiency."""
    validate_scene(scene)
    if len(frames) < 3 or [f["frame"] for f in frames] != list(range(frames[0]["frame"], frames[0]["frame"]+len(frames))):
        raise ValueError("missing or stale original frames")
    counts = {name: 0 for name in BANDS}
    centers = []
    times = []
    for f in frames:
        time_s = float(f["time_s"])
        if not math.isfinite(time_s):
            raise ValueError("nonfinite original frame time")
        times.append(time_s)
        body = f["body_xy_m"]
        if len(body) != 4 or any(len(point) != 2 for point in body):
            raise ValueError("original full-body polygon required")
        if not all(math.isfinite(v) for point in body for v in point):
            raise ValueError("nonfinite original body")
        xs = [p[0] for p in body]
        ys = [p[1] for p in body]
        centers.append((sum(xs)/4, sum(ys)/4))
        covered = False
        for name, (low, high) in BANDS.items():
            if max(xs) >= 0 and min(xs) <= 30 and max(ys) >= low and min(ys) <= high:
                counts[name] += 1
                covered = True
        if not covered:
            raise ValueError("original pedestrian body is outside corridor")
    if any(b[0] <= a[0] for a, b in zip(centers, centers[1:])):
        raise ValueError("original pedestrian did not progress along corridor")
    if any(abs((b-a)-.05) > .005 for a, b in zip(times, times[1:])):
        raise ValueError("original frame timing is not 20 Hz")
    speeds = [(b[0]-a[0])/(tb-ta) for a, b, ta, tb in
              zip(centers, centers[1:], times, times[1:])]
    if any(speed > 2.0 for speed in speeds):
        raise ValueError("original pedestrian motion exceeds engineering speed envelope")
    endpoint = scene["pedestrian_route_xy_m"][-1]
    reached_endpoint = math.hypot(centers[-1][0]-endpoint[0],
                                  centers[-1][1]-endpoint[1]) <= .5
    return {"frames": len(frames), "band_overlap_frame_counts": counts,
            "first_center_xy_m": list(centers[0]), "last_center_xy_m": list(centers[-1]),
            "duration_s": times[-1]-times[0], "maximum_forward_speed_mps": max(speeds),
            "authored_endpoint_reached": reached_endpoint,
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}


def compare_authored_routes(first, second, declared_band_change):
    """Isolate the lateral route request in two engineering scenes."""
    validate_scene(first)
    validate_scene(second)
    if first["bounds_xy_m"] != second["bounds_xy_m"]:
        raise ValueError("corridor geometry changed")
    if first["map_source_sha256"] != second["map_source_sha256"]:
        raise ValueError("corridor map source changed")
    for key in ("sidewalk_provided_claim", "sidewalk_adjacent_to_roadway",
                "trail_access_status", "pedestrian_body_half_width_m"):
        if first[key] != second[key]:
            raise ValueError("fixed corridor context changed")
    if not declared_band_change or first["route_band"] == second["route_band"]:
        raise ValueError("lateral route change was not declared and realized")
    xs1 = [point[0] for point in first["pedestrian_route_xy_m"]]
    xs2 = [point[0] for point in second["pedestrian_route_xy_m"]]
    if xs1 != xs2:
        raise ValueError("longitudinal route changed")
    return {"fixed_corridor_and_longitudinal_route": True,
            "changed_route_bands": [first["route_band"], second["route_band"]],
            "realized_movement_claimed": False, "legal_judgment": "unresolved"}
