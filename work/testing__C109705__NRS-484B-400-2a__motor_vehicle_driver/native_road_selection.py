"""Inspect both intersecting Native roads for opposite-direction driving lanes.

Signed lane IDs are an engineering preflight, not proof of legal highway status
or the exact physical centerline; original map/camera review remains required.
"""

import hashlib
import math
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon

CAMERA_PROFILE = {
    "overview": (1920, 1080),
    "approach": (1280, 720),
    "reference_corner": (1280, 720),
    "driver_reference": (1280, 720),
}


def verify_two_directional_roads(world, approach_road_id, outgoing_road_id,
                                 *, waypoint_spacing_m=2.0):
    if approach_road_id==outgoing_road_id:
        raise ValueError("Two intersecting road identities required")
    waypoints=world.get_map().generate_waypoints(waypoint_spacing_m)
    lanes={approach_road_id:set(),outgoing_road_id:set()}
    for waypoint in waypoints:
        if waypoint.road_id in lanes and str(waypoint.lane_type).lower().endswith("driving"):
            lanes[waypoint.road_id].add(waypoint.lane_id)
    for road_id,ids in lanes.items():
        if not any(i>0 for i in ids) or not any(i<0 for i in ids):
            raise ValueError("Opposite-direction Native driving lanes missing on road "+str(road_id))
    return {"approach_road_id":approach_road_id,"outgoing_road_id":outgoing_road_id,
            "native_lane_ids":{str(key):sorted(value) for key,value in lanes.items()},
            "legal_two_directional_status":"unresolved pending source review"}


def _geometry_points(value, label, minimum):
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError("Missing " + label)
    points = []
    for point in value:
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(number) not in (int, float) or
                    not math.isfinite(number) for number in point)):
            raise ValueError("Invalid " + label)
        points.append(tuple(float(number) for number in point))
    return points


