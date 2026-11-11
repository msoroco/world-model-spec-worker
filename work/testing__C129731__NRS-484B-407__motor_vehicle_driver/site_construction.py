"""Source-bound curve/crest site and real occluder actor construction.

The site packet is a reviewed candidate input, never a visibility verdict. A
2D segment intersection only checks that a prop can obstruct a planned line;
Native rays, pixels, driver recognition and actual motion remain separate.
"""

import hashlib
import json
import math
from contextlib import contextmanager
from pathlib import Path

LAW = "NRS-484B-407"
CELL = "C129731"
ACTOR = "motor_vehicle_driver"
BOUNDARY_M = 152.4


def _point(value, size, label):
    if not isinstance(value, list) or len(value) != size or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError("Finite " + label + " required")
    return tuple(float(v) for v in value)


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _distance(a, b):
    return math.dist(a[:2], b[:2])


def _segment_intersects_box(a, b, center, extent, yaw_deg):
    radians = math.radians(yaw_deg)
    cosine, sine = math.cos(radians), math.sin(radians)

    def local(p):
        dx, dy = p[0]-center[0], p[1]-center[1]
        return (cosine*dx+sine*dy, -sine*dx+cosine*dy, p[2]-center[2])

    start, end = local(a), local(b)
    lower, upper = 0.0, 1.0
    for axis in (0, 1, 2):
        delta = end[axis]-start[axis]
        if abs(delta) < 1e-10:
            if abs(start[axis]) > extent[axis]:
                return False
            continue
        t0, t1 = sorted(((-extent[axis]-start[axis])/delta,
                         (extent[axis]-start[axis])/delta))
        lower, upper = max(lower, t0), min(upper, t1)
        if lower > upper:
            return False
    return True


