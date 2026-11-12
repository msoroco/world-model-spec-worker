"""CARLA-lazy construction for the C111294 through-intersection comparison.

The simulator light bit is a control and readback, not proof of installed hardware
or emitted pixels. A separately sourced asset inventory is required at capture.
"""
from hashlib import sha256
import json
from math import atan2, cos, hypot, radians, sin
from pathlib import Path


def _xy(wp):
    p = wp.transform.location
    return (float(p.x), float(p.y))


def _yaw(wp):
    return float(wp.transform.rotation.yaw)


def _angle_difference(a, b):
    return abs((a - b + 180) % 360 - 180)


def _junction_id(wp):
    junction = wp.get_junction()
    return None if junction is None else int(junction.id)


def _unique_steps(wp, method, distance):
    options = getattr(wp, method)(distance)
    if len(options) != 1:
        raise ValueError('Ambiguous intersection through route')
    return options[0]


def discover_routes(world_map, *, approach_m=45., exit_m=35.):
    """Find a straight route and a perpendicular road through one junction.

    Map waypoints and actual junction IDs govern selection. Ambiguous candidates
    are rejected, allowing a local operator to pin a route instead of guessing.
    """
    candidates = {}
    for wp in world_map.generate_waypoints(2.0):
        jid = _junction_id(wp)
        if jid is None:
            continue
        try:
            start = _unique_steps(wp, 'previous', approach_m)
            end = _unique_steps(wp, 'next', exit_m)
        except ValueError:
            continue
        if _junction_id(start) is not None or _junction_id(end) is not None:
            continue
        if _angle_difference(_yaw(start), _yaw(end)) > 20:
            continue
        key = (jid, int(wp.road_id), int(wp.lane_id))
        candidates[key] = {'start': start, 'center': wp, 'end': end,
                           'junction_id': jid, 'road_id': int(wp.road_id),
                           'lane_id': int(wp.lane_id)}
    pairs = []
    routes = list(candidates.values())
    for i, ego in enumerate(routes):
        for other in routes[i+1:]:
            if ego['junction_id'] != other['junction_id'] or ego['road_id'] == other['road_id']:
                continue
            diff = _angle_difference(_yaw(ego['start']), _yaw(other['start']))
            if not 70 <= diff <= 110:
                continue
            pairs.append((ego, other))
    if len(pairs) != 1:
        raise ValueError('Need one unambiguous perpendicular intersection route pair')
    return pairs[0]


def validate_equipment_inventory(path, blueprint_id, expected_count):
    """Bind an independently authored asset inspection, never infer hardware from a bit."""
    path = Path(path)
    source = path.read_bytes()
    record = json.loads(source)
    lamps = record.get('installed_backup_lamps')
    if (record.get('blueprint_id') != blueprint_id or
            record.get('inspection_method') not in ('asset_mesh_review', 'physical_asset_review') or
            not record.get('inspector') or not isinstance(lamps, list) or
            len(lamps) != expected_count or
            any(not isinstance(x, dict) or not x.get('location') or
                not x.get('asset_source') for x in lamps)):
        raise ValueError('Sourced backup-lamp asset inventory missing or incompatible')
    return {'kind': 'motor_vehicle', 'blueprint_id': blueprint_id,
            'blueprint_source_sha256': sha256(source).hexdigest(),
            'installed_backup_lamps': lamps,
            'inspection_method': record['inspection_method'],
            'inspector': record['inspector']}


def construct(world, carla, config, equipment_inventory):
    """Create a separate ego and other vehicle with fixed scene purpose."""
    ego_route, other_route = discover_routes(world.get_map(),
        approach_m=config['approach_m'], exit_m=config['exit_m'])
    library = world.get_blueprint_library()
    ego_bp = library.find(config['ego_blueprint_id'])
    other_bp = library.find(config['other_blueprint_id'])
    equipment = validate_equipment_inventory(equipment_inventory,
        str(ego_bp.id), config['installed_backup_lamp_count'])
    owned = []
    try:
        for bp, route, label in ((ego_bp, ego_route, 'ego'),
                                 (other_bp, other_route, 'other vehicle')):
            transform = route['start'].transform
            actor = world.try_spawn_actor(bp, transform)
            if actor is None:
                raise ValueError(label + ' Native actor spawn failed')
            owned.append(actor)
        equipment['actor_id'] = owned[0].id
        context = {'junction_id': ego_route['junction_id'],
                   'other_vehicle_purpose': 'perpendicular moving intersection context',
                   'other_vehicle_priority': 'unresolved pending source review',
                   'ego_road_id': ego_route['road_id'],
                   'other_road_id': other_route['road_id']}
        return {'ego': owned[0], 'other': owned[1], 'owned': owned,
                'ego_route': ego_route, 'other_route': other_route,
                'equipment': equipment, 'context': context}
    except BaseException:
        for actor in reversed(owned):
            actor.destroy()
        raise


def drive_through(actor, world_map, carla, route, *, speed_mps=5., gain=.2):
    """Follow the selected source lane; reject branch or wrong-road drift."""
    transform = actor.get_transform()
    wp = world_map.get_waypoint(transform.location)
    if wp is None or int(wp.road_id) != route['road_id']:
        raise ValueError('Participant left selected approach road')
    options = [n for n in wp.next(6.)
               if _angle_difference(_yaw(n), _yaw(route['start'])) <= 25]
    if len(options) != 1:
        raise ValueError('Through lane lookahead ambiguous')
    target = options[0].transform.location
    desired = atan2(target.y-transform.location.y, target.x-transform.location.x)
    yaw = radians(transform.rotation.yaw)
    error = atan2(sin(desired-yaw), cos(desired-yaw))
    velocity = actor.get_velocity()
    speed = hypot(velocity.x, velocity.y)
    delta = speed_mps-speed
    actor.apply_control(carla.VehicleControl(
        throttle=min(.65, max(0., gain*delta)),
        brake=min(.8, max(0., -.3*delta)),
        steer=min(.45, max(-.45, error/.6))))


def set_backup_lamp(actor, carla, desired_on):
    """Set and read back the Native bit, preserving all unrelated lamp bits."""
    mask = int(carla.VehicleLightState.Reverse)
    before = int(actor.get_light_state())
    desired = before | mask if desired_on else before & ~mask
    actor.set_light_state(carla.VehicleLightState(desired))
    actual = int(actor.get_light_state())
    if actual != desired:
        raise ValueError('Native backup-lamp state readback mismatch')
    return bool(actual & mask)
