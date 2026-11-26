"""Record original Native sight rays without assigning a legal visibility result."""
import math


def xyz(location):
    return [float(location.x), float(location.y), float(location.z)]


def distance(a, b):
    return math.dist(xyz(a), xyz(b))


def sample_approaches(junction, lane_type):
    """Choose 0/50/100-foot points on every unique entering driving lane."""
    samples = {}
    for entry, _ in junction.get_waypoints(lane_type):
        key = f"{entry.road_id}:{entry.lane_id}"
        if key in samples:
            continue
        points = []
        for feet, meters in ((0, 0.0), (50, 15.24), (100, 30.48)):
            choices = [entry] if not meters else entry.previous(meters)
            if len(choices) != 1:
                raise ValueError(f"unresolved entering lane geometry: {key}:{feet}ft")
            points.append({"distance_from_intersection_ft": feet,
                           "xyz_m": xyz(choices[0].transform.location)})
        samples[key] = points
    if len(samples) < 2:
        raise ValueError("fewer than two entering driving approaches")
    return samples


def original_rays(world, carla, eye, targets):
    """Retain every hit on each ray for independent source review."""
    rows = []
    for target in targets:
        endpoint = carla.Location(x=target[0], y=target[1], z=target[2])
        hits = world.cast_ray(eye, endpoint)
        rows.append({"target_xyz_m": target,
                     "ray_length_m": distance(eye, endpoint),
                     "hits": [{"xyz_m": xyz(hit.location),
                               "label": str(hit.label)} for hit in hits]})
    return rows
