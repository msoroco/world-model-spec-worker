"""Portable U-turn route construction and next-tick actuator requests."""
from __future__ import annotations

import hashlib
import math

from shapely.geometry import LineString, Point, box


def validate_scene(scene):
    context = scene["context"]
    if not context.get("map_source_sha256") or not context.get("authority_review_source_sha256"):
        raise ValueError("source-hashed map and authority review required")
    opening = box(*context["opening_bounds_xy_m"])
    barriers = [box(*item) for item in context["closed_divider_bounds_xy_m"]]
    source = box(*context["source_right_roadway_bounds_xy_m"])
    destination = box(*context["destination_right_roadway_bounds_xy_m"])
    route = scene["route_xy_m"]
    directions = scene["segment_directions"]
    half_width = scene["vehicle_half_width_m"]
    if (len(route) < 5 or len(directions) != len(route)-1 or
            any(item not in ("forward", "reverse") for item in directions) or
            not isinstance(half_width, (int,float)) or not 0 < half_width < 3):
        raise ValueError("invalid authored maneuver segments")
    if not source.covers(Point(route[0])) or not destination.covers(Point(route[-1])):
        raise ValueError("U-turn endpoints differ from source/destination right roadways")
    path = LineString(route)
    corridor = path.buffer(half_width, cap_style=2, join_style=2)
    if path.length <= 0 or not path.intersects(opening):
        raise ValueError("authored U-turn route misses the median opening")
    if any(corridor.intersects(barrier) for barrier in barriers):
        raise ValueError("authored full-width route contacts closed divider")
    source_center, destination_center = source.centroid, destination.centroid
    vector = (destination_center.x-source_center.x,
              destination_center.y-source_center.y)
    if math.hypot(*vector) <= 0:
        raise ValueError("source and destination roadway centers coincide")
    middle = ((source_center.x+destination_center.x)/2,
              (source_center.y+destination_center.y)/2)
    signed = [((point[0]-middle[0])*vector[0]+(point[1]-middle[1])*vector[1])
              for point in route]
    through_opening = False
    for i,(before,after) in enumerate(zip(signed,signed[1:])):
        if before <= 0 <= after and after > before:
            fraction = -before/(after-before)
            crossing = Point(route[i][0]+fraction*(route[i+1][0]-route[i][0]),
                             route[i][1]+fraction*(route[i+1][1]-route[i][1]))
            through_opening |= opening.covers(crossing)
    if not through_opening:
        raise ValueError("authored roadway transition bypasses median opening")
    if len({tuple(point) for point in route}) < 4:
        raise ValueError("authored route has insufficient distinct points")
    start = math.atan2(route[1][1]-route[0][1],route[1][0]-route[0][0])
    end = math.atan2(route[-1][1]-route[-2][1],route[-1][0]-route[-2][0])
    turn = abs((math.degrees(end-start)+180)%360-180)
    if turn < 150:
        raise ValueError("authored route does not reverse travel direction")
    return {"route_length_m": path.length, "authored_direction_change_deg": turn,
            "reverse_segments": [i for i,item in enumerate(directions) if item == "reverse"],
            "physical_success_claimed": False}


def bind_map(world_map, scene, location_factory):
    validate_scene(scene)
    digest = hashlib.sha256(world_map.to_opendrive().encode()).hexdigest()
    if digest != scene["context"]["map_source_sha256"]:
        raise ValueError("live OpenDRIVE differs from inspected route source")
    route = scene["route_xy_m"]
    bound = []
    for point in (route[0], route[-1]):
        waypoint = world_map.get_waypoint(location_factory(*point), project_to_road=False)
        if waypoint is None:
            raise ValueError("U-turn endpoint lacks Native driving waypoint")
        bound.append(waypoint)
    if (bound[0].road_id != scene["source_road_id"] or
            bound[1].road_id != scene["destination_road_id"] or
            bound[0].road_id == bound[1].road_id):
        raise ValueError("Native roadway identities differ from source plan")
    return bound


def next_request(scene, state, *, x, y, yaw_deg, speed_mps, frame):
    """Require a stopped gear transition; requests never establish realization."""
    if type(frame) is not int or frame <= state.get("last_frame", -1):
        raise ValueError("stale original control frame")
    if state.get("last_frame") is not None and frame != state["last_frame"]+1:
        raise ValueError("gap in original control frames")
    if not all(math.isfinite(value) for value in (x,y,yaw_deg,speed_mps)):
        raise ValueError("non-finite original pose or speed")
    route = scene["route_xy_m"]
    directions = scene["segment_directions"]
    target = state.get("target_index",1)
    if target >= len(route):
        return {"last_frame":frame,"target_index":target,"request":"brake",
                "throttle":0.0,"brake":1.0,"steer":0.0,"reverse":False}
    distance = math.hypot(route[target][0]-x,route[target][1]-y)
    if distance < .8:
        if target == len(route)-1:
            target += 1
        elif directions[target-1] != directions[target] and speed_mps >= .15:
            return {"last_frame":frame,"target_index":target,"request":"gear_transition_brake",
                    "throttle":0.0,"brake":1.0,"steer":0.0,
                    "reverse":directions[target-1]=="reverse"}
        else:
            target += 1
    if target >= len(route):
        return {"last_frame":frame,"target_index":target,"request":"brake",
                "throttle":0.0,"brake":1.0,"steer":0.0,"reverse":False}
    reverse = directions[target-1] == "reverse"
    dx,dy = route[target][0]-x,route[target][1]-y
    desired = math.atan2(dy,dx)+(math.pi if reverse else 0)
    error = (desired-math.radians(yaw_deg)+math.pi)%(2*math.pi)-math.pi
    steer = max(-.65,min(.65,error*( -1.2 if reverse else 1.2)))
    return {"last_frame":frame,"target_index":target,"request":"drive",
            "throttle":max(.08,min(.35,.3-.07*speed_mps)),"brake":0.0,
            "steer":steer,"reverse":reverse}


def apply(actor, carla, request):
    actor.apply_control(carla.VehicleControl(throttle=request["throttle"],
        brake=request["brake"],steer=request["steer"],reverse=request["reverse"]))
