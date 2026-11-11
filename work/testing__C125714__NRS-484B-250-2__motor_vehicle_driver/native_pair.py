"""Lazy Native construction of an other-from-right median crossing candidate."""
from contextlib import contextmanager
import math

from shapely.geometry import Point, Polygon

from entry_measurements import _right_side


def _xy(transform):
    return float(transform.location.x), float(transform.location.y)


def _waypoint(world_map, transform, label):
    waypoint = world_map.get_waypoint(transform.location, project_to_road=False)
    if waypoint is None:
        raise ValueError("No Native driving waypoint for " + label)
    if getattr(waypoint, "lane_type", None) is not None and "Driving" not in str(waypoint.lane_type):
        raise ValueError("Non-driving Native waypoint for " + label)
    return waypoint


def plan_pair(world_map, site, transforms):
    """Check executable geometry; legal priority remains a saved-source question."""
    required = ("native_map_name", "crossing_id", "ego_highway_id",
                "other_highway_id", "polygon_source", "approach_geometry_source")
    if any(site.get(key) in (None, "") for key in required):
        raise ValueError("Sourced Native crossing and highway identities required")
    if site["ego_highway_id"] == site["other_highway_id"]:
        raise ValueError("Different highway identities required")
    polygon = Polygon(site.get("crossing_polygon_xy_m", []))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Valid selected crossing polygon required")
    approaches = {}
    for role in ("ego", "other"):
        start = transforms[role + "_approach"]
        entry = transforms[role + "_entry"]
        start_point, entry_point = Point(_xy(start)), Point(_xy(entry))
        if polygon.intersects(start_point) or not polygon.intersects(entry_point):
            raise ValueError(role + " approach/entry misses selected crossing")
        dx, dy = entry_point.x - start_point.x, entry_point.y - start_point.y
        distance = math.hypot(dx, dy)
        yaw = math.radians(float(start.rotation.yaw))
        if distance < 3 or (math.cos(yaw) * dx + math.sin(yaw) * dy) / distance < 0.8:
            raise ValueError(role + " heading does not approach crossing entry")
        start_wp = _waypoint(world_map, start, role + " approach")
        entry_wp = _waypoint(world_map, entry, role + " entry")
        if start_wp.is_junction or not entry_wp.is_junction or entry_wp.get_junction().id != site["crossing_id"]:
            raise ValueError(role + " Native entry is not in selected junction")
        approaches[role] = {
            "start_xy_m": list(_xy(start)), "entry_xy_m": list(_xy(entry)),
            "heading_deg": float(start.rotation.yaw),
            "road_id": start_wp.road_id, "lane_id": start_wp.lane_id,
            "entry_road_id": entry_wp.road_id,
            "entry_lane_id": entry_wp.lane_id}
    if approaches["ego"]["road_id"] == approaches["other"]["road_id"]:
        raise ValueError("Distinct Native approach roads required")
    lateral = _right_side(approaches["ego"]["start_xy_m"],
                          approaches["ego"]["heading_deg"],
                          approaches["other"]["start_xy_m"])
    reciprocal = _right_side(approaches["other"]["start_xy_m"],
                             approaches["other"]["heading_deg"],
                             approaches["ego"]["start_xy_m"])
    if lateral <= 0 or reciprocal >= 0:
        raise ValueError("Other Native approach is not on ego right")
    return {"native_map_name": site["native_map_name"],
            "native_junction_id": site["crossing_id"],
            "ego_highway_id": site["ego_highway_id"],
            "other_highway_id": site["other_highway_id"],
            "crossing_polygon_xy_m": site["crossing_polygon_xy_m"],
            "crossing_polygon_source": site["polygon_source"],
            "approach_geometry_source": site["approach_geometry_source"],
            "other_lateral_to_ego_right_m": lateral,
            "ego_lateral_to_other_right_m": reciprocal,
            "approaches": approaches,
            "physical_acceptance_claimed": False,
            "legal_priority_judgment": "unresolved"}


@contextmanager
def construct_pair(world, site, transforms, other_blueprint):
    world_map = world.get_map()
    if world_map.name != site.get("native_map_name"):
        raise ValueError("Native map differs from reviewed median site")
    plan = plan_pair(world_map, site, transforms)
    other = world.try_spawn_actor(other_blueprint, transforms["other_approach"])
    if other is None:
        raise ValueError("Other-from-right Native spawn failed")
    try:
        yield plan, other
    finally:
        other.destroy()