def _review_source(root, reference, label):
    if not isinstance(reference, dict) or not reference.get("path") or not reference.get("sha256"):
        raise ValueError("Missing " + label + " source")
    relative = Path(reference["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe " + label + " source path")
    source = Path(root) / relative
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != reference["sha256"]:
        raise ValueError("Stale or missing " + label + " source")
    return {"path": reference["path"], "sha256": reference["sha256"]}


def validate_approach_site(world, packet, root):
    """Check a reviewed two-way approach packet against the loaded Native map.

    This binds map geometry and review documents; it does not settle legal road
    status or prove the vehicle's eventual physical position in a recording.
    """
    if not isinstance(packet, dict):
        raise ValueError("Approach site packet required")
    mapping = world.get_map()
    if packet.get("native_map_id") != mapping.name or packet.get("intersection_id") is None:
        raise ValueError("Native map or intersection identity differs")
    approach = packet.get("approach_road_id")
    outgoing = packet.get("outgoing_road_id")
    lane = packet.get("approach_lane_id")
    if any(type(value) is not int for value in (approach, outgoing, lane)) or lane == 0:
        raise ValueError("Exact Native approach and outgoing lane identities required")
    inventory = verify_two_directional_roads(world, approach, outgoing)
    if lane not in inventory["native_lane_ids"][str(approach)]:
        raise ValueError("Selected approach lane absent from Native inventory")
    if packet.get("centerline_kind") not in ("marked", "imaginary"):
        raise ValueError("Marked or imaginary centerline kind required")
    center = LineString(_geometry_points(packet.get("centerline_xy_m"), "centerline", 2))
    right = Polygon(_geometry_points(packet.get("right_half_polygon_xy_m"), "right half", 3))
    junction = Polygon(_geometry_points(packet.get("junction_polygon_xy_m"), "junction", 3))
    route = LineString(_geometry_points(packet.get("approach_route_xy_m"), "approach route", 2))
    if (center.length <= 0 or not right.is_valid or right.area <= 0 or
            not junction.is_valid or junction.area <= 0 or route.length <= 0 or
            not center.intersects(right.boundary) or not right.intersects(junction) or
            not right.covers(route) or not route.intersects(junction)):
        raise ValueError("Approach centerline, right half, route or junction geometry differs")
    names = ("approach_road_source", "outgoing_road_source", "centerline_source",
             "right_half_source", "junction_source", "route_source")
    sources = {name: _review_source(root, packet.get(name), name) for name in names}
    if len({source["path"] for source in sources.values()}) != len(sources):
        raise ValueError("Distinct review source documents required")
    if not packet.get("reviewer") or not packet.get("review_basis"):
        raise ValueError("Explicit site review basis required")
    return {"format": "worker-c109705-approach-site-review",
            "native_map_id": mapping.name, "intersection_id": packet["intersection_id"],
            "approach_road_id": approach, "approach_lane_id": lane,
            "outgoing_road_id": outgoing, "centerline_kind": packet["centerline_kind"],
            "native_lane_inventory": inventory, "sources": sources,
            "physical_approach_position": "unverified", "legal_two_directional_status": "unresolved"}


def plan_left_turn(world, packet, root):
    """Construct a left turn following a source-bound right-half approach."""
    review = validate_approach_site(world, packet, root)
    approach = _geometry_points(packet["approach_route_xy_m"], "approach route", 2)
    route = _geometry_points(packet.get("left_turn_route_xy_m"), "left turn route", 4)
    junction = Polygon(_geometry_points(packet["junction_polygon_xy_m"], "junction", 3))
    if route[:len(approach)] != approach:
        raise ValueError("Turn route does not preserve reviewed approach")
    if any(math.dist(a, b) < 0.1 for a, b in zip(route, route[1:])):
        raise ValueError("Duplicate turn route points")
    approach_vector = (approach[-1][0]-approach[-2][0],
                       approach[-1][1]-approach[-2][1])
    exit_vector = (route[-1][0]-route[-2][0], route[-1][1]-route[-2][1])
    if (math.hypot(*approach_vector) < 0.1 or math.hypot(*exit_vector) < 0.1 or
            approach_vector[0]*exit_vector[1]-approach_vector[1]*exit_vector[0] <= 0):
        raise ValueError("Route must make a left turn")
    if not junction.intersects(LineString(route[len(approach)-1:])):
        raise ValueError("Turn route misses reviewed junction")
    if junction.covers(Point(route[-1])):
        raise ValueError("Turn route must exit reviewed junction")
    return {"route_xy_m": [list(point) for point in route],
            "source_review": review, "physical_completion_claimed": False}


def four_camera_plan(packet, route_xy_m):
    """Camera placement intent; Native capture must confirm actual visibility."""
    route = _geometry_points(route_xy_m, "left turn route", 4)
    z = packet.get("start_z_m")
    if type(z) not in (int, float) or not math.isfinite(z):
        raise ValueError("Finite Native spawn height required")
    start, corner, departure = route[0], route[len(route)//2], route[-1]
    yaw = math.degrees(math.atan2(route[1][1]-start[1], route[1][0]-start[0]))
    cameras = [
        {"name": "overview", "mount": "world", "position_xyz_m": [corner[0]+12, corner[1]+12, z+30], "yaw_deg": yaw-135, "pitch_deg": -75},
        {"name": "approach", "mount": "world", "position_xyz_m": [start[0]-6, start[1]+4, z+7], "yaw_deg": yaw, "pitch_deg": -20},
        {"name": "reference_corner", "mount": "world", "position_xyz_m": [departure[0]+8, corner[1]+5, z+8], "yaw_deg": yaw+120, "pitch_deg": -35},
        {"name": "driver_reference", "mount": "ego_vehicle", "position_xyz_m": [1, 0, 1.65], "yaw_deg": 0, "pitch_deg": -5},
    ]
    for camera in cameras:
        camera["width"], camera["height"] = CAMERA_PROFILE[camera["name"]]
        camera["fov_deg"] = 75
        camera["visibility_verified"] = False
    return cameras


class RouteFollower:
    """Bounded, CARLA-independent steering and speed controller."""
    def __init__(self, route_xy_m, *, target_speed_mps=4.0, reach_m=2.0):
        self.route = _geometry_points(route_xy_m, "route", 2)
        if (type(target_speed_mps) not in (int, float) or
                not math.isfinite(target_speed_mps) or not 0 < target_speed_mps <= 8):
            raise ValueError("Bounded turn speed required")
        if type(reach_m) not in (int, float) or not math.isfinite(reach_m) or reach_m <= 0:
            raise ValueError("Positive waypoint reach required")
        if any(math.dist(a, b) < 0.1 for a, b in zip(self.route, self.route[1:])):
            raise ValueError("Duplicate route points")
        self.speed, self.reach, self.index = float(target_speed_mps), float(reach_m), 1

    def step(self, position_xy_m, forward_xy, speed_mps):
        position, forward = _geometry_points([list(position_xy_m), list(forward_xy)], "vehicle state", 2)
        px, py = position
        if (type(speed_mps) not in (int, float) or
                not math.isfinite(speed_mps) or speed_mps < 0):
            raise ValueError("Invalid observed speed")
        norm = math.hypot(*forward)
        if norm < 0.1:
            raise ValueError("Zero vehicle forward vector")
        fx, fy = forward[0]/norm, forward[1]/norm
        while self.index < len(self.route)-1 and math.dist((px, py), self.route[self.index]) <= self.reach:
            self.index += 1
        tx, ty = self.route[self.index]
        vx, vy = tx-px, ty-py
        distance = math.hypot(vx, vy)
        if self.index == len(self.route)-1 and distance <= self.reach:
            return {"throttle": 0.0, "brake": 1.0, "steer": 0.0,
                    "route_complete": True, "target_index": self.index}
        angle = math.atan2(fx*vy-fy*vx, fx*vx+fy*vy)
        error = self.speed-float(speed_mps)
        return {"throttle": max(0.0, min(0.45, 0.12*error)),
                "brake": max(0.0, min(0.6, -0.2*error)),
                "steer": max(-1.0, min(1.0, angle/math.radians(40))),
                "route_complete": False, "target_index": self.index}
