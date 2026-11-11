"""Construct and check two Native approaches to one reviewed median crossing."""
import math
from shapely.geometry import Point, Polygon


def _location(transform):
    location = transform.location
    x, y = float(location.x), float(location.y)
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError("Nonfinite approach location")
    return x, y


def _waypoint(world_map, transform, label):
    waypoint = world_map.get_waypoint(transform.location, project_to_road=False)
    if waypoint is None:
        raise ValueError("No Native waypoint for " + label)
    return waypoint


def _forward_alignment(approach, entry):
    ax, ay = _location(approach)
    ex, ey = _location(entry)
    dx, dy = ex - ax, ey - ay
    length = math.hypot(dx, dy)
    if length < 3:
        raise ValueError("Approach begins too near crossing entry")
    yaw = math.radians(float(approach.rotation.yaw))
    alignment = (math.cos(yaw) * dx + math.sin(yaw) * dy) / length
    if alignment < 0.8:
        raise ValueError("Approach heading does not enter crossing")
    return alignment


def plan_approaches(world_map, ego_approach, ego_entry, other_approach,
                    other_entry, crossing_polygon_xy_m, crossing_id,
                    polygon_source, entrance_source):
    """Check executable spawn/entry geometry; statutory identity still needs review."""
    if not polygon_source or not entrance_source:
        raise ValueError("Reviewed crossing polygon and entrance sources required")
    polygon = Polygon(crossing_polygon_xy_m)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid crossing polygon")
    approaches = {}
    for role, start, entry in (("ego", ego_approach, ego_entry),
                               ("other", other_approach, other_entry)):
        start_point, entry_point = Point(_location(start)), Point(_location(entry))
        if polygon.intersects(start_point):
            raise ValueError(role + " spawn is already in crossing")
        if not polygon.intersects(entry_point):
            raise ValueError(role + " entry misses crossing polygon")
        start_wp = _waypoint(world_map, start, role + " approach")
        entry_wp = _waypoint(world_map, entry, role + " entry")
        if start_wp.is_junction:
            raise ValueError(role + " approach begins inside Native junction")
        if not entry_wp.is_junction or entry_wp.get_junction().id != crossing_id:
            raise ValueError(role + " entry is not in selected Native junction")
        alignment = _forward_alignment(start, entry)
        approaches[role] = {
            "road_id": start_wp.road_id, "lane_id": start_wp.lane_id,
            "entry_road_id": entry_wp.road_id, "entry_lane_id": entry_wp.lane_id,
            "spawn_xy_m": list(start_point.coords[0]),
            "entry_xy_m": list(entry_point.coords[0]),
            "heading_alignment": alignment,
        }
    if approaches["ego"]["road_id"] == approaches["other"]["road_id"]:
        raise ValueError("Different Native approach roads required")
    return {
        "native_junction_id": crossing_id,
        "candidate_same_native_junction": True,
        "statutory_same_crossing_verified": False,
        "crossing_polygon_xy_m": crossing_polygon_xy_m,
        "crossing_geometry_source": polygon_source,
        "all_entrances_source": entrance_source,
        "approaches": approaches,
    }
