"""Lazy Native construction and turn/yield policy for exact C111610 probes."""
from __future__ import annotations

import math


class ConstructionError(ValueError):
    pass


def _check(condition, message):
    if not condition:
        raise ConstructionError(message)


def waypoint_near(mapping, carla, xy, limit_m=2.0):
    waypoint = mapping.get_waypoint(carla.Location(x=xy[0], y=xy[1], z=0))
    _check(waypoint is not None, 'original map waypoint missing')
    point = waypoint.transform.location
    _check(math.hypot(point.x - xy[0], point.y - xy[1]) <= limit_m,
           'authored point not on original lane')
    return waypoint


def connected(start, goal, step_m=2.0, maximum=800):
    target = goal.transform.location
    queue = [start]
    seen = set()
    for node in queue:
        point = node.transform.location
        identity = (getattr(node, 'road_id', None), getattr(node, 'lane_id', None),
                    round(point.x, 1), round(point.y, 1))
        if identity in seen:
            continue
        seen.add(identity)
        if math.hypot(point.x-target.x, point.y-target.y) <= step_m:
            return True
        if len(seen) >= maximum:
            break
        queue.extend(node.next(step_m))
    return False


def construct(world, carla, scene, verified_site):
    """Spawn separate participants on connected original lanes; clean on failure.

    The verified_site must come from an original map/device survey checked by
    crosswalk.bind_site. It cannot be synthesized from the desired case label.
    """
    _check(scene['case_id'] and scene['turn_direction'] == 'left',
           'fixed left-turn case identity missing')
    _check(verified_site['turn_route'] and verified_site['destination_half'],
           'original site binding missing')
    mapping = world.get_map()
    route = [waypoint_near(mapping, carla, xy) for xy in verified_site['turn_route']]
    _check(all(connected(a,b) for a,b in zip(route,route[1:])),
           'original lane route does not connect through turn')
    person_start = scene['pedestrian_start_xy_m']
    _check(any(_contains(person_start, poly) for poly in verified_site['destination_half']) ==
           (scene['pedestrian_half'] == 'destination'),
           'pedestrian starts on wrong directional half')
    library = world.get_blueprint_library()
    vehicle_bp = library.find(scene['ego_blueprint_id'])
    person_bp = library.find(scene['pedestrian_blueprint_id'])
    _check(vehicle_bp is not None and person_bp is not None, 'Native blueprint missing')
    spawned = []
    try:
        for blueprint, xy, yaw in ((vehicle_bp, scene['ego_start_xy_m'], scene['ego_yaw_deg']),
                                   (person_bp, person_start, scene['pedestrian_yaw_deg'])):
            actor = world.spawn_actor(blueprint,
                carla.Transform(carla.Location(x=xy[0], y=xy[1], z=0),
                                carla.Rotation(yaw=yaw)))
            _check(actor is not None, 'Native participant spawn failed')
            spawned.append(actor)
        _check(spawned[0].id != spawned[1].id, 'Native participant identities overlap')
        return {'ego': spawned[0], 'pedestrian': spawned[1],
                'route_waypoint_ids': [(getattr(w,'road_id',None),getattr(w,'lane_id',None)) for w in route]}
    except BaseException:
        for actor in reversed(spawned):
            actor.destroy()
        raise


def _contains(point, polygon):
    # Bundled source-gated crosswalk geometry, without a CARLA dependency.
    import crosswalk
    return crosswalk.polygon_contains(point, polygon)


def control_policy(scene, measured):
    """Return engineering commands only; legal yielding remains under review."""
    _check(measured.get('source_frame') is not None and measured.get('source_refs'),
           'original motion measurement missing')
    _check(measured.get('device_condition') in ('absent','not_operating','operating'),
           'original device state missing')
    _check(measured.get('pedestrian_in_crosswalk') is not None and
           measured.get('pedestrian_on_destination_half') is not None,
           'original pedestrian geometry missing')
    if measured['device_condition'] == 'operating':
        return {'throttle':0.0,'brake':1.0,'reason':'active device case: pause for independent control review'}
    if measured['pedestrian_in_crosswalk'] and measured['pedestrian_on_destination_half']:
        return {'throttle':0.0,'brake':1.0,'reason':'destination half occupied'}
    if scene['pedestrian_half'] == 'opposite' and measured.get('approaching_danger_review') != 'cleared':
        return {'throttle':0.0,'brake':1.0,'reason':'opposite-half proximity unresolved'}
    return {'throttle':scene['engineering_throttle'],'brake':0.0,
            'reason':'measured crossing clear; bounded turn controller may proceed'}
