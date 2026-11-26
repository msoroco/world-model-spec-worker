"""Source-gated Native geometry for an independently reviewed restricted zone.

Stations are measured along the reviewed approach polyline. This module never
infers that a sign is authoritative or that a curb is legally effective.
"""

import hashlib
import math
from pathlib import Path


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _require(value, message):
    if not value:
        raise ValueError(message)


def _vector(value, length, label):
    _require(isinstance(value, list) and len(value) == length, label + " missing")
    try:
        numbers = tuple(float(item) for item in value)
    except (TypeError, ValueError) as error:
        raise ValueError(label + " invalid") from error
    _require(all(math.isfinite(item) for item in numbers), label + " nonfinite")
    return numbers


def _source(packet_path, ref, label):
    _require(isinstance(ref, dict) and ref.get("path") and ref.get("sha256"),
             label + " source reference missing")
    source = Path(ref["path"])
    if not source.is_absolute():
        source = Path(packet_path).resolve().parent / source
    source = source.resolve()
    _require(source.is_file(), label + " source missing")
    _require(hashlib.sha256(source.read_bytes()).hexdigest() == ref["sha256"],
             label + " source stale")
    return source


def validate_binding(packet_path, packet, plan):
    """Validate reviewed world coordinates without opening or mutating CARLA."""
    binding = packet.get("native_binding")
    _require(isinstance(binding, dict), "reviewed Native binding missing")
    _source(packet_path, binding.get("geometry_source"), "Native geometry")
    _require(binding.get("map_name") == plan.map_id, "Native map identity mismatch")
    route = binding.get("approach_route")
    _require(isinstance(route, list) and len(route) >= 2,
             "reviewed approach route missing")
    stations = []
    for point in route:
        _require(isinstance(point, dict), "reviewed route point invalid")
        station = float(point.get("station_m", float("nan")))
        _require(math.isfinite(station), "reviewed route station nonfinite")
        _vector(point.get("location_m"), 3, "reviewed route coordinate")
        stations.append(station)
    _require(all(right > left for left, right in zip(stations, stations[1:])),
             "reviewed route stations not increasing")
    _require(stations[0] <= min(-5, plan.entrant_start_m) and
             stations[-1] >= plan.zone_end_m + 5,
             "reviewed route does not cover approach and zone")
    for left, right in zip(route, route[1:]):
        a = _vector(left["location_m"], 3, "route coordinate")
        b = _vector(right["location_m"], 3, "route coordinate")
        distance = math.dist(a, b)
        delta = float(right["station_m"]) - float(left["station_m"])
        _require(distance > .01 and abs(distance - delta) <= max(.5, .05 * delta),
                 "reviewed station distances disagree with world coordinates")
    for name in ("subject", "entrant", "passenger"):
        blueprint = binding.get("blueprints", {}).get(name)
        _require(isinstance(blueprint, str) and blueprint.strip(),
                 "reviewed blueprint missing: " + name)
    actors = binding.get("fixed_actors")
    _require(isinstance(actors, dict), "reviewed fixed-actor inventory missing")
    for name in ("zone_sign", "zone_curb"):
        item = actors.get(name)
        _require(isinstance(item, dict) and type(item.get("actor_id")) is int and
                 isinstance(item.get("type_id"), str) and item["type_id"],
                 "reviewed fixed actor missing: " + name)
    poses = binding.get("camera_poses")
    _require(isinstance(poses, dict) and set(poses) == set(VIEWS),
             "four reviewed camera poses required")
    for name, pose in poses.items():
        _require(isinstance(pose, dict), "reviewed camera pose missing: " + name)
        _vector(pose.get("location_m"), 3, "camera location " + name)
        _vector(pose.get("rotation_deg"), 3, "camera rotation " + name)
    _vector(binding.get("passenger_spawn_m"), 3, "passenger spawn")
    _vector(binding.get("passenger_door_m"), 3, "passenger door")
    access = binding.get("entrant_access_polygon_m")
    _require(isinstance(access, list) and len(access) >= 3,
             "reviewed entrant access polygon missing")
    for point in access:
        _vector(point, 2, "entrant access vertex")
    tolerances = binding.get("observation_tolerances_m")
    _require(isinstance(tolerances, dict), "reviewed observation tolerances missing")
    for name in ("station", "door", "access"):
        value = tolerances.get(name)
        _require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= 5,
                 "reviewed observation tolerance missing: " + name)
    return binding


def point_at_station(binding, station):
    route = binding["approach_route"]
    station = float(station)
    for left, right in zip(route, route[1:]):
        a, b = float(left["station_m"]), float(right["station_m"])
        if a <= station <= b:
            fraction = (station - a) / (b - a)
            start = _vector(left["location_m"], 3, "route coordinate")
            end = _vector(right["location_m"], 3, "route coordinate")
            return tuple(x + fraction * (y - x) for x, y in zip(start, end))
    raise ValueError("station outside reviewed route")


def station_of(binding, location):
    """Project live actor position onto route, rejecting off-route readback."""
    point = _vector(list(location), 3, "live actor position")
    best = None
    for left, right in zip(binding["approach_route"], binding["approach_route"][1:]):
        a = _vector(left["location_m"], 3, "route coordinate")
        b = _vector(right["location_m"], 3, "route coordinate")
        v = tuple(y - x for x, y in zip(a, b))
        factor = max(0.0, min(1.0, sum((p - x) * d for p, x, d in zip(point, a, v)) /
                               sum(d * d for d in v)))
        projected = tuple(x + factor * d for x, d in zip(a, v))
        distance = math.dist(point, projected)
        station = float(left["station_m"]) + factor * (
            float(right["station_m"]) - float(left["station_m"]))
        if best is None or distance < best[0]:
            best = (distance, station)
    _require(best is not None and best[0] <= binding["observation_tolerances_m"]["station"],
             "live actor outside reviewed route tolerance")
    return best[1]


def load(packet_path, plan):
    from reviewed_site import validate
    packet = validate(packet_path, plan.case_id, plan)
    return validate_binding(packet_path, packet, plan)
