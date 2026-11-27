"""Lazy CARLA walker adapter for a reviewed original C40598 route."""
from __future__ import annotations

import math

from crosswalk_site import point_in_polygon


def validate_review(reviewed: dict, case_id: str) -> None:
    if reviewed['review']['case_id'] != case_id:
        raise ValueError('reviewed walker route case differs')
    route = reviewed['sources']['pedestrian_route']
    roadway = reviewed['sources']['roadway']
    if len(route['route_xy_m']) < 3:
        raise ValueError('start, roadway and opposite-curb walker waypoints required')
    if not any(point_in_polygon(point, roadway['roadway_polygon_xy_m'])
               for point in route['route_xy_m'][1:-1]):
        raise ValueError('reviewed walker route lacks roadway point')


def configure(world, reviewed: dict, case_id: str, speed: float) -> dict:
    """Spawn one walker only after source and route validation."""
    validate_review(reviewed, case_id)
    if type(speed) not in (int, float) or not .3 <= speed <= 1.5:
        raise ValueError('bounded pedestrian speed required')
    import carla
    route = reviewed['sources']['pedestrian_route']
    blueprints = world.get_blueprint_library().filter('walker.pedestrian.*')
    if not blueprints:
        raise ValueError('original Native pedestrian blueprint missing')
    start = route['approach_xy_m']
    transform = carla.Transform(carla.Location(x=float(start[0]), y=float(start[1]),
                                         z=float(route['spawn_z_m'])), carla.Rotation())
    walker = world.try_spawn_actor(blueprints[0], transform)
    if walker is None:
        raise ValueError('original Native pedestrian spawn failed')
    return {'walker': walker, 'route': route['route_xy_m'], 'speed': float(speed),
            'target_index': 1, 'reviewed': reviewed}


def _body_polygon(actor) -> list[list[float]]:
    transform = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) < 4:
        raise ValueError('original Native walker body vertices missing')
    xs = [float(vertex.x) for vertex in vertices]
    ys = [float(vertex.y) for vertex in vertices]
    if any(not math.isfinite(value) for value in xs + ys):
        raise ValueError('finite original Native walker body vertices required')
    return [[min(xs), min(ys)], [max(xs), min(ys)],
            [max(xs), max(ys)], [min(xs), max(ys)]]


def sample(world, handle: dict, frame: int, time_s: float) -> dict:
    """Read original walker pose/body, then request the next route target."""
    import carla
    walker = handle['walker']
    pose = walker.get_transform().location
    xyz = [float(pose.x), float(pose.y), float(pose.z)]
    if any(not math.isfinite(value) for value in xyz):
        raise ValueError('original Native walker pose missing')
    body = _body_polygon(walker)
    roadway = handle['reviewed']['sources']['roadway']
    on_road = any(point_in_polygon(vertex, roadway['roadway_polygon_xy_m'])
                  for vertex in body)
    if on_road:
        side = 'roadway'
    elif point_in_polygon(xyz[:2], roadway['start_curb_zone_polygon_xy_m']):
        side = 'start'
    elif point_in_polygon(xyz[:2], roadway['opposite_curb_zone_polygon_xy_m']):
        side = 'opposite'
    else:
        raise ValueError('original Native walker outside reviewed road and curb zones')
    route = handle['route']
    index = handle['target_index']
    while index < len(route) - 1 and math.dist(xyz[:2], route[index]) <= .4:
        index += 1
    handle['target_index'] = index
    target = route[index]
    delta = [float(target[0]) - xyz[0], float(target[1]) - xyz[1]]
    remaining = math.hypot(*delta)
    if remaining > .1:
        direction = carla.Vector3D(x=delta[0] / remaining,
                                   y=delta[1] / remaining, z=0)
        speed = handle['speed']
    else:
        direction = carla.Vector3D(x=0, y=0, z=0)
        speed = 0.0
    walker.apply_control(carla.WalkerControl(direction=direction,
                                             speed=speed, jump=False))
    return {'pedestrian_on_roadway': on_road, 'pedestrian_xyz_m': xyz,
            'body_polygon_xy_m': body, 'curb_side': side,
            'observation_source': 'original_native_snapshot'}


def teardown(handle: dict) -> None:
    walker = handle.get('walker')
    if walker is not None:
        walker.destroy()
