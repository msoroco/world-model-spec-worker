"""Reversible Native condition setup and original-world geometry probes.

Weather readback is an actuator check, not proof of wet/icy pavement or a
legal speed threshold. The caller must retain original camera and map sources.
"""
from contextlib import contextmanager
import math

WEATHER_FIELDS = ("cloudiness", "precipitation", "wetness", "fog_density",
                  "fog_distance", "sun_altitude_angle")


def _finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Finite " + label + " required")
    return float(value)


@contextmanager
def apply_sourced_weather(world, profile, *, profile_source):
    """Set and read back supported Native weather fields; always restore."""
    if not isinstance(profile_source, str) or not profile_source.strip():
        raise ValueError("Reviewed weather profile source required")
    if not isinstance(profile, dict) or set(profile) != set(WEATHER_FIELDS):
        raise ValueError("Complete Native weather profile required")
    requested = {name: _finite(profile[name], name) for name in WEATHER_FIELDS}
    for name in WEATHER_FIELDS[:4]:
        if not 0 <= requested[name] <= 100:
            raise ValueError("Native weather percentage outside 0..100: " + name)
    if requested["fog_distance"] < 0 or not -90 <= requested["sun_altitude_angle"] <= 90:
        raise ValueError("Native weather distance or sun angle invalid")
    saved = world.get_weather()
    applied = False
    try:
        # Work on a new object so the saved state remains restorable even in a
        # fake Native implementation whose set_weather stores by reference.
        import copy
        candidate = copy.copy(saved)
        for name, value in requested.items():
            setattr(candidate, name, value)
        applied = True
        world.set_weather(candidate)
        observed = world.get_weather()
        for name, value in requested.items():
            if abs(_finite(getattr(observed, name, None), "weather readback") - value) > .01:
                raise ValueError("Native weather readback differs: " + name)
        yield {"weather_profile_source": profile_source, "requested": requested,
               "readback": {name: float(getattr(observed, name)) for name in WEATHER_FIELDS},
               "surface_state_verified": False, "visibility_verified": False}
    finally:
        if applied:
            world.set_weather(saved)


def sample_lane_and_sight(world, waypoint, eye, forward, max_distance_m, *,
                          map_source, ray_source):
    """Measure Native lane width and nearest labelled ray obstruction.

    The resulting ray is an engineering probe. Original camera pixels and a
    reviewed surface/visibility source remain necessary for delivery.
    """
    if not map_source or not ray_source:
        raise ValueError("Original map and ray source required")
    width = _finite(getattr(waypoint, "lane_width", None), "lane width")
    if width <= 0 or not getattr(waypoint, "road_id", None):
        raise ValueError("Native lane width or road identity invalid")
    vector = [_finite(value, "forward axis") for value in forward]
    if len(vector) != 3:
        raise ValueError("3D forward axis required")
    norm = math.sqrt(sum(value * value for value in vector))
    distance = _finite(max_distance_m, "ray distance")
    if norm < .1 or distance <= 0:
        raise ValueError("Positive sight ray required")
    start = tuple(_finite(getattr(eye, key, None), "eye coordinate") for key in ("x", "y", "z"))
    end = tuple(start[i] + vector[i] * distance / norm for i in range(3))
    # CARLA takes Location objects; using eye.__class__ retains the Native
    # location type while keeping this module importable without CARLA.
    target = eye.__class__(x=end[0], y=end[1], z=end[2])
    hits = world.cast_ray(eye, target)
    first = distance
    for hit in hits:
        point = hit.location
        position = tuple(_finite(getattr(point, key, None), "ray hit") for key in ("x", "y", "z"))
        along = sum((position[i] - start[i]) * vector[i] / norm for i in range(3))
        if 0 <= along <= distance:
            first = min(first, along)
    return {"road_id": waypoint.road_id, "lane_id": waypoint.lane_id,
            "lane_width_m": width, "sight_ray_origin_xyz_m": list(start),
            "sight_ray_endpoint_xyz_m": list(end), "sight_distance_m": first,
            "map_source": map_source, "ray_source": ray_source,
            "original_camera_visibility_verified": False,
            "road_surface_verified": False}


def survey_narrow_route(start_waypoint, *, target_width_m, route_length_m=110,
                        sample_step_m=5):
    """Check a continuous Native lane, rather than trusting a width flag.

    The source waypoint must be from the reviewed site packet. A branch,
    junction, lane change or missing route segment requires a new site review.
    """
    if (not isinstance(target_width_m, list) or len(target_width_m) != 2 or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in target_width_m) or
            not 0 < target_width_m[0] < target_width_m[1]):
        raise ValueError('Finite narrow-lane target interval required')
    length = _finite(route_length_m, 'survey length')
    step = _finite(sample_step_m, 'survey step')
    if length < 100 or step <= 0 or length / step > 1000:
        raise ValueError('Narrow route must cover at least 100 m at bounded resolution')
    road_id, lane_id = start_waypoint.road_id, start_waypoint.lane_id
    if type(road_id) is not int or type(lane_id) is not int:
        raise ValueError('Original Native road/lane identity required')
    samples = []
    current = start_waypoint
    count = math.ceil(length / step)
    for index in range(count + 1):
        width = _finite(getattr(current, 'lane_width', None), 'lane width')
        if ((current.road_id, current.lane_id) != (road_id, lane_id) or
                getattr(current, 'is_junction', False) or
                not target_width_m[0] <= width <= target_width_m[1]):
            raise ValueError('Native narrow lane width or continuity differs')
        samples.append({'distance_m': min(index * step, length), 'lane_width_m': width})
        if index < count:
            advance = min(step, length - index * step)
            choices = current.next(advance)
            if len(choices) != 1:
                raise ValueError('Native narrow route missing or branching')
            current = choices[0]
    return {'road_id': road_id, 'lane_id': lane_id,
            'surveyed_length_m': length, 'sample_step_m': step,
            'samples': samples, 'source': 'original Native waypoint.next',
            'physical_motion_verified': False}