def load_site(path, expected_sha256):
    path = Path(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Site packet changed")
    site = validate_site(json.loads(raw))
    if site["source_status"] != "reviewed_candidate":
        raise ValueError("Diagnostic geometry cannot be loaded for Native capture")
    return site


def validate_site(site):
    if (site.get("law_id"), site.get("cell_id"), site.get("actor")) != (LAW, CELL, ACTOR):
        raise ValueError("Wrong site law/cell/actor")
    if site.get("source_status") not in ("reviewed_candidate", "diagnostic_fixture") or not site.get("map_name"):
        raise ValueError("Candidate or diagnostic map source required")
    feature = site.get("feature")
    if feature not in ("curve", "crest"):
        raise ValueError("Curve or crest feature required")
    if site.get("probe") not in ("short_of_500ft", "at_500ft", "beyond_500ft"):
        raise ValueError("Exact 500-foot probe required")
    site_point = _point(site.get("turn_site_xyz_m"), 3, "turn site")
    centerline = [_point(p, 3, "centerline point") for p in site.get("centerline_xyz_m", [])]
    if len(centerline) < 3:
        raise ValueError("At least three surveyed centerline points required")
    if feature == "curve" and not any(abs(_cross(*centerline[i:i+3])) > 0.01
                                      for i in range(len(centerline)-2)):
        raise ValueError("Centerline has no constructed curve")
    if feature == "crest" and not any(centerline[i][2] > centerline[i-1][2]
                                       and centerline[i][2] > centerline[i+1][2]
                                       for i in range(1, len(centerline)-1)):
        raise ValueError("Centerline has no constructed grade crest")
    incoming = site.get("incoming_lanes")
    if not isinstance(incoming, dict) or set(incoming) != {"approach_a", "approach_b"}:
        raise ValueError("Both incoming directions required")
    lanes, lane_ids, outer = set(), set(), {}
    for direction, lane in incoming.items():
        identity = (lane.get("road_id"), lane.get("lane_id"))
        if any(type(v) is not int for v in identity) or identity in lanes:
            raise ValueError("Distinct surveyed road/lane identity required")
        lanes.add(identity)
        if identity[1] in lane_ids:
            raise ValueError("Pinned sight proxy requires distinct incoming lane IDs")
        lane_ids.add(identity[1])
        stations = lane.get("stations")
        if not isinstance(stations, list) or len(stations) < 3:
            raise ValueError("Three or more approach stations required: " + direction)
        distances = []
        for sample in stations:
            distance = sample.get("distance_to_turn_m")
            if type(distance) not in (int, float) or not math.isfinite(distance) or distance < 0:
                raise ValueError("Invalid approach station: " + direction)
            _point(sample.get("xyz_m"), 3, "approach waypoint")
            distances.append(distance)
        if distances != sorted(distances) or len(set(distances)) != len(distances):
            raise ValueError("Approach stations must be ordered and distinct: " + direction)
        if distances[-1] < BOUNDARY_M:
            raise ValueError("Approach inventory does not reach 500 feet: " + direction)
        outer[direction] = _point(stations[-1]["xyz_m"], 3, "far approach waypoint")
        if _distance(stations[0]["xyz_m"], site_point) > 30:
            raise ValueError("Nearest approach station misses turn site: " + direction)
    a, b = outer["approach_a"], outer["approach_b"]
    va, vb = (a[0]-site_point[0], a[1]-site_point[1]), (b[0]-site_point[0], b[1]-site_point[1])
    if math.hypot(*va) < 1 or math.hypot(*vb) < 1:
        raise ValueError("Far approach waypoint coincides with turn site")
    cosine = (va[0]*vb[0]+va[1]*vb[1])/(math.hypot(*va)*math.hypot(*vb))
    if cosine > -0.5:
        raise ValueError("Inventoried lanes do not approach from opposite directions")
    if len({road for road, lane in lanes}) != 1:
        raise ValueError("Pinned subject-road sight proxy requires one sourced road")
    if site.get("ego_road_lane") not in ([road, lane] for road, lane in lanes):
        raise ValueError("Ego spawn road/lane is not in approach inventory")
    route = [_point(p, 3, "U-turn route point") for p in site.get("u_turn_route_xyz_m", [])]
    if len(route) < 4 or _distance(route[0], site_point) > 30:
        raise ValueError("Continuous U-turn route through site required")
    inbound = (route[1][0]-route[0][0], route[1][1]-route[0][1])
    outbound = (route[-1][0]-route[-2][0], route[-1][1]-route[-2][1])
    if math.hypot(*inbound) < 0.1 or math.hypot(*outbound) < 0.1:
        raise ValueError("Degenerate U-turn route")
    reversal = (inbound[0]*outbound[0]+inbound[1]*outbound[1])/(math.hypot(*inbound)*math.hypot(*outbound))
    if reversal > -0.85:
        raise ValueError("Route does not reverse travel heading")
    obstruction = site.get("occluder")
    if not isinstance(obstruction, dict) or not str(obstruction.get("blueprint_id", "")).startswith("static.prop."):
        raise ValueError("Native static prop blueprint required")
    center = _point(obstruction.get("center_xyz_m"), 3, "occluder center")
    extent = _point(obstruction.get("half_extent_xyz_m"), 3, "occluder extent")
    yaw = obstruction.get("yaw_deg")
    if min(extent) <= 0 or type(yaw) not in (int, float) or not math.isfinite(yaw):
        raise ValueError("Positive occluder extent and finite yaw required")
    direction = obstruction.get("target_direction")
    if direction not in incoming:
        raise ValueError("Occluder must name an inventoried direction")
    observer = (outer[direction][0], outer[direction][1], outer[direction][2]+1.4)
    target = (site_point[0], site_point[1], site_point[2]+1.5)
    if not _segment_intersects_box(observer, target, center, extent, yaw):
        raise ValueError("Occluder does not intersect planned approach sight line")
    return site


@contextmanager
def spawned_occluder(world, carla, site):
    """Create and own the declared physical prop; caller owns the rest of run."""
    validate_site(site)
    spec = site["occluder"]
    blueprint = world.get_blueprint_library().find(spec["blueprint_id"])
    if blueprint is None:
        raise ValueError("Native occluder blueprint unavailable")
    x, y, z = spec["center_xyz_m"]
    pose = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=spec["yaw_deg"]))
    actor = world.try_spawn_actor(blueprint, pose)
    if actor is None:
        raise ValueError("Native occluder spawn failed")
    try:
        box = getattr(actor, "bounding_box", None)
        actual = getattr(box, "extent", None)
        if actual is None or any(getattr(actual, axis, 0) < required
                                 for axis, required in zip(("x", "y", "z"), spec["half_extent_xyz_m"])):
            raise ValueError("Native occluder body smaller than declared obstruction")
        yield actor
    finally:
        actor.destroy()
