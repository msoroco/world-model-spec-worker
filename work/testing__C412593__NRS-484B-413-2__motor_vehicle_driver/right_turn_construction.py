"""Spawn on a source-reviewed Native approach with a measured right-turn route."""

from contextlib import contextmanager
import math


def _xy(waypoint):
    point = waypoint.transform.location
    x, y = float(point.x), float(point.y)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("Nonfinite Native waypoint")
    return (x, y)


def verify_route(approach, outgoing, *, required_direct_approach_m=91.44,
                 max_step_m=5.0):
    """Check physical lane geometry; district class remains source-reviewed."""
    if len(approach) < 3 or len(outgoing) < 2:
        raise ValueError("Incomplete approach or departure waypoints")
    first = approach[0]
    if any(wp.road_id != first.road_id or wp.lane_id != first.lane_id for wp in approach):
        raise ValueError("Approach changes lane or road before turn")
    if any(wp.road_id != outgoing[0].road_id or wp.lane_id != outgoing[0].lane_id for wp in outgoing):
        raise ValueError("Departure does not hold the selected lane")
    if outgoing[0].road_id == first.road_id:
        raise ValueError("No observed turning road transition")
    points = [_xy(wp) for wp in approach]
    departure = [_xy(wp) for wp in outgoing]
    steps = [math.dist(a,b) for a,b in zip(points,points[1:])]
    if any(step <= 0 or step > max_step_m for step in steps):
        raise ValueError("Approach waypoint chain is discontinuous")
    length = sum(steps)
    if length < required_direct_approach_m:
        raise ValueError("Direct approach shorter than required observation span")
    incoming = (points[-1][0]-points[-2][0], points[-1][1]-points[-2][1])
    outgoing_vector = (departure[-1][0]-departure[0][0], departure[-1][1]-departure[0][1])
    denominator = math.hypot(*incoming)*math.hypot(*outgoing_vector)
    if denominator == 0:
        raise ValueError("Zero turn vector")
    cross = (incoming[0]*outgoing_vector[1]-incoming[1]*outgoing_vector[0])/denominator
    dot = (incoming[0]*outgoing_vector[0]+incoming[1]*outgoing_vector[1])/denominator
    angle = math.degrees(math.atan2(cross,dot))
    if not -150 < angle < -30:
        raise ValueError("Native route is not a physical right turn")
    return {"approach_road_id":first.road_id,"approach_lane_id":first.lane_id,
            "outgoing_road_id":outgoing[0].road_id,"outgoing_lane_id":outgoing[0].lane_id,
            "direct_approach_m":length,"turn_angle_degrees":angle,
            "approach_waypoints":approach,"outgoing_waypoints":outgoing}


@contextmanager
def spawn_right_turn_vehicle(world, blueprint, approach, outgoing,
                             *, required_direct_approach_m=91.44):
    route = verify_route(approach,outgoing,required_direct_approach_m=required_direct_approach_m)
    actor = world.try_spawn_actor(blueprint,approach[0].transform)
    if actor is None:
        raise ValueError("Native vehicle spawn failed")
    try:
        waypoint = world.get_map().get_waypoint(actor.get_location(),project_to_road=False)
        if waypoint is None or (waypoint.road_id,waypoint.lane_id) != (
                route["approach_road_id"],route["approach_lane_id"]):
            raise ValueError("Spawned vehicle outside sourced right-turn approach")
        yield {"actor":actor,"route":route}
    finally:
        actor.destroy()
